# Local NL0 extraction and incremental-review record

Use [the procedure](../references/source-refactoring.md) and
[executable guide](../references/integrated-workflow.md). This worksheet is not
itself an acceptance record; the adapter validates the actual JSON reviews.
All review fields begin UNVERIFIED and can
change only after actual inspection. Keep the baseline files immutable.

## Baseline and scope

- Baseline canonical graph/spec paths and SHA256:
- Baseline Audit A path/SHA256, exact scope, actual status and reviewer disclosure:
- Baseline evidence verified; outstanding FAIL/UNVERIFIED items:
- Revised package directory and revision identity:
- Operation: translation-preparation proof factoring, not NL0 reconstruction.
- Protected original target/H/D/E/M/logic/pins and existing N/P statements:
- Candidate IDs and proposed edit allowlist:
- Mathematical author, delta reviewer and actual prior exposure:

## One record per candidate

- Candidate ID:
- Existing exported N usable instead of new extraction? Explain:
- Repeated occurrences: exact old R IDs and JSON pointers/paragraph spans:
- Avoided repeated work expected; basis and unmeasured assumptions:
- Proposed new N/R IDs:
- Full statement with all binders, domains and conditions:
- Direct inputs and their roles:
- Existing derivation to copy, its source spans and required local context:
- Any temporary assumption, witness, choice, definition guard or escaping local:
- Why this is an existing derivation, without stronger/generalized mathematics:
- Eligibility judgment and actual evidence: UNVERIFIED
- Candidate outcome: UNVERIFIED / STAGED / DEFERRED_NOT_LOCAL / REJECTED

## Patch manifest

| Stable ID / JSON pointer | Before hash / exact span | After hash / exact span | Permitted edit and reason |
| --- | --- | --- | --- |

- New producer proof and its mapping to old derivation spans:
- Every changed consumer input/citation/application record:
- All other mathematical records/spans preserved:
- Global graph/spec check command, actual output and artifact hashes:
- Cycle/reachability/definition-guard/producer checks:
- New source package hashes and actual diff artifact:
- Unexplained changes: UNVERIFIED

## New producer review

Apply the ordinary Audit A obligations to the full new N/R. Record actual
source applications and the fresh packet-only replay separately.

- Complete statement, objects and dependency closure: UNVERIFIED
- Inputs, argument, accounting and exact output: UNVERIFIED
- Scope, guards and E/M applicability: UNVERIFIED
- Fresh replay carrier/input boundary, packet hash and evidence: UNVERIFIED
- Review verdict and located evidence: UNVERIFIED
- Scope: producer packet only; whole-graph acceptance and comparison to the old
  derivation belong to the separate substitution/evidence checks.

## One substitution review per consumer

- Consumer R ID and exact replaced span:
- This consumer's old derivation and the separate supplier derivation for the
  shared producer; compare intermediate conclusions, not consumer final goals:
- Exact reviewed cut packet SHA256; inherited evidence and actual exposure:
- Old conclusion at the cut, with binders/conditions/conventions:
- Shared theorem instantiation and exact supplied conclusion:
- Evidence discharging every application condition:
- Facts/objects/values/scopes needed by the unchanged continuation:
- Evidence that these remain available and unchanged:
- Old source/application accounting and its exact replacement:
- Unchanged region hashes and precise baseline judgments inherited:
- New judgments covering the changed boundary, with located evidence:
- Exposure: delta review with baseline access, not a fresh whole-R replay.
- Boundary review verdict: UNVERIFIED
- Review the actual source format: N calls use direct inputs/prose, while
  `applications` records belong only to E/M; do not require invalid N records.
- The shared application replaces the selected derivation rather than merely
  adding an annotation; actual before/after evidence: UNVERIFIED
- If not local, defer the candidate instead of expanding to whole-case review:

## Coverage and disposition

- Baseline + new reviews cover each revised proof region; coverage evidence:
- Inherited unresolved items and currently blocked descendants:
- Actual discovery/edit/check/review elapsed time and any model/tool faults:
- Record status: UNVERIFIED / DELTA-REVIEW-PASSED / DEFERRED_NOT_LOCAL / REJECTED
- Accepted source revision, or baseline retained; exact reason:
- Executable acceptance: source_preparation.py check result and
  source-acceptance.json; baseline and all new evidence revalidated by Audit B.
- Actual inherited baseline qualifications and reviewer exposure:
- Pending work before production acceptance and worker-packet generation:

## Boundary example

Suppose old R010 and R020 each explicitly derive L(x) from A and B, then use it
in different continuations. Copy one complete derivation into a new producer
of `for every x in the stated domain, A(x) and B(x) imply L(x)`. At each actual
occurrence, keep the same x, discharge A(x)/B(x), and replace only that proof
span by this application. Review the new closed statement and each cut.

Do not replace a span that also selected a witness w used later by a theorem
merely asserting `there exists w`: that may lose the required value/scope.
Defer the extraction unless the exact continuation interface can be preserved.
These examples explain the review method; they are not executed controls or
evidence that a model correctly follows it.
