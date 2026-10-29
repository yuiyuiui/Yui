# Review completion, local repair and inherited evidence

This is an execution contract for authors, reviewers and controllers. It does
not change NL0's mathematical standard or prove a reviewer's judgment correct.

## Per-case roles

Use one serial NL0 author and one serial preparation/global-review lane.
Finish the global Audit A stage first, then review frozen R packets in up to
N independent fresh contexts. Each packet keeps its own directory, source
hash, profile, tool evidence and result. Submit the same frozen version to all
reviewers; never share sibling judgments or proof bodies. Collect by stable
job ID, independent of finish order. Retain completed results if a sibling
fails. Actual source revisions get new packets and invalidate affected work.
Interface work, assembly and Audit B stay serial. Local Lean proof work uses
the same confirmed N in a separate later phase. `concurrency.CaseBudgets`
records all three lanes in one ledger and rejects phase overlap. Independent
cases may overlap; their mutable stores and mathematical inputs do not.

## Preserve work at its actual boundary

- Known IDs, hashes, pins and printer metadata are controller data. Populate
  omissions; reject explicit identity conflicts. Never rewrite mathematical
  statements to resolve a conflict. Return independent cheap reference errors
  together with exact locations and valid IDs.
- Patch an explicit own-stage candidate. Retain the expanded draft on a failed
  check. Restarting an older frozen base requires an explicit reset. A metadata
  correction is not a new mathematical proof or a reason for cold authoring.
- An available definition is not an unavailable theorem. Put it in D; justify
  any property from registered sources or displayed proof. Routine bookkeeping
  is unfinished drafting, not a substantive mathematical gap.
- A type/API/tactic failure stays in its interface or proof task. Return to
  NL0/Audit A only if mathematical content or allowed dependencies must change.
- Keep an unchanged accepted source/Audit A when a later interface fails.
  Earlier execution policy remains disclosed; it is not relabeled a new run.

## Complete actual assessments

`ReviewContract` separates coverage (`unread`, `read`, `assessed`) from verdict
(`PASS`, `FAIL`, `UNVERIFIED`). New review stages disclose their required item
pointers. Save actual rows using `record_review_item`, inspect them using
`read_review_progress`, and finish through `submit_draft` with either complete
coverage or `{from_saved_review:true, summary:{...}}`. Summary fields contain
the reviewer's actual overall verdict/notes/findings where required; the
controller never fills PASS.

A submission with unread work continues the same stage and remaining budget.
An evaluated uncertainty may finish UNVERIFIED, with a specific reason. A real
located blocker may finish early through `submit_review_blocker` after saving
its assessed FAIL item. The report remains explicitly incomplete. Reading an
interval establishes access, not comprehension or mathematical correctness.

Fresh reviewers receive only their canonical task/candidate, required source
evidence and rules. They receive no author repair history, previous verdict,
unused candidate, personal memory or foreign-case material. Packet replay
retains its packet-only boundary even when the global reviewer saw sources.

For a blocking Audit A finding, give an exact supplied location and a short
verbatim `quotation:{location,text}`. Global references use an input document
ID plus a resolving JSON pointer, or an existing input/pinned-library line
span. Packet references resolve in the packet. Program checks bind quoted
bytes, not the truth of the objection. Compare the actual constants, domains
and quantifiers before requiring a repair. A disputed objection retains its
raw verdict; one explicitly disclosed targeted adjudication is permitted,
and unresolved disagreement stays disputed. Do not resample an unchanged
proof/review until PASS. Ordinary independent defects should be collected
together when feasible within the current review budget.

Authorized warm author inputs may include `repair-obligations.json` with
`version:yui-repair-obligations-1`, `baseline_input` naming an explicit input,
`baseline_content_sha256` binding that input's canonical `{spec,graph}` and
`issues:[{id,criterion,location,note},...]`. Issue locations resolve in that
baseline. These diagnostics persist until actual located author resolutions
and fresh scoped review; they are not mathematical premises or prior PASS.
Cold authors receive none of this file, the old source or prior findings.

## Interface phase and disputes

Review complete typed obligations, direct inputs, source mappings and planned
conversion obligations. Proof bodies are produced by subsequent workers and
must all be discharged at assembly/Audit B. Type elaboration does not prove
those obligations. Definitions that need construction proofs must elaborate;
their fields may not hide an unproved target.

Locate alleged mismatches on both the exact source and formal sides, including
object/scalar field, binders, domains, hypotheses and conclusion. Blocking
interface findings carry paired literal excerpts and their specific difference.
The controller checks the quoted bytes/locations, not semantic equivalence.
A property assumed on one object or field is not automatically the target on
another. A planned bridge is not an imported source assumption.

For an evidence-backed disagreement, an operator may prepare one targeted
adjudication with `interface_review.py prepare --adjudicate PRIOR --dispute
DISPUTE.json`. The dispute contains the paired `comparison` record required
by the interface validator. Prior source/contract/plan bytes must match.
The prior verdict and dispute are explicitly disclosed; this mode cannot claim
untouched independence or be adjudicated again. Retain the original result.
An unresolved disagreement stays disputed; never resample until PASS.

## Conservative Audit A reuse

An unchanged accepted whole source is reused directly. For local revisions,
`audit_a_campaign.py prepare --reuse-from PRIOR_CAMPAIGN` may inherit qualified
passing review items. The test queue exposes the same explicit `reuse_audits`
list; cold comparisons leave it empty. No implicit cross-case cache is read.

Compare the approved target/context, parameter domains, H contracts, logic,
relevant definitions/guards, complete direct inputs/output, local proof/scopes,
source contracts/pins and semantic rule hashes. Exclude only the known whole
graph/spec/packet envelope hashes. Preserve those hashes as provenance.
Copy bounded original evidence by content hash, compare old/current contexts,
and retain old raw judgment, execution qualification and costs. New reviewers
see only assigned work, without inherited verdicts. Whole-graph structure and
current complete coverage still need to pass.

New receipts bind inherited items through `inheritance` evidence. The NL0
reader validates it, and Audit B consumes that same authority chain. Inherited
packet replay refers to the actual old packet, not an invented new replay.
A passing item from a failed campaign is not a passing parent audit. Uncertain
equality misses the cache. A current structure-review failure is stored in the
receipt and blocks acceptance. Older accepted receipts retain their original
format/disclosure; they are not claimed to have newly added fields.

Existing bounded mathematical shared extraction still uses
`nl02lean/scripts/source_preparation.py`: its producer/substitution review
is separate from general exact item reuse. Neither mechanism re-proves the
whole NL0. Changed assumptions/definitions/statements invalidate affected work.

## Sources, outcomes and costs

Stage external source documents before clean review. Exact UTF-8 or explicitly
recorded PDF text extraction is access evidence, not authenticity. Unsupported
readbacks remain UNVERIFIED while other checks continue. Apply all nine
external-source requirements, five separate citation checks and every actual
application's binding/per-condition/conclusion checks. External premises remain
explicit in interfaces and Audit B; they are not advertised as Lean proofs of
the publications. Report blocked citation checks to the user.

Keep mathematical status, coverage, execution health, identity/input
qualification, usage completeness and stop reason separate. Missing usage alone
preserves a qualified mathematical candidate/judgment, but prevents a complete
performance result. Unknown model identity or input isolation blocks
qualification. Healthy budget exhaustion is MODEL_BUDGET_EXHAUSTED; faults,
unverified attribution and user stops remain separate.

Use `yui.py case-status SOURCE` for artifact-scoped progress and `yui.py metrics
RUN` for recorded phase/tool/request costs. Stage completion is not Audit A/B.
Nested tool durations are already inside stage wall time; request latency also
contains transport/service queues, not observable pure model reasoning. Warm
reuse keeps original acquisition cost and does not create a cold benchmark.

## Mathematical background during local review

Under mathematical-background-v2-1 the fresh R lane reviews routine facts and
actual available conditions mathematically, without native Mathlib lookup.
Five grouped judgments cover the complete node; concise located reasons are
sufficient for straightforward PASS. Prefer a complete artifact with coverage
rather than a separate model/tool roundtrip for every report row. Checkpoints
remain available. The exact supplement is hash-bound, kept with its original
review context/cost and consumed as node-local reference in nl02lean, never a
new assumption. Substantive gaps and source uncertainty cannot be waived.
