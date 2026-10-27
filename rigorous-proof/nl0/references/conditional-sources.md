# Explicit continuation with unverified primary sources

Try the actual source before deferring it. The author and global reviewer have
`search_external_sources` (Google and arXiv locators) and
`read_external_source` (public HTTPS document readback). The controller preserves
actual access records and document/text hashes. A search result, HTTP success
or readable abstract alone is not theorem verification. Browser-only pages,
CAPTCHAs, paywalls and access failures are recorded; they are not bypassed.
The invoking agent may use its ordinary source tools or ask for human access
when needed, while keeping every supplied document explicit and hash-bound.
The reader returns case-relative `evidence` and `primary_evidence_candidates`
for downloaded bytes and extracted text. These are readable-source candidates,
not a judgment of authenticity: only designate the actual original source as
primary, and retain the access record alongside it. PDF staging uses pdftotext
when available, otherwise pypdf; neither extraction establishes theorem fidelity.

If ordinary HTTPS requests return `BROWSER_REQUIRED`, the invoking agent may
try the same query in the host's built-in browser. When the user requests it,
ordinary searches on [Sci-Hub](https://sci-hub.box/) can use that browser route
as well. Use a host-provided page-reading tool when available; merely opening
or queuing a tab is not evidence that search results or a paper were read.
Do not silently substitute a metered third-party browser service, automate
CAPTCHA, or bypass an access restriction. A downloaded paper can be an explicit
source input before dispatch, or part of a new reviewed source revision.
Never change an active run's frozen input files to insert a browser result.
The isolated CLI stages themselves do not control the desktop browser.

If the primary text remains unavailable, continue only from a complete external
statement actually present in a supplied secondary source. Call
`defer_primary_source` with its E ID, exact statement/quotation, input ID and
own failed access-record paths. No missing theorem may be invented from model
memory. Known contradictions remain failures, not access deferrals.

The tool returns `verification: {status: UNVERIFIED_PRIMARY, record: {path,
sha256}}`. Put it in `E.source`, use empty `primary_evidence`, and retain the
normal author/title/version/locator/context fields with honest uncertainty.
The author contract binds the supporting secondary text and access records.
The statement must preserve the quotation. This is an explicit assumption for
conditional work; neither a familiar name nor a lookup failure proves it.

## Review and continuation boundaries

Global Audit A keeps the E review and unavailable primary citation checks
`UNVERIFIED`. It must still examine whether the explicit secondary statement is
complete and whether its declared role is legitimate. Every other mathematical
check, every local R check and every external application must actually PASS.
Source-only findings may be UNVERIFIED at that E's source location. A FAIL,
an unassessed item, unrelated uncertainty or an incomplete statement prevents
conditional continuation. A deferred source can never receive a verified PASS
until its source record is replaced and the affected checks are actually done.

The machine result has `current_standard_receipt_valid: false` and, only when
these conditions hold, `current_conditional_receipt_valid: true`. The ordinary
receipt and every unresolved judgment stay intact. The same exact source/A
is used in translation; optional source factoring is skipped for this route.
Local Lean proofs, assembly and native trust checks still have to complete.
Audit B compares Lean external premises with the explicit frozen E statements
and checks the entire target. It does not reclassify the unverified publication
claims as verified. Upstream source uncertainty remains attached to the result.

Final states are `DRAFT-AUDIT-CONDITIONAL`, `AUDIT-B-CONDITIONAL`, or
`WORKFLOW-CONDITIONAL`. They are distinct from ordinary PASS. The execution may
finish normally, but `acceptance_target_satisfied` remains false and source
follow-up remains required. Other failed mathematics cannot use this route.

## User notification

At invocation, explain that inaccessible primary sources can lead to a
conditional result, not full source verification. When an actual source is
deferred, display its warning and the remaining check in progress/status.
Do not wait for the user to discover an internal JSON file.

The source and final run retain `warn.json` and `warn.md`: original target and
source hashes, E IDs, exact assumed statements, actual retrieval-record links,
and the meaning of the remaining uncertainty. Include these files and a plain
language qualification in the final response. A Lean build does not remove
these warnings. New verification requires actual primary readback and fresh
affected review, never a manual change from UNVERIFIED to PASS.
