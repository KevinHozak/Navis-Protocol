# Public repository hygiene

Vault indexes, search exports, journals, runtime databases, environment files,
credentials, signing keys, logs, crash dumps, backups, and local test output must
stay outside published Git history. `.gitignore` protects new files; it does not
remove files that were already committed.

## Local checks

Install Node.js and Gitleaks **8.30.1**. On Windows, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-gitleaks.ps1
npm run prepare
npm run security:scan:staged
npm run security:scan:tree
npm run security:scan
```

The installer verifies the pinned Windows archive SHA-256 before extracting it
into ignored `.tools/gitleaks/`. On other platforms, install the same version
from the [official release](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1)
on `PATH`. Husky checks staged additions/changes before commits and all reachable
Git history before pushes. Missing Gitleaks or a failed scan blocks the operation.
The output redacts detected credentials. Existing frontend/backend lint checks
still run after the staged scan.

GitHub Actions performs the same full-history check on pushes and pull requests,
using a checksum-verified Linux archive and read-only repository permissions.
Configure its `secret-scan` check as required in GitHub branch protection before
publication; the workflow alone does not prevent merging a failed check.

Keep fake credentials in tests visibly synthetic. Review findings individually;
do not exempt the entire tests directory. Sanitized environment examples can be
committed as `.env.example` or `.env.<name>.example`.

## Fresh public history

This repository was created independently from a reviewed source snapshot. It
starts with one initial commit; private development commits, old branches, tags,
issues, PR references, and recovery refs were not imported. The prior development
repository remains private and must not be made public as part of routine work.
Never fetch/merge the old private repository into this repository or push recovery
refs here. Recover individual source changes only after reviewing their contents.

Personal portraits are replaced with neutral project artwork. Published image
metadata was reviewed and nonvisual EXIF/XMP/IPTC/text records were removed while
preserving rendered pixels. Review new images and documents before adding them;
credential scanning cannot identify private faces, journal prose, or copyrighted
material on its own.

The ignore rules and publication path policy reject Vault roots, credential JSON,
signing keys, databases and their sidecars, logs, archives/backups, and generated
exports. `npm run security:test` exercises that path policy in CI. Environment
examples are explicitly allowed; actual environment files are excluded. Container
and cloud upload contexts also exclude local data and credentials.

Run `npm ci` once at the root to install Husky, then install Gitleaks and run
`npm run prepare`. Branch protection on public main requires the `secret-scan`
check, blocks force pushes/deletions, and requires a pull request for changes.
Repository owners can administer these settings; local hooks can be bypassed,
so the required CI check supplies the shared enforcement boundary.

## Cloud import configuration

The optional cloud library search and datastore/import scripts require `NAVIS_GCP_PROJECT` and
`NAVIS_GCS_BUCKET` in the invoking process environment. Google Cloud credentials
remain outside the repository through Application Default Credentials. The
generated metadata index remains a local ignored file. Frontend `.env.production`
is excluded from Google Cloud upload; provide deployment configuration through
the build/deployment environment.
