# Proof progress, diagnosis and reviewed repair

This protocol applies to the normal Yui controller. It is generic: no domain,
particular theorem, historical node ID or notation activates a repair. The
direct arm receives none of these Yui instructions or escalation tools.

## Before proof dispatch

After interface authoring and actual type checks, a separate clean reviewer
compares accepted NL0 with the complete proposed contract/plan. Check definitions,
domains, binders, quantifiers, hypothesis/conclusion direction, library parameter
and index meanings, coercions, nonvacuous domains, and every external E and full
target P. Read actual definitions in the pinned library instead of guessing from
notation. A well-typed encoding may still strengthen or weaken the mathematics.

The normal full/translation entry requires a complete actual independent,
hash-bound passing interface receipt before freezing proof packets. A failed
located review returns to the same serial interface-author responsibility with
its own prior proposal and actual findings. Changed types get new type checks
and a fresh independent review. An unchanged rejected proposal cannot trigger
another review. The reviewer does not see the author's repair history or old
judgments. This gate reduces early semantic mistakes; it does not replace the
final independent Audit B of the completed proof or guarantee judge accuracy.

## During a local proof

1. Repair ordinary compiler feedback in the worker. The 300-second native-call
   limit returns a retained failed candidate and applicable frozen ST020 advice;
   isolate the expensive application, repair it and recheck the unchanged target.
2. If the fixed packet appears inconsistent, use `report_proof_obstruction`.
   Supply the alleged layer (`local_proof`, `interface`, `source`, `unknown`), a
   concrete explanation, resolving JSON pointers in the current packet, and up
   to six actual own proof/helper candidate IDs. An assertion without a check
   can be escalated for diagnosis, but is never treated as a proved mismatch.
   No arbitrary path, sibling body, new premise or reference answer is accepted.
3. Separately track distinct check candidates and relevant library/note queries.
   Three normally completed turns with no new such action create a structured
   `NO_OBSERVABLE_PROGRESS` request instead of another identical continuation.
   Repeated identical candidates, index reads and repeated lookups do not reset
   this counter. Fresh failed checks count as evidence, not as proved progress.
   Provider backoff is not a completed idle turn. There is no total turn/call,
   token or case-time allowance in this policy.

A report returns no accepted proof. `REPAIR_REQUESTED`/`REPAIR_WAIT` retire this
case's current proof round, cancel its unstarted jobs and interrupt its remaining
model workers safely. Already checked bodies and all own attempts remain. Other
cases and their processes are untouched. In-flight native calls finish or reach
their existing native limit before shared inputs can change. Explicit user
cancellation has priority and remains `CANCELLED`, never an internal repair.

## Serial diagnosis and routing

The diagnostic session sees accepted source, current interface/plan, the located
packet and only that reporting worker's actual selected attempts. Worker claims
are allegations to verify. It is separate from the author, but its exposure to
the allegation is disclosed; it is not the later fresh interface reviewer.

| Actual diagnostic route | Controller action |
| --- | --- |
| `LOCAL_PROOF_REPAIR` | Retain own failed drafts, return located advice to that own obligation in a disclosed warm repair, and check new candidates under the unchanged interface. |
| `INTERFACE_REPAIR_REQUIRED` | Require paired quoted source/formal evidence; finish retiring the round, return to the interface author, type-check its changes and obtain fresh independent semantic review before new packets. |
| `SOURCE_REVIEW_REQUIRED` | Preserve a located source-review checkpoint. Do not change accepted NL0/A, add a hypothesis or weaken Lean silently. |
| `UNRESOLVED` | Preserve the diagnostic and explicit unresolved checkpoint; no guessed repair or fresh whole-paper replay. |

Repeated identical obligation/evidence after a located local-repair handoff
becomes `PROOF_REPAIR_STALLED`, not hundreds of new contexts or repeated reviews.
Changing only an explanation, turn count or timestamp is not new evidence.
Actual fresh attempts can continue without a fixed total attempt count.

Retained successful bodies are candidates, not inherited acceptance. Exact
program reuse requires a fresh current Lean check. After a definition repair,
reuse additionally requires the same accepted source, pins and own port boundary
plus the new actual independent interface receipt; recompile every reused body
under the new definitions. Old checks never certify the new program. Own failed
drafts are explicitly marked unaccepted and remain confined to their own node.

## Evidence and reporting

`proof-progress.json` separates last distinct action/check time and completed idle
turns from model/transport liveness. `proof-repair-request.json`, each diagnostic
stage, `repairs/` and all proof rounds are retained with actual usage. A successful
later round is selected by hash-bound `proof-selection.json`; previous failures
are not overwritten or counted as fresh successes. Assembly and Audit B read the
selected compiled round and still perform all existing independent gates.

An unresolved checkpoint is not a theorem FAIL or `MODEL_BUDGET_EXHAUSTED`.
Report the actual obstruction, execution health, retained work and next required
boundary. Owner monitoring remains a bounded observation; it must not inject
mathematical hints, manually edit the measured interface or restart live work.
