# FORK.md

This is a LavndrCommunity fork of [`arslanbekov/terraform-provider-googleworkspace`](https://github.com/arslanbekov/terraform-provider-googleworkspace). Consumed by [`LavndrCommunity/it-infra`](https://github.com/LavndrCommunity/it-infra).

We forked for bus-factor reasons, not to diverge. The goal is to stay near upstream, pick up fixes quickly, and be able to take over maintenance if upstream goes dormant. See [`it-infra/.claude/plans/workspace-iac-coverage.md`](https://github.com/LavndrCommunity/it-infra) (local-only plan) for the full rationale.

## Who consumes this fork

One consumer today: `LavndrCommunity/it-infra` via a network mirror (`provider_installation { network_mirror }`) pointing at this repo's GitHub Releases. Not published to the Terraform Registry — if we ever gain a second consumer, evaluate registry publishing then.

## Release process

The release workflow (`.github/workflows/release.yml`, inherited from upstream) fires on any `v*` tag push. It:

1. Imports the GPG signing key from repo secrets.
2. Runs goreleaser, which builds platform binaries, a zipped archive per platform, a `SHA256SUMS` checksum file, and a GPG signature over it.
3. Publishes everything as a GitHub Release on this repo.

### First-time setup (done once by a maintainer)

1. **Generate the GPG signing key** on your machine (or wherever you manage secrets):
   ```bash
   gpg --full-generate-key
   # RSA + RSA, 4096 bits, no expiry (or long expiry — this key is long-lived).
   # Real name: "Lavndr Community"
   # Email:     "ops@lavndr.community"
   # Passphrase: something strong, stored in the shared vault alongside the private key.
   ```
2. **Export the private key** for GitHub Secrets:
   ```bash
   gpg --armor --export-secret-keys ops@lavndr.community > private.asc
   ```
3. **Store the public key** where consumers can verify signatures — key server, a file in this repo, or the `it-infra` docs. For now, attach the `.asc` public key to the first GitHub Release and note the fingerprint here:
   > GPG fingerprint: `BBD614EB5E2D6DB6441439A078525BAAF90C3396`
   > Key: `rsa4096/78525BAAF90C3396`, name `Lavndr Community <ops@lavndr.community>`, generated 2026-04-24.
4. **Add secrets** to this repo → Settings → Secrets and variables → Actions:
   - `GPG_PRIVATE_KEY` — contents of `private.asc`
   - `PASSPHRASE` — the passphrase from step 1
5. **Verify**: push a throwaway tag (e.g. `v0.0.0-setup-test`) to trigger the release workflow, inspect the resulting release, then delete it.

### Cutting a release

Only tag when a sync-merge (or a bugfix we've patched ourselves) introduces something we want our consumers to pick up. Not every sync needs a tag.

```bash
# From main, at the commit we want to release:
git tag -s v1.0.1-lavndr.1 -m "release v1.0.1-lavndr.1"
git push origin v1.0.1-lavndr.1
```

**Tag scheme**: `v<upstream_version>-lavndr.<n>`. The suffix ensures our tags can't collide with upstream's. Increment `<n>` per our release; reset `<n>` to `1` when `<upstream_version>` changes.

After the release workflow completes (~5 min), update `it-infra`'s `required_providers` version to the new tag and open a PR there.

## Weekly upstream sync

Every Monday 09:00 UTC, `.github/workflows/sync-upstream.yml` fetches `upstream/main` and, if we're behind, opens a `sync/upstream-<date>` PR with the merge. See the workflow file for details.

### Review checklist for a sync PR

CI catches regressions; this checklist catches things CI can't.

- [ ] Diff is **incremental** — no resources removed or renamed without a plan.
- [ ] No schema breaks on existing resources (scan `internal/provider/resource_*.go` changes for field-type changes, removed attributes, or changed `Required`/`Optional`/`Computed`).
- [ ] No CI changes that alter what gets built or published.
- [ ] CI is green on the PR.
- [ ] If behavior changes (eventual-consistency timing, API call patterns, retry semantics): document in a short note appended to this file so consumers know before upgrading.
- [ ] If this PR introduces something we actively want downstream, follow the release process above after merging.

### When upstream goes dormant

If `arslanbekov/terraform-provider-googleworkspace` has no non-dependabot commits for **90 days**, we start accepting PRs directly on this fork and maintaining it ourselves. The provider is ~15 resources; this is tractable with IT team bandwidth.

Signals that upstream is truly dormant (vs quiet):

- No comments on open issues or PRs.
- No response to maintainer-tagged issues.
- Sync workflow keeps reporting "Nothing to sync" for consecutive months.

Before flipping this switch, open a tracking issue on this repo documenting the decision and pinging the previous upstream maintainer.

## Behavior notes

Drift from upstream, if any, gets noted here per sync. Currently: none — we're a clean mirror.

<!-- Format for future entries:
### 2026-MM-DD — sync `<upstream_sha>`

- Noted change: ...
- Consumer impact: ...
-->
