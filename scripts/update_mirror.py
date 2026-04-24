#!/usr/bin/env python3
"""
Update the OpenTofu/Terraform network-mirror index for this provider after a
release is published.

Given a version tag (e.g. `v1.0.1-lavndr.1`), this script:
  1. Fetches the SHA256SUMS file from the corresponding GitHub Release.
  2. For every platform zip, computes an `h1:<base64-sha256>` hash.
  3. Writes / updates:
       mirror/registry.terraform.io/LavndrCommunity/googleworkspace/index.json
       mirror/registry.terraform.io/LavndrCommunity/googleworkspace/<version>.json
  4. Leaves previous versions in index.json untouched (additive).

Designed to run from the release-published workflow in this repo. Idempotent —
running twice for the same version produces no diff.

Why this exists: `it-infra` consumes this provider via a `provider_installation
{ network_mirror }` block pointing at raw.githubusercontent.com/.../mirror/.
OpenTofu expects a static JSON index at that URL shape, and GitHub Releases
don't natively serve it. Generating it on release keeps the mirror automatic.
"""

import argparse
import base64
import json
import re
import sys
import urllib.request
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


def fetch_shasums(tag: str, version: str) -> str:
    url = RELEASE_URL_TMPL.format(tag=tag, fname=SHASUM_FNAME_TMPL.format(version=version))
    with urllib.request.urlopen(url) as resp:
        return resp.read().decode()


def build_version_json(tag: str, version: str, shasums: str) -> dict:
    archives: dict[str, dict] = {}
    for line in shasums.strip().splitlines():
        hex_hash, fname = line.split()
        if not fname.endswith(".zip"):
            continue
        m = PLATFORM_RE.search(fname)
        if not m:
            continue
        os_, arch = m.group(1), m.group(2)
        raw = bytes.fromhex(hex_hash)
        h1 = "h1:" + base64.standard_b64encode(raw).decode()
        archives[f"{os_}_{arch}"] = {
            "url": RELEASE_URL_TMPL.format(tag=tag, fname=fname),
            "hashes": [h1],
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

    shasums = fetch_shasums(tag, version)
    version_json = build_version_json(tag, version, shasums)
    index_json = update_index(version)

    write_json(MIRROR_DIR / f"{version}.json", version_json)
    write_json(MIRROR_DIR / "index.json", index_json)

    print(f"Updated mirror for {tag}: {len(version_json['archives'])} platforms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
