# Release checklist

**Release candidate prepared October 25, 2026. Public publication is awaiting the owner's explicit approval.** The private master remains `swanal3131-cpu/EURJPY-Trading`. The separate release repository is `swanal3131-cpu/EURJPY-V3-Research`, staged privately. No public visibility, public Release, public Pages site or college portfolio is authorized by this preparation.

## Private master and October 24 remediation

The private master was verified on October 25 at `6635133c4dbf31ba4738e805dfd655823e6720d6` on `main`, with four commits. Its earlier commits, files and history are preserved. The October 19 upload was an earlier verification, not a new upload or test performed on October 25.

The October 24 commit completed the dependency remediation: Pillow changed from 12.3.0 to **13.0.0** in the runtime/test lock, and **certifi 2026.10.19** was pinned for the separate security environment. Those exact pins are carried into this candidate. The earlier three private commits contain personal email metadata and must remain private; a later noreply commit does not remove that metadata.

The public candidate was exported from the exact 38 tracked files at that private-master commit. No `.git` directory, Git objects, original history, ignored files or untracked files were copied. A new `main` history uses the owner's verified GitHub numeric noreply identity for both author and committer. Do not publish the private master or merge its ancestry into the release repository.

## Validation performed October 25 on the candidate

| Check | Result and scope |
|---|---|
| Automated tests | **32 passed**, Python 3.14.3. See [test output](../security/test_results.txt). |
| Environment | Existing isolated environment matched every runtime/test lock pin; `pip check` passed. This review does not claim a newly installed environment. |
| Authorized data reproduction | Input matched the previously documented fingerprint; all **18 independent accounting reconciliations** and saved-artifact validation passed. Source data was read privately, not copied into the release. |
| Aggregate results | Both performance and cost-sensitivity CSVs reproduced **byte for byte**. Continuous result remains 120 trades and **-1,064.8 net pips**. See [reproduction record](../security/fresh_reproduction.json). |
| Dependency vulnerability refresh | Live PyPI version vulnerability records queried for **26 exact versions**, covering the runtime/test lock, security pins and installed scanner dependencies; no nonwithdrawn entries were returned. This is a dated database check, not a guarantee against undisclosed vulnerabilities. |
| Content and security | Every release file, exact staged blob, fresh Git history and decoded media are reviewed. The scanner uses detect-secrets 1.5.0 with 27 detectors and no network verification. The verified noreply identity is permitted only in Git metadata using the explicit scanner option documented in [SECURITY](../SECURITY.md). |
| Paper, charts and links | Five-page PDF, four PNG figures, decoded metadata/content, internal links and documented reproduction commands are checked. The paper and all figures retain their private-release bytes. |
| Research integrity | Strategy, parameters, execution/accounting code, costs, findings, conclusions, provider attribution and both aggregate CSVs are unchanged. |

## Content and rights review

| Category | Treatment |
|---|---|
| Original Python and documentation | Included. The sole Python change is the security scanner's explicit noreply handling and correction of email false positives in compressed Git storage; decompressed objects remain checked and research Python is unchanged. |
| Derived statistics | Only `research_summary/performance_summary.csv` and `research_summary/cost_sensitivity.csv` are included. No detailed ledgers or temporary results. |
| Research charts | All four approved figures retained with source credit in README, captions and comparison-chart footers. |
| Research paper | Original five-page PDF and accessible Markdown retained, including negative findings, limitations and AI-assistance disclosure. |
| Raw London Strategic Edge data | Excluded, together with intermediate OHLC, detailed price-level exports, credentials, personal email metadata, private correspondence and private application materials. |
| Provider permission | Existing project-specific permission for the requested code, derived charts, statistics and paper is documented with relevant credit. No broader data rights or endorsement are implied. Supporting correspondence stays private. See [provenance](DATA_PROVENANCE.md). |
| Software license | **No LICENSE file and no software license assigned.** A specific license requires a separate owner decision. |

## Publication gate

- Preserve the private master and private supporting correspondence.
- Confirm the final 38-file manifest, candidate commit, fresh history and private staging-repository tree match the release review.
- Obtain the owner's **explicit approval for public visibility of the separate release repository** before exposing any content. Approval has not been given.
- After approval, change only the release repository's visibility and verify public access, rendering, links and commit metadata. Public GitHub verification is still pending.
- Create the two-paper college research portfolio only after public GitHub verification and a subsequent request. No portfolio work is part of this release.

The technical candidate is prepared for the publication decision. Publication status is **private staging; public approval and public-access verification pending**. Prior October 15-19 evidence is historical; the dated checks above identify the work rerun on October 25.
