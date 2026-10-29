# Shared-lemma extraction as a local NL0 revision

## Scope and position

Apply this procedure at the start of **NL0-to-Lean translation**, before final
interface/planning freeze or worker-packet generation. It is not an extra
requirement for a task that requests NL0 alone. The input is an existing,
versioned NL0, not an invitation to reconstruct its proof.

The operation is proof factoring: move an already supplied local derivation
into one shared N/R pair and replace its occurrences by explicit applications.
Do not rewrite the whole NL0, regenerate its prose, reprove unchanged results,
or seek a stronger/general theorem for speculative future reuse. Reading the
existing graph to locate candidates is not a new proof-construction task.
If an existing N already exports the needed fact, reuse that node directly.

Use [the revision record](../templates/source-refactoring.md). Preserve the
original package and audit as immutable evidence. Write a revised package in
a new directory; retain existing IDs and keep the revision identity in the
sidecar record. Generated Markdown/diagrams are views, never patch authorities.

## 1. Locate and qualify candidates without reconstructing NL0

Start with existing node statements, direct inputs, definitions and any
available index. Locate repeated subarguments using their mathematical role,
objects, formulas or operation names; then inspect the actual candidate spans
and the local context they need. Do not commission a new proof or a full prose
summary for every node as a discovery method. Text similarity is only a lead.

For each proposed lemma record:

- The complete mathematical statement, all parameters/conditions and proposed
  direct input IDs, together with exact old graph pointers or paragraph spans.
- The existing derivation to reuse and every occurrence that will consume it.
  The derivation must actually supply the proposed statement; a summary label
  or a theorem believed true from memory is insufficient.
- Identify the baseline revision/old paragraph IDs separately from the current
  new producer. A new N's origin label must state the historical/current
  distinction; a bare old R number is ambiguous after consumer editing.
- The expected avoided repeated work. An occurrence count is not measured
  formalization cost and does not by itself establish a speed benefit.
- The scope at each occurrence, including bound variables, temporary
  assumptions, definition guards and local facts established before the span.

Prefer a statement already justified at the cuts. Do not generalize its domain,
change representations, weaken conditions or introduce new mathematics merely
to make more occurrences match. If the proposed derivation needs an earlier
local calculation, include that calculation with its justified inputs. Never
declare an unexported local fact to be an available graph input.

Temporary assumptions stay closed in an implication or other complete
proposition; they cannot become H roots. An extraction that moves a witness,
choice, definition or binder across a scope boundary needs an explicit account
of the values and properties used afterwards. If that account cannot be made
locally and clearly, leave the original argument in place.

## 2. Write the patch boundary before editing

Prepare an edit allowlist for one candidate or one coherent batch:

| Part | Allowed edit |
| --- | --- |
| New shared theorem | One fresh N and its R producer, with a complete statement and derivation from existing permitted inputs. |
| Actual consumers | Replace only the located repeated proof spans by a complete application; adjust direct inputs, citations and application accounting accordingly. |
| Necessary local bookkeeping | Update the directly affected binder/reference accounting and generated views. Record every such edit explicitly. |
| Everything else | Preserve the existing record content; do not reorder or renumber it as a cleanup. |

Keep the entire frozen specification unchanged: target P, original H, parameter
domains, global definitions/notation, logic, pins and E/M source inventories and
statements. Preserve all existing N/P statements and every unmodified argument
span. New sources, changed hypotheses, new global definitions, removed existing
nodes, or a changed old output are outside this fast factoring operation.

Copy an existing derivation rather than writing a new proof route. The new
producer may use only its declared inputs, global definitions and legitimate
local derivations. It cannot depend on a consumer output or its descendants.
Do not split each consumer into additional source nodes around the shared fact.

Each consumer application must state the parameter substitution, which inputs
or local proved facts discharge each condition, and the exact conclusion used.
Remove a former direct input only if the remaining argument no longer uses it;
retain it when it still has a direct role. A shared theorem is never ambient.

If an edit escapes the allowlist, return that candidate to the shortlist or
leave it unextracted. A source defect goes through the existing gap procedure;
do not turn a reuse optimization into a repair or a new research route.

## 3. Check structural preservation globally, reasoning locally

Compare canonical JSON records by stable IDs, not only rendered text or changed
line numbers. Record before/after hashes and the actual changed fields/spans.
Reject any unexplained diff. Check these global mechanical invariants:

- The frozen specification and protected records are unchanged.
- All IDs/references resolve; definitions and guards remain available; there
  is no cycle or unsupported initial node; every N/P still has one producer.
- Every retained node remains in P's dependency closure. Reject the candidate
  if it would require deleting or reorganizing unrelated nodes to restore this.
- All consumers declare their actual inputs and remain self-contained. Only
  the explicit allowlisted nodes/fields have changed.

Run the existing `../scripts/nl0.py check` on the revised graph and specification.
Rechecking graph metadata across the package is allowed and inexpensive relative
to rereading every mathematical proof. It does not require a new LLM proof of
every node, and it does not establish the semantics of a substitution.

Distinguish **review impact** from **dependency status**. The new producer and
edited application boundaries need new mathematical review. An unchanged
downstream proof whose input statements and conventions are unchanged need not
be reconstructed merely because its ancestors have a new producer. Its final
acceptance nevertheless depends on the replacement producer being accepted.
Until that happens, affected descendants are pending, not newly accepted.

## 4. Incremental Audit A: review the new proof and the substitution cuts

This is an incremental review procedure under Audit A's mathematical
obligations, not permission to weaken source verification or invent a fresh
packet replay. The version-bound receipt limitation below is part of the rule.

First inspect the baseline audit and its evidence bindings. Reuse a judgment
only for the exact previously reviewed content, context and evidence. Carry
FAIL, UNVERIFIED, inaccessible sources and disclosure limits forward. A source
file hash proves byte identity, not that an auditor ever inspected the theorem.
An unaudited baseline cannot acquire whole-proof acceptance through extraction.

Review the **new N/R in full**: complete statement, exact inputs, argument,
dependency accounting, scopes, guards and E/M applications, and the normal
fresh packet-only replay requirement. The extracted proof may be copied, but
its new closed interface and context must actually be checked.

For **each changed consumer**, review a substitution cut rather than rewriting
or replaying its entire old proof by default:

1. Compare the old derived conclusion at the cut with the instantiated shared
   result, including all conditions, quantifiers and semantic conventions.
2. Check that every condition of the shared theorem follows from that consumer's
   declared inputs or explicit in-scope local derivations, without extra facts.
3. Check the interface to the untouched continuation: every subsequently used
   proposition, object, value and scope remains available with the same meaning.
   Equal output text alone cannot establish preservation of a selected witness.
4. Verify the changed direct-input/citation/application accounting. Reuse source
   identity evidence only when unchanged; check every new source application.
5. Bind the untouched remainder to its old reviewed bytes and old review
   evidence. Record exactly which old checks are inherited and which new checks
   cover the patch. Do not relabel this comparison as a new fresh whole-R replay.

If those boundaries do not justify inheritance, mark that candidate
`DEFERRED_NOT_LOCAL` and keep the baseline argument. Do not automatically expand
to a full-case audit. A separately requested broader review may inspect the
specific unresolved node, but is not part of this fast extraction.

Unchanged target/source/definition reviews and proof regions need no new
mathematical re-review when their audited content, applicable context and
evidence are unchanged. Do not reopen source searches solely because a global
graph hash changed. Changes or failures in their evidence invalidate reuse.

The result is a chain: baseline audit + exact revision + actual new reviews.
It is not a copied PASS with an updated graph hash. Record actual reviewer
exposure; old-review access is appropriate for delta review and cannot be called
an independent fresh packet-only review. This procedure authorizes no additional
agent or external-service dispatch.

## 5. Seal or leave the candidate unextracted

Seal only after the allowlist/diff and graph checks pass and the scoped
mathematical review is complete. Keep original and revised manifests, patch,
location map, old/new evidence, pending findings and measured preparation cost.
Stage all candidate edits transactionally; a failed candidate must not replace
the accepted baseline. Do not launch formalization workers for an unaccepted
source revision or reuse task packets bound to the old graph.

Then finalize and freeze typed interfaces, shared Lean ports and local plans;
only afterwards generate worker packets. Shared Lean interface discovery may
use this preparation pass, but must not silently mutate the sealed NL0 later.
No extraction is a valid outcome; do not manufacture shared lemmas to satisfy
the workflow. The work is bounded by the chosen proof regions and patch size,
not a universal minute count. Longer time alone is not a mathematical gap.

## Executable acceptance and review responsibilities

The unchanged parent checker still binds ordinary V2 audit v4 to the complete
graph. `scripts/source_preparation.py` adds a separate incremental record;
it never copies old PASS fields into a forged fresh whole-graph audit.
Audit B and `workflow.py` both revalidate that record and all underlying evidence.
See [commands and the patch contract](integrated-workflow.md).

The initial executable scope is current-v2 source and nonoverlapping consumer
paragraph substitutions. Old proposition records/specification, unlisted R
records, untouched paragraphs and local fact/assumption lifetimes are protected.
Consumer source-application changes can remove obsolete uses, not introduce new
external uses. A broader refactor is deferred rather than widening this operation.
Multiple proposed edits to one consumer must first be merged into one coherent
candidate or left unextracted. Legacy test copies remain development evidence.

Separate three responsibilities:

- A producer reviewer sees only the complete new per-R packet and audits its
  conditional mathematics under ordinary Audit A, including actual fresh replay.
  Do not ask that packet to establish whole-graph acceptance or old-copy provenance.
- A substitution reviewer sees paired before/after consumers, the proposed shared
  statement, original derivations and explicit cut contract. `old_derivation`
  names THIS consumer's replaced proof; `producer_source_derivation` names the
  one original proof used to export the shared lemma. Its supplier may be a
  different consumer with a different final goal. Compare the common intermediate
  conclusion, not equality of those final goals. Check existing-proof
  factoring, each condition, exact supplied conclusion, continuation and accounting.
  This is delta review with baseline access, not fresh whole-consumer replay.
- Python checks canonical fanout, edit scope, graph validity, immutable evidence,
  the exact coverage partition and inherited acceptance/qualifications. It does
  not judge natural-language mathematics or authenticate a dishonest reviewer.

Internal N applications are direct inputs, paragraph citations and explicit prose;
the parent's `applications` source records remain E/M-only. Do not invent an N
source-application record to satisfy a reviewer. A prose citation without a real
substitution is not successful factoring. Derivation labels and fanout guesses
from a model are leads, not canonical graph facts.

Each cut review binds the exact supplied packet hash. Retain the binding from
the generated template and verify it during acceptance. Reusing an actual old
review after a record-only change requires identical canonical mathematics and
byte-identical actual reviewed packets; preserve its verdicts, notes, evidence
and original cost, and disclose that no new mathematical review occurred.

`INCREMENTAL-AUDIT-A-PASSED` requires a passing current baseline plus all actual
new producer/cut reviews. Missing/failed baseline checks remain inherited and
yield development-only local review. Every later consumer acceptance still
depends on the new producer; unchanged input statements and context permit
inheriting the old conditional argument without rereading it mathematically.
No fixed completion-time threshold makes a candidate worthwhile or incorrect.
