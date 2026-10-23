# NL0 data contract, version 2

New graphs/specifications use v2 and audit records use v3. The existing v1
Koch/BO cases are historical snapshots and have not been reaccepted. Reading
them requires `--legacy`; current default checks reject them. Historical
receipt validity is labeled `LEGACY-*` and `current_standard_receipt_valid`
remains false. Do not mechanically bump a version number to migrate a proof.
Apply [self-containment](self-containment.md) to the actual mathematical text.

## Authority and semantics

`spec.json` freezes the original full theorem, the conclusion under its declared
parameters/hypotheses, the exact H list, global definition pairs, logic policy,
source-input hashes, and Lean/mathlib pins. A human must confirm that this
specification matches the original problem; string equality cannot establish
semantic fidelity. `nl0.json` references this spec by its SHA256 and duplicates
none of its definitions or H statements. One separate spec is required per
target. Multiple-target decomposition is outside version 2.

Read a derived proposition as a theorem under the original parameters and the
H nodes actually used on its derivation path. All additional free variables are
locally quantified in its statement; there are no ambient undeclared claims.
An unused original H is allowed and reported; do not silently strengthen or
weaken the frozen theorem. E/M results retain their general signatures; apply
them through explicit bindings and hypothesis checks in the inference.

Graph vertices are propositions and inferences. Edges are generated only as
`input proposition -> inference -> output proposition`. An inference requires
all inputs. List order is presentation only: a dependency may occur later in
the JSON array, provided the graph admits a topological order. Actual circular
dependencies, unknown IDs, and disconnected retained branches fail.

## Specification fields

Use [the authoring template](../templates/authoring.md) and the complete
[model-visible submission example](../templates/submission-example.md). The
example explains metadata placeholders and local-witness accounting; it is not
a benchmark or proof certification. Required top-level spec fields are:

- `format_version: 2`, `case_id`, `full_target`, `conclusion` (nonempty strings);
- `parameters`: records `{symbol, type}`; parameter symbols reserve global names;
- `hypotheses`: records `{id: Hddd, statement, origin}` extracted before authoring;
- `definitions`: records `{id: Dddd, symbol, definition, type, depends_on,
  requires, binders, objects}`. Each symbol has exactly one global meaning. `depends_on` lists
  earlier/resolvable D IDs and is acyclic. `requires` lists proved H/N IDs that
  must already be available whenever the definition is used;
- `logic`: `{classical: boolean, rules: [names], calculations: [nonempty descriptions],
  primitives: [{symbol, type, meaning}]}`. Primitives declare fixed logical
  language/objects, not free analysis theorems;
- `pins`: `{lean_version, mathlib_commit, mathlib_root}`; the root is a local
  locator, the version/commit are scientific identifiers;
- `inputs`: evidence records `{path, sha256}` for the original problem/proof.

The exact machine identifiers permitted in `logic.rules` and inference `rules`
are `direct`, `modus_ponens`, `implication_introduction`, `negation_introduction`,
`contradiction_classical`, `case_elimination`, `forall_introduction`,
`exists_elimination`, and `natural_induction`. Describe algebra/analysis in the
actual proof text; it is not a new trusted logical rule. These identifiers
describe proof packaging, not a substitute for establishing the implication.

Definitions may be globally visible but guarded. Example: “K is the unique
fixed curve from N008” requires N008 before K is used. N008 itself must state
existence using the previously defined space/operator, without assuming K.
Proof prerequisites must be direct inference inputs in v2;
the output being proved cannot discharge its own definition prerequisite.
Definition prerequisites of input/output statements are checked too.

## Proposition fields

Every proposition has `id`, `kind`, the complete `statement`, `definitions`
(D IDs), `binders`, and `objects`:

- `binders`: `{symbol, type}` records for statement-bound variables. These do
  not introduce free variables in a consuming R. Register actual nested scope
  in the statement; alpha-rename to avoid global shadowing.
- `objects`: distinct names of mathematical objects actually used in the
  statement, from frozen parameters/primitives, referenced D closure or these
  binders. A D also has these fields for its defining expression.

These are inventories, not a parser-generated list. Audit A must find omitted
objects by reading actual prose/formulas. Export all formulas and conditions;
another N ID or an original equation number cannot replace their content.

| kind | ID | Producer | Additional fields |
|---|---|---|---|
| `hypothesis` | Hddd | none | exactly matches frozen H statement |
| `mathlib` | Mddd | none | `source` record below |
| `external` | Eddd | none | `source` record below |
| `internal` | Nddd | exactly one | `origin` locating source or explaining added bridge |
| `target` | P | exactly one | exact frozen `conclusion` |

A source record contains `statement` (exact NL restatement), `evidence` (file
hashes), and `hypotheses` (complete applicability obligations, not their proof).
M additionally has `declaration`, `module`, `mathlib_commit`, `source_path`,
`source_sha256`, `signature` (complete Lean output), and `declaration_kind` equal
to `theorem` or `proved_instance`. A definition/opaque constant is not a proved
source proposition. Library definitions belong in D. A named M's official
library dependencies need not be copied into the project graph; pin the library
and inspect relevant axioms. Do not introduce project results as library M.
M evidence includes the successful version-1 report from `probe_mathlib.py`,
with the same ID, declaration, full signature, source bytes and toolchain pins.
In the clean Yui NL0 carrier, `probe_library` produces this evidence and the
submission adapter binds exact signature/source metadata from the successful
probe matching the selected M ID, declaration and dotted module. Those metadata
fields may be omitted from that tool's submitted JSON; canonical graph files
still contain them in full. No unprobed source is filled from model memory.
The adapter does not rewrite mathematical statements, hypotheses, definitions,
binders or arguments. Their fidelity remains the author's and auditor's work.
To avoid retranscribing mandatory duplicate strings, its tool input may omit
an H node's `statement` (copied from the same artifact's `spec.hypotheses`),
P's `statement` (copied from `spec.conclusion`), or an E/M `source.statement`
(copied from that proposition's primary `statement`). This is serialization of
one authoritative text, not a second premise or an inferred theorem. Canonical
files contain all fields. Conflicting supplied duplicates are rejected with
both texts shown; they are never silently overwritten. The actual external
`source_statement` and the probed Lean signature remain separate source-fidelity
evidence that Audit A must compare to the primary project restatement.
Use a fresh probe output directory for a new source-query version. The helper
refuses to overwrite existing evidence; `--replace-existing` deliberately
archives previous outputs and revokes the old active receipt before rerunning.
The checker verifies this record binding; it does not authenticate a fabricated
execution transcript. Audit A still reads the actual source and checks meaning.

E additionally has nonempty strings `author`, `title`, `version`, `identifier`,
`locator`, `notation_map`, `errata`, `source_kind`, `origin`, `retrieved_at`,
`source_statement`, `context`, `qualification`, and `version_check`, plus
`primary_evidence`: a nonempty list of hashed evidence records also present in
`evidence`. `source_statement` records the actual source theorem and its full
conditions, separately from the project's restatement. `version_check` states
the check date, scope, findings and effect; `qualification` explains source
category and proved-result eligibility. Read the full
[external-theorem review standard](external-theorems.md).
A DOI/URL alone is insufficient. Include an
accessible local primary document and precise excerpt/location evidence. Do not call
the target work's unproved internal lemma an imported E. Existing internally
proved modules need a separate expanded graph or a versioned proof handoff;
version 2 does not silently certify an opaque module.

Every retained non-H proposition must be in P's backward dependency closure.
Every frozen H is present as an initial graph node, including an unused H.
Report unused H rather than removing it or changing the original statement.

## Inference fields

Required fields: `id: Rddd`, `inputs` (unique proposition IDs), `output` (one
N/P ID), `definitions` (direct D references), `rules` (permitted logic-rule
names), `locals`, `argument`, and `applications`.

- `locals`: `{symbol, type, scope}` records. Scope identifies a binding inside
  this inference; names cannot shadow globals. Two bindings in different
  scopes/nodes may use the same spelling. Bound variables of source theorems
  can be alpha-renamed and instantiated. Audit actual binding/freshness.
  In v2 also require `start`, `end` (inclusive S IDs), `kind` (`arbitrary`,
  `definition`, or `witness`), `declaration` (full introduction), `from_inputs`,
  `from_local` (prior F IDs) and `objects` (already available objects used to
  introduce this one). A witness must have an input/local existence basis.
  The checker verifies declared availability/order, not the existence claim's
  semantics. Source-bound variables need a legitimate local instantiation.
- `argument`: ordered records `{id: Sddd, text, uses, uses_local, objects,
  produces, introduces, discharges}`. S IDs are inference-local and unique. `uses`
  lists direct graph inputs used at this point. Local facts established earlier
  in the prose do not become graph inputs. The union of `uses` must equal
  `inputs`. A citation's presence is not semantic evidence that it was used.
  `uses_local` lists only earlier F IDs; `objects` lists the actually used
  global/active local objects. `produces` holds complete local facts
  `{id: Fddd, statement, binders, objects, assumptions}`; assumptions lists remaining
  local L IDs on which the fact depends. A local fact cannot be used before
  its production or outside its assumption/object scope. A paragraph cannot
  cite its newly produced F as a previous premise. Formulas to be reused by a
  different R must appear in the exported proposition, not only in `produces`.
- `introduces`/`discharges`: lists of inference-local assumption IDs (e.g.
  `L1`). Temporary assumptions are never proposition vertices. Every introduced
  ID is unique in this inference and must be discharged once, no earlier than
  introduction. These lists account for prose; Audit A checks the actual
  formula, scope, and chosen rule. A correctly closed implication may retain
  the assumption in its antecedent. Deleting the ID cannot justify an output.
- `applications`: records covering every directly used E/M input, with
  `{input, at: Sddd, bindings, hypothesis_checks}`. The S paragraph must list
  this input in `uses`; only local facts available before that paragraph may
  supply application conditions. E applications additionally require
  an inference-local unique `id: Addd`; different actual uses of the same E
  need separate IDs and records. M may also use explicit A IDs for repeated
  instances; a legacy M without `id` uses its input ID as the unique key.
  `hypothesis_checks` has one nonempty
  explanation for each corresponding source obligation. A hypothesis needs an
  actual argument from inputs/H/local proved facts; filling a string is only
  an accounting check. Prove substantive normalization bridges as N nodes.

Input-free R nodes are permitted only for explicitly shown calculations or
logical/definitional consequences. They are audited proofs, not a fourth kind
of trusted source. Transitive inputs need not be repeated unless used directly.

## Audit record

`audit-a.json` contains `format_version`, `graph_sha256`, `spec_sha256`,
`reviewer` (`identity`, `mode`, `independent`, `disclosure`), `target_review`,
`definition_reviews`, `source_reviews`, and `inference_reviews`.

Each review contains `verdict: PASS|FAIL|UNVERIFIED`, substantive `notes`, and
hashed `evidence`. Inference reviews contain ten separate check review objects:
`inputs`, `argument`, `dependency_accounting`, `output`, `scope`, `applicability`,
`statement_closure`, `object_closure`, `dependency_closure`, `packet_replay`.
Each check has `{verdict, notes, evidence, locations}`. `locations` contains
JSON pointers resolving inside that R's actual packet, such as
`/inputs/0/statement` or `/inference/argument/1/text`. PASS requires at least
one actual inspected location; a boolean/enum alone is insufficient.
Every D, every E/M source, every R, and the target must be covered exactly once.
Spec input hashes and source evidence are read back; malformed/duplicate JSON
keys, missing files, changed bytes, failed verdicts, and stale audit hashes fail.

Use audit `format_version: 3` for all new records. Audit v1/v2 are readable
only with historical graph v1 and `--legacy`; they cannot satisfy this contract.
Each E source review additionally has `citation_checks`, mapping exactly
`literature_identity`, `result_location`, `statement_fidelity`,
`context_completeness`, `version_and_eligibility` to separate ordinary review
objects `{verdict, notes, evidence}`.
Each version-3 inference review additionally has `external_applications`,
mapping exactly its E application A IDs to records
`{input, verdict, notes, evidence, bindings_review, hypothesis_reviews,
conclusion_review, bridges}`. `input` must match A's E; each nested review
has `{verdict, notes, evidence}`; the ordered `hypothesis_reviews` list matches
all source obligations one for one. `bridges` lists N nodes already in R's
direct input list. A bridge string is not a proof of that bridge.

Each inference review also has `replay: {packet_sha256, mode, carrier,
prior_exposure, read_materials}`. Modes are `unperformed`,
`same_context_diagnostic`, and `fresh_packet_only`. A passing replay/overall
inference requires the actual fresh carrier, empty prior proof exposure, and
`read_materials` equal to `["packet:<hash>"]` for mathematical input. Skill
instructions supply the procedure, not additional mathematics. The hash must
match the regenerated packet. Keep traces as evidence; metadata cannot
authenticate a claimed identity or prove truthful isolation.

`audit-template` creates only UNVERIFIED reviews, empty check locations and an
unperformed replay. It refuses to overwrite an existing output. It does not
inherit author notes or old verdicts. `inspect-audit` can inspect this pending
record; `check --audit` rejects it. Each PASS must come from actual review.

`check --audit` accepts only fully passing records. `inspect-audit --audit`
also validates the completeness and evidence of FAIL/UNVERIFIED records and
returns their unresolved review paths; success of inspection is not proof
acceptance. Overall PASS with a failed child review never passes acceptance.

Mode `same_context_self_audit` requires `independent: false`. If claiming an
independent review, disclose its actual carrier and input boundary; this file
does not authenticate identity or prove independence.

## Local packet

The v2 packet contains `contract_version`, `case_id`, spec/graph hashes,
parameters, fixed logic, pins, expanded definitions, complete input/output
ports, the current inference, a warning, and `packet_sha256`. Source ports keep
applicability obligations and M signatures; primary-document verification is
separate. Producer arguments, original-proof locations, source proof text,
non-input H and extra ancestor/guard statements are not supplied. Guards must
already be direct inputs. The packet intentionally omits the global full target
so that its unstated premises cannot become an ambient local hypothesis.

Its digest is SHA256 of UTF-8 canonical JSON (`sort_keys=True`,
`ensure_ascii=False`, `separators=(",", ":")`) excluding `packet_sha256`.
It is independent of audit-verdict fields, avoiding a circular receipt hash.
Packets are generated views and never a second editable proof authority.

## Mechanical boundaries

The checker validates declared objects, the frozen contract, graph closure,
notation-name metadata, citation parity, local-assumption accounting, guarded
definition availability, and hash-bound audit coverage. It verifies source
checkout/file hashes, not the truth of a source restatement. The printed
signature must be obtained from a successful pinned Lean probe and compared by
the auditor; an arbitrary string called `signature` is not verification.

The checker cannot establish that a natural-language formula is well typed,
that two spellings have the same mathematical meaning, that a hidden theorem
was not used, that a local witness did not escape the prose, or that an argument
is valid. Those are explicit Audit A obligations. Neither a JSON PASS nor a
fabricated complete audit receipt is a mathematical certificate.
Numbered-reference diagnostics reject common opaque references, not every
possible paraphrase or hidden import. Behavioral tests must actually ask an
auditor to review unseen controls; manually prefilled FAIL records only test
receipt rejection and must be reported as such.
