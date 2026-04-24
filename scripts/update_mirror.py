#!/usr/bin/env python3
"""
Update the OpenTofu network-mirror index for this provider after a release is
published.

Given a version tag (e.g. `v1.0.1-lavndr.1`), this script:
  1. Lists platform zips from the corresponding GitHub Release's SHA256SUMS.
  2. Downloads each zip and computes the OpenTofu/Terraform `h1:` content hash
     (Go `dirhash.Hash1` algorithm — *not* SHA-256 of the zip itself).
  3. Writes / updates:
       mirror/registry.opentofu.org/lavndrcommunity/googleworkspace/index.json
       mirror/registry.opentofu.org/lavndrcommunity/googleworkspace/<version>.json
  4. Leaves previous versions in index.json untouched (additive).

Why this exists: `it-infra` consumes this provider via a `provider_installation
{ network_mirror }` block. OpenTofu expects a static JSON index in a specific
shape, and GitHub Releases don't natively serve it. Generating it on release
keeps the mirror automatic.

Why h1 specifically: OpenTofu's network mirror requires content-hash
verification of each archive, and the supported hash format is `h1:` —
defined as the SHA-256 of a sorted, line-prefixed list of every file inside
the zip. Plain SHA-256 of the zip file (the easy option) is *not* what
OpenTofu accepts here.

Designed to run from the release-published workflow in this repo. Idempotent —
running twice for the same version produces no diff.
"""

import argparse
import base64
import hashlib
import io
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

MIRROR_DIR = Path("mirror/registry.opentofu.org/lavndrcommunity/googleworkspace")
RELEASE_URL_TMPL = (
    "https://github.com/LavndrCommunity/terraform-provider-googleworkspace"
    "/releases/download/{tag}/{fname}"
)
SHASUM_FNAME_TMPL = "terraform-provider-googleworkspace_{version}_SHA256SUMS"
PLATFORM_RE = re.compile(r"_([a-z]+)_([a-z0-9]+)\.zip$")


def strip_v(tag: str) -> str:
    return tag[1:] if tag.startswith("v") else tag


def fetch_url(url: str) -> bytes:
    with urllib.request.urlopen(url) as resp:
        return resp.read()


def hash1_zip(zip_bytes: bytes) -> str:
    """Compute Go `dirhash.Hash1` over a zip's contents.

    For each entry in alphabetical order, write `<hex_sha256>  <name>\\n` to a
    rolling SHA-256, then base64 the digest with the `h1:` prefix.
    """
    h = hashlib.sha256()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        for name in sorted(z.namelist()):
            content = z.read(name)
            file_hex = hashlib.sha256(content).hexdigest()
            h.update(f"{file_hex}  {name}\n".encode())
    return "h1:" + base64.standard_b64encode(h.digest()).decode()


def build_version_json(tag: str, version: str, shasums: str) -> dict:
    archives: dict[str, dict] = {}
    for line in shasums.strip().splitlines():
        _hex, fname = line.split()
        if not fname.endswith(".zip"):
            continue
        m = PLATFORM_RE.search(fname)
        if not m:
            continue
        os_, arch = m.group(1), m.group(2)
        zip_url = RELEASE_URL_TMPL.format(tag=tag, fname=fname)
        zip_bytes = fetch_url(zip_url)
        archives[f"{os_}_{arch}"] = {
            "url": zip_url,
            "hashes": [hash1_zip(zip_bytes)],
        }
    if not archives:
        raise SystemExit(f"No platform zips found in SHA256SUMS for {tag}")
    return {"archives": archives}


def update_index(version: str) -> dict:
    index_path = MIRROR_DIR / "index.json"
    if index_path.exists():
        index = json.loads(index_path.read_text())
    else:
        index = {"versions": {}}
    index["versions"].setdefault(version, {})
    return index


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tag", help="Release tag, e.g. v1.0.1-lavndr.1")
    args = ap.parse_args()

    tag = args.tag
    version = strip_v(tag)

    shasums_url = RELEASE_URL_TMPL.format(
        tag=tag, fname=SHASUM_FNAME_TMPL.format(version=version)
    )
    shasums = fetch_url(shasums_url).decode()
    version_json = build_version_json(tag, version, shasums)
    index_json = update_index(version)

    write_json(MIRROR_DIR / f"{version}.json", version_json)
    write_json(MIRROR_DIR / "index.json", index_json)

    print(f"Updated mirror for {tag}: {len(version_json['archives'])} platforms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
