# Credential security

V3 runs on a local historical CSV with no API credentials. There is no `.env` file or `.env.example`, because this program needs neither. Runtime requirements exclude the original API client, dotenv and WebSocket packages. The original environment and private configuration were not copied.

The root `.gitignore` excludes `.env`, `.env.*` (while allowing a placeholder-only `.env.example` if one is ever needed), Python caches/environments, private key files, `credentials.json`, raw inputs and detailed local outputs. These rules are only a safeguard: they do not protect already staged files.

The final scan covers every working-tree file, text and binary bytes, hidden files, documentation, reports and logs. detect-secrets scans all eligible text files, with all default detectors and no network verification. Supplemental checks detect sensitive file names, private-key material, personal paths/emails, credential assignments and forbidden network/authentication imports in runtime code. Git-index bytes are checked against the scanned files and directly inspected. A local reference `.env` may optionally be compared in memory; its values and fingerprints are never written or displayed.

The project contains no notebooks or source-price datasets. Aggregate research summaries are included; detailed market prices, intermediate candles, private runtime outputs and original files/history are not copied. Project-specific support permission for the requested derived results is recorded in `docs/DATA_PROVENANCE.md`, conditional on attribution. Raw-data redistribution is excluded; the owner must approve publication separately.

Run `python -B tools/security_scan.py` after changes and again after staging, before publication. Install `requirements-security.txt` separately if needed. The scanner returns nonzero on findings and reports paths/types/line numbers only; do not print matched lines or credential values. A clean scan is evidence within these checks, not a mathematical guarantee that all possible credentials are absent.

The all-file scan includes ignored files. For a publication audit, keep authorized input CSVs, virtual environments and detailed runtime outputs outside the release candidate; the README commands use sibling environment and results directories. Ignored private outputs are not automatically suitable for inclusion in a review ZIP.

If a potential credential is found, stop publication preparation. Remove it from the proposed publication, inspect staging and history, and rerun the scan. If it was exposed in a public repository, revoke and rotate it through the provider. Deleting a file or adding an ignore rule does not revoke a credential or erase public history.

No original public history was imported or audited here. No credential exposure was found in the reviewed V3 snapshot. This does not establish that a credential was never exposed elsewhere.

## Fresh public-release history

The separate release candidate has fresh history; the private master and its earlier personal email metadata remain private and unchanged. For a known, reviewed GitHub numeric noreply identity, use PowerShell:

```powershell
python -B tools/security_scan.py --allowed-git-email (git config user.email)
```

First verify that the local `user.email` value is the owner's GitHub noreply identity. The option accepts only the numeric GitHub noreply format and permits exactly that value only in `.git/` metadata. It does not suppress personal emails or email findings in working-tree files or indexed blobs. Without this option the scanner remains strict and flags all email addresses. Before the initial commit, add `--require-fresh` to require zero commits and zero remotes. After a commit, use the command above without `--require-fresh`.

Review every commit and every Git object separately, including packed objects; `--require-fresh` does not by itself establish what was later committed. The October 25 review checks all objects and both author and committer identities. Public access still requires the owner's explicit approval. No software license is added.

Loose Git objects are scanned after decompression. Email-like text created by decoding compressed storage bytes is not treated as a real email; the actual decompressed object is checked for all email addresses. Exact private-reference values, private-key material and personal paths remain checked in storage bytes as well. This avoids false privacy findings while preserving checks of the content Git actually stores.
