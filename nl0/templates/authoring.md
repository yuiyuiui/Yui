# NL0 construction and tool template

Use [Audit A's shared criteria](../references/audit-a.md#shared-mathematical-acceptance-requirements)
as the mathematical authority. This template explains data/tool construction;
it is not a parallel acceptance policy. Read the [schema](../references/nl0-format.md),
[construction guide](../references/nl0-authoring.md), and the complete neutral
[submission](submission-example.md), [source application](source-application-example.md)
and [quantified implication](quantified-implication-example.md) examples.
These examples show format and derivations, not certified benchmark answers.

The complete [guarded-definition example](guarded-definition-example.md) shows
how to organize a target that includes an object's existence and a property
of that object. For a real a let Q(r) mean r=a. R001 first proves N001, unique
existence of a Q witness, without using w. D002 then defines w as that unique
witness with requires=[N001]. R002 takes N001 as a direct input and proves the
full target: unique existence and w=a. Listing D002 in the global spec does
not let R001 use it before its guard. Do not hide an unproved guard in a
restricted domain when the frozen target requires a statement on the full
original domain. This pattern adds no new assumption or mathematical source.

## Construct one coherent candidate

1. For `target` and `definitions`, extract the original H, ambient parameters
   and global typed definitions. Preserve the original source locations. Do
   not change a parameter's mathematical kind while fixing its metadata.
2. For `statement_closure`, design N/R interfaces from what their
   consumers actually need. Put the complete formulas, quantified conditions
   and space identifications into the exported statement, not only its body.
3. For `dependency_closure` and `argument`, construct
   each proof unit alongside its premises. List exact source inputs or display
   a prior local derivation for every substantive fact beyond the fixed
   calculations. Split when local context changes; avoid a giant S whose
   changing objects must later be repaired one at a time.
4. For `sources` and `applicability`, inspect each selected native/primary
   source, preserve its complete contract and ground each instantiated premise.
   A signature lookup or a sentence claiming a hypothesis is true is not proof
   of that hypothesis. Reuse an adequate proved source rather than re-proving
   it; a project-specific bridge still requires its displayed derivation.
5. For object declarations and local scopes under dependency_closure, introduce objects and conditional premises
   at their actual first use. Keep witness bases and local F dependencies
   correct. Preserve exact coefficients and ranges when copying calculations.
6. Run check_draft, correct its actual located records, inspect every own
   conditional packet, and report readiness below. The independent auditor
   applies the same criteria after definitive submission.

## Canonical data shapes

Submit {spec,graph} using the schema, or preserve an own draft with
{base_candidate:N,patches:[...]}. The controller binds identity, input/pin
hashes, fixed language and exact native metadata; it does not rewrite proof
content. Use read_draft with a narrow pointer after an edit rejection.
Unique existing @ID/@symbol selectors work for own-stage reads/patches;
inserting array elements still uses numeric indices or /-. Audit evidence
uses standard JSON pointers instead of this selector extension.

For multiline changes prefer read_draft(candidate=N,pointer="/graph/inferences/@R001/argument/@S001/text",
start_line=1,end_line=20). It returns the actual numbered lines, total_lines
and complete text_sha256. Use an edit with exactly
{op:"replace_lines",path:"/graph/inferences/@R001/argument/@S001/text",start_line:4,end_line:5,
text:"replacement including its intended line endings",text_sha256:"the returned hash"}.
Ranges are positive and inclusive. Unselected text and line endings are
preserved; stale hashes are rejected. Include a line terminator when a
nonempty replacement precedes retained lines. Empty text deletes the range.
All ordinary validation and later Audit A still apply.
For reads only, an end beyond the string returns its remaining existing lines
and the actual range; the start must exist and at most 250 lines may be
requested. Line edits still reject any out-of-range end and never clamp it.

Each D has type, full definition, binders, used objects, D dependencies and
proved guards. Each H/E/M/N/P has full statement, definitions, binders, objects
and appropriate source/origin fields. Each R has direct inputs, one output,
definitions, rules, locals, argument and real source applications. Each S has
actual text, uses, earlier uses_local, objects, complete produces F statements,
and assumption introductions/discharges. Each source application has input,
at:Sddd, bindings and actual hypothesis_checks. See the linked schema/examples
for exact names. source_uses can serialize one already selected M/E into the
R.inputs, S.uses and application together; supply the actual mathematical
bindings and grounds yourself.

When a declared frozen task already supplies a complete adequate definition,
D.definition may be {from_task:"input ID",start_line:N,end_line:M}, just like
S.text. The same form is available for spec.hypotheses[i].statement when the
selected passage states a complete original GIVEN. Keep its origin; never
promote a desired conclusion or proof claim to H. An H referring to the
target/problem for its missing content is not standalone.
The controller copies those exact lines to an ordinary canonical
string and records their hashes; it does not select or correct the definition.
Still declare its objects, binders, dependencies and guards. Normalize any
needed notation explicitly and preserve the supplied meaning. Copying never
grants a property or a mathematical PASS.

A local declaration has symbol, type, scope, start/end, kind, declaration,
from_inputs, from_local and objects. from_local holds earlier F proof IDs;
ordinary object dependencies belong in objects. A fact proved later in this
same paragraph is not yet a premise for choosing its witness. State it in an
earlier S. In sum_{k=0}^m a(k), k is expression-bound; the free objects are a,m.
A k used outside the sum needs its own declaration. Statement binders are
recorded with that statement; a variable spanning S paragraphs uses locals.
Changing a ledger entry does not rename an existing formula.

## Actual own-packet inspection and release

After structural validation call read_author_packet(candidate,inference) for
every R. The returned view contains the real direct input/output statements,
definitions, logic and own proof, plus the shared contract binding. Read the
output without remembering its producer body. For each factual invocation,
identify its actual input or previous derivation. Complete closing notes use
these existing evidence groups; their criterion IDs are supplied by the
controller from Audit A. Cite actual H/M/E/N/F/R/S or candidate locations in
those notes; generic assurances are insufficient.

record_author_checks has this exact tool form (one row per actual N/P and R):

```json
{
  "candidate": 7,
  "readiness": "no_known_issue",
  "open_issues": [],
  "resolutions": [],
  "original_context_note": "Located comparison of original target/H, definitions, selected source contracts and graph closure.",
  "output_notes": [{"id": "P", "note": "Located check of the full output and the derivation of every clause."}],
  "inference_notes": [{
    "id": "R001",
    "dependency_and_local_assumption_check": "Actual factual grounds, calculation, compatible inputs and discharged assumptions, with locations.",
    "source_application_check": "Actual substitutions and grounds for every source premise, or why no source is used.",
    "declaration_check": "Actual object introductions, types, witness bases and scopes, with locations."
  }]
}
```

These are author claims, not PASS verdicts. If an obligation is unfinished,
set readiness=unresolved and list an issue such as
{id:"I001",criterion:"dependency_closure",location:"/graph/inferences/0/argument/0/text",note:"The exact missing input/derivation."}.
Use not_checked for unperformed inspection; incomplete notes can be saved,
but cannot release the artifact. Known issues persist across candidate edits.
Once corrected, provide resolutions:[{id:"I001",location:"/graph/inferences/0/argument/0/text",note:"The actual correction or justified withdrawal and its grounds."}].
Both issue and resolution locations must exist in the current candidate.
The context note checks the actual definition types and their prior guards;
inference notes check the exact source conclusion and any needed change of
domain or representation, rather than listing source names alone.
An empty new list cannot silently erase an old issue. The program checks
coverage, explicit state, locations and content/authority binding; mathematical
soundness still needs independent Audit A.

An actual own-packet read remains credited after an unrelated candidate edit
only when its complete displayed mathematical view and acceptance authority
have identical canonical contents. The recorded hash covers parameters, logic, selected
definitions, actual direct inputs/source contracts, output and full argument.
Changed views require new actual reads. Current whole-candidate release notes
are still invalidated by every edit, and known issues still need resolutions.
These are same-author read receipts, never inherited mathematical verdicts.

Only author_release_ready allows complete-artifact submission. Otherwise
continue the actual local proof/source work in this same stage. At a real
budget limit preserve the draft as unfinished. Normal completion difficulties
are not a substantive mathematical-gap report. Source/graph edits invalidate
bound closing notes. When ready, resubmit the exact candidate. Fresh Audit A
receives none of these notes or historical feedback.

## Native Mathlib access

probe_library queries the selected Mathlib environment directly and resolves
genuine aliases and the actual module; its optional module argument is only a
locator hint. The query records its actual environment and native evidence.
Read the pinned source
and compare its whole native signature with its NL restatement and actual
application. Predicates/data definitions are not source theorems. Same-stage
M-label renumbering can reuse exact metadata through a disclosed mapping;
it does not rewrite any mathematical statement or applicability argument.

## Background granularity

Follow Audit A's shared verified-background admission rule. Register the main
tools; write ordinary rigorous mathematics rather than anticipating every
small Lean lemma. Correct elementary compression is allowed. Audit A can
verify an omitted routine library fact and attach a note without an author
rewrite. Missing original H, source uncertainty and substantive proof gaps
remain blocking. These audit notes later accompany each Lean task.
