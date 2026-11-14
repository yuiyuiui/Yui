# Audit B: endpoint fidelity and checked Lean closure

For the optional [basis route](../../nl0/references/basis.md), this same Audit B
checks the conditional intermediate under the frozen basis interfaces. It is
followed by b2lean's fresh inspection of the actual `YuiClosed.P`, with only
original H and explicitly approved class 4 remaining. Its final receipt binds
the compiled standalone source and full actual signature/dependency closure;
this intermediate receipt must not be reported as unconditional completion.

The stage-two policy is `endpoint-fidelity-2` (Audit B schema version 2).
Its semantic objects are every original external theorem E and the complete
final target P. P includes its parameters, quantifiers, hypotheses, domains and
conclusion. Accepted NL0/Audit A remains the source authority; B does not repeat
unchanged natural-language proof checking.

## Normal final acceptance and deviation exception

The normal workflow uses `yui-frozen-interface-acceptance-1`. A complete independent
pre-proof review establishes source-to-type fidelity for every E and full P and
all definitions needed to interpret them. Final native inspection compares the
actual exported full types against that frozen contract, checks the exact defining
header/pins and semantic receipt, and validates standalone proof/dependency/trust
closure. This normal final gate is pure machine work: no additional final LLM is
called. It records inherited semantics, not a newly performed independent Audit B.

The actual E/P types include retained hypotheses and quantifiers. Text labels or
a source-hash check alone do not establish this gate. The original mathematical
review may be wrong; the machine establishes preservation of that reviewed encoding,
not correctness of the reviewer's natural-language judgment.

Only complete proof-integrity success plus genuine endpoint/definition drift may
open the exceptional independent B-final review below. A faithful result then has
`AUDIT-B-CONDITIONAL`, a freeze-deviation warning and an explicit harness-defect
report. Invalid native evidence, incomplete dependencies or changed provenance
cannot be overridden semantically. Nonfaithful/unverified results wait for the
three explicit user choices in [proof repair](proof-repair.md); accepting a different
result does not complete the original target. Semantic receipts must use the current schema.
Explicitly nonindependent/self-review records remain readable development checks;
they cannot grant whole-workflow Audit B acceptance. The same qualification rule
applies to supplied Audit A authority and incremental producer/cut reviews.

## Author correspondence explanations

During interface authoring, provide `endpoint_correspondence`, keyed by every
E ID and P. Each entry is `{mode: direct|equivalent, explanation: string}`.
Keep it short and useful; do not restate the entire proof or manufacture a
line-by-line formalization commentary:

- **Direct:** identify the corresponding variables, hypotheses and assertion.
  One sentence is enough when the translation is immediate.
- **Equivalent:** explain the mathematical identification or reformulation,
  why it works in both directions and which existing conditions it uses.
  Point to relevant definitions or checked conversions when needed.

For example, expressing invariance under a finite basis of operators can encode
invariance under their linear span: explain the spanning property and closure
of a subspace under linear combinations. The review must establish those facts
for the actual source algebra/action; the word “equivalent” alone is insufficient.

The postprocessing author carries these notes into each E/P entry in
`mapping.json`, checks them against the actual export and completes missing
notes for older frozen contracts. It must not change frozen proof statements
or bodies merely to improve a note. An explanation is an author's claim, not
an Audit B verdict or a formal proof.

## Semantic responsibility before freeze or at explicit B-final

Read the explanation together with the original source statement and actual
elaborated Lean type. Follow the definitions needed to interpret the endpoint,
including structure fields that might hide extra assumptions. Check each E/P
row, then these four global checks:

1. `endpoint_inventory_and_scope`: all original E statements and P are covered;
   the source version, reviewer scope and inherited qualifications are explicit.
2. `external_statement_fidelity`: each external assumption has the source's
   complete mathematical meaning, including conditions and quantifiers. With
   no external inputs, record that fact.
3. `complete_target_and_representations`: the entire target theorem has the
   same meaning, including every hypothesis. Validate the explanation of each
   direct or equivalent encoding and relevant edge cases.
4. `kernel_closure_and_trust`: the actual exported proof compiled, all required
   producers and intermediate library ports were discharged, and the checked
   root has only the declared external assumptions and permitted foundations.

Equivalent formulations are allowed. Do not reject a faithful encoding because
it lacks a particular Mathlib type/name, a separate object for every NL0
D node, or a duplicate formal representation. A mathematical source-to-code
identification can be checked semantically without constructing an unnecessary
second model. If the implementation actually crosses two different Lean
representations, the required conversion must occur in checked Lean code.
Unexplained equivalence, stronger assumptions, missing hypotheses, changed
domains or hidden target assumptions remain defects.

Do not accept an explanation on trust or copy the author's conclusion into the
review. Record PASS/FAIL/UNVERIFIED with specific findings and source/type/note
locations. A compiler pass cannot substitute for this independent judgment.

## Freely available Mathlib

All proved results in the pinned Mathlib environment are available in stage
two. Do not compare their names, counts or node-by-node uses with the NL0 M
inventory. There is no per-M semantic row, imported-proof whitelist,
`calculation_links` ledger, or separate review of implementation N/D nodes.
Definitions are examined when they determine endpoint meaning, not for an
exact inventory match. Notes from Audit A are optional local guidance, not
permissions to use a library theorem.

New interfaces normally use Mathlib directly. An older or deliberately
conditional interface can retain M ports; `library_terms` supplies an actual
Lean proof for each such port at assembly. These are discharge proofs, not a
library correspondence inventory. They cannot remain unproved assumptions of
the final export. New external axioms or stronger project hypotheses still
require returning to the affected source boundary.

## Mechanical evidence and limits

### Compact review materials

The semantic reviewer reads the separately versioned
`yui-audit-b-review-view-1` in `review-packet.json`. Start at `/scope` and
`/mechanical_summary`, then examine each `/endpoints/<ID>` source, actual
inspected type and author correspondence. P retains the complete original
target, parameters and hypotheses. The view is a deterministic Python extraction,
not an LLM summary or mathematical judgment. It never substitutes a declared
expected type for the actual inspected type.

`/documents` identifies hash-bound `source-context.json`, `source-original.txt`
and actual `Proof.lean`. Read relevant original and Lean definitions there,
including hidden structure fields, when needed to interpret an endpoint.
Complete raw compiler, elaboration and dependency records stay in the machine
archive; they are not default reviewer inputs. A mechanical summary reports
actual checks and exceptions, without populating a semantic PASS. The full
dependency inspection remains a program responsibility.

Use `read_task_input` JSON pointers, not guessed fixed line positions. Large
containers expose keys and large strings expose `next_offset`. Text reads
resume with `next_start` and `next_column`. Serialized read results are at most
32 KiB; follow `has_more` until the needed statement is complete. This pagination
limit is not a task time/token/call budget. Unknown calls or modified feedback
remain rejected with a specific local protocol fault, not a retryable HTTP 502.

### Explicit reuse of completed native evidence

`audit_b.py reuse-review <new-directory> --original <old-audit-directory>`
prepares a new semantic review without rebuilding or changing Lean. It validates
every original input and snapshot, the original native artifacts/output, source
and accepted-A authority, environment pins, and the exact historical tool
snapshots. The new view and current reviewer runtime are separately bound in
`review-reuse.json`; the normal current-build tool check is not disabled.
Changed or incomplete evidence blocks reuse. Preserve the original failure.

The new independent reviewer receives no previous B verdict, reviewer history,
owner reasoning or other-case material. The receipt discloses inherited native
checks and a new semantic review; it cannot claim fresh compilation, an unaided
cold whole-workflow success or measured acceleration. Changing proofs or source
requires the appropriate new checks, rather than this review-only path.

`audit_b.py prepare/build/check` binds the source, accepted A, contract, plan,
proofs, tool versions and environment hashes. Build compiles standalone
`Proof.lean` before adding inspection. It checks E/P against their declared
encoded types, modulo definitional equality and bijective universe renaming.
It does not prove equivalence between natural-language text and Lean.
Distinct universes must not be collapsed; changed types or hypotheses must not
be normalized away. Source fidelity is established by the bound pre-proof independent review, or an actual exceptional B-final review; this native comparison does not establish it anew.

Inspection follows the actual `AuditBExport.P` closure. No `sorry`, unproved
local axiom/opaque substitute or undeclared foundation may be introduced.
Local bodies still compile against their own task inputs and the pinned
library; every required producer must exist. Assembly, inspection and semantic
review have separate recorded outcomes.

Use a current version-2 receipt. Start a new bound audit when policy, source,
code or evidence changes. Pending templates
never pass. A whole accepted source plus complete native gates and its bound semantic
authority yields `AUDIT-B-PASSED`; a fragment yields at most the explicitly
scoped development verdict. A whole source with an actual conditional Audit A
can yield `AUDIT-B-CONDITIONAL` after all the same native and semantic checks.
It retains the exact source warnings and never upgrades them to full PASS.
Neither proves external publications in Lean or
establishes formalizer speedup. Preserve failures and report actual costs.
