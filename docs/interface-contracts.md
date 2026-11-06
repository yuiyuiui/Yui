# Model submission contracts

The owner of an artifact defines its structural protocol once, from the data
the consuming stage needs. Tools advertise that definition, format instructions
are generated from it, and validation uses it before the existing semantic
checks. Changing a prompt or tool declaration alone cannot change acceptance.
No format adapter supplies a verdict, deletes an unexpected field, or relaxes
source fidelity, Lean checking, dependency closure, or user decisions.

## Ownership map

| Boundary | Authoritative definition | Consumers |
| --- | --- | --- |
| Global and local Audit A | `audit_a_campaign.review_shape` | Complete/partial submissions, saved rows, completion summaries, campaign collection |
| Local background notes | `background.note_schema` and `source_schema` | Review submission, checkpoint tool and provenance validation; checkpoint scope excludes native library notes |
| Basis semantic review | `basis_review.review_shape` and `row_schema` | Same, including resolution required only for the disputed basis item |
| Interface review/adjudication | `interface_review.review_shape` | Saved/direct reviews and collected interface receipt |
| Audit B semantic review | `audit_b_review.review_shape` | Dynamic endpoint checks, saved/direct reviews and receipt collection |
| Basis author | `basis.artifact_schema` | Author tools and basis validation; reusable edits use `payload_protocols.editable` |
| NL0 author transport | `artifact_validation.submission_schema` | Complete draft, retained-candidate selection, patches and source-use binding |
| Node-local repair | `NodePatch.schema` | Own inference draft or located global repair request |
| Interface author | `translation_author.artifact_schema` | Author tools and typed candidate validation; step fields come from `dependency_instances.step_schema` |
| Source factoring | `source_preparation.patch_schema` | Preparation tool and patch application; NO_CHANGE is a separate explicit variant |
| Source cut review | Shape constructed in `source_refactor.cut_reviews` | Tool and review validation |
| Proof diagnosis | `proof_diagnosis.artifact_schema` | Route-dependent comparison and diagnostic submission |
| Source-gap allegation | `proof_repair.source_issue_schema` | Proof-worker tool, diagnosis and allegation validation |
| Proof obstruction report | `proof_repair.obstruction_schema` | Worker tool and live diagnosis request; a source allegation requires its evidence and ordinary local proof errors remain local |
| Endpoint mapping/connection | `audit_b.mapping_schema` | Connection author and final mapping reader; optional proof patches are separately checked |
| Partial Lean type probes | `translation_author.type_probe_schema` | Expression-checking tool and its parameter validation |
| Development interface and plan tools | `ir.interface_draft_schema` and `plan_schema` | Legacy string adapter instructions and the actual interface/plan checks |

`ReviewShape` derives required review pointers, the saved-row tool, complete and
partial artifact variants, and the completion summary from the same fields.
Full coverage is not a verdict: a complete UNVERIFIED or FAIL review remains
UNVERIFIED or FAIL. Saved completion adds only controller identities and the
reviewer's actual saved rows and supplied summary.

The shared schema evaluator implements the small JSON Schema vocabulary emitted
by these definitions. It does not coerce types, count Boolean values as integers,
or mutate rejected objects. Errors identify the JSON pointer and missing or
unexpected fields. Relational requirements, actual source locations, protected
interfaces and proof validity stay in the existing domain validators.

## Deliberately different inputs

Incomplete author drafts can be saved without passing final validation. NL0's
author language also permits controller-bound metadata and omitted duplicate
aliases, unlike a finalized NL0 file. Its `spec` and `graph` draft bodies still
go through normalization, structural preflight and the canonical NL0 checker;
they must not be confused with an already accepted graph. Explicit JSON edit
values are arbitrary JSON because the addressed field determines their type.
Existing extensible finding payloads remain extensible; blocking findings also
advertise and validate the owner's required quotation or comparison fields.
The owner still resolves locations and checks the quoted bytes. These are stated input languages, not competing
definitions of the same final artifact.

Compatibility string wrappers decode into the same checker as object tools.
Historical receipts retain their existing readers. Running jobs keep their
frozen runtime; changing the installation does not migrate an active or paused
review or authorize its resumption.

## What the previous tests missed

The earlier native review fixture built replies from `contract.base` and
`contract.required`, then manually added fields known to the test author.
It exercised real processes, dispatch and collection, but bypassed the question
of whether the advertised submission schema conveyed the consumer's format.
Saving and submitting through one validator was tested; deriving the producer's
format from that validator's authoritative protocol was not.

That left three separately maintained descriptions: the prose prompt, an open
tool-object declaration, and the consumer's exact field checks. The earlier
saved-row repair covered the persistence boundary, but did not eliminate this
duplication across the whole submission. A long workflow test with an already
correct payload could pass while the actual producer was still asked to guess
the fields. This was a design and test-selection omission, not a requirement
for a harder mathematical benchmark to reveal the defect.

The geometry incident exposed that gap: all 18 requested rows were saved, but
an extra top-level `verdict` and `notes` caused a generic completeness error.
Repeated guesses eventually reached the correctly functioning no-progress
guard. The repair keeps the guard and gives producers the exact protocol and
located feedback rather than relying on repeated guesses.

`test_artifact_protocol.py` exercises the advertised schema, invalid fields,
partial versus full coverage, saved/direct and object/string submission,
scope-dependent rows, correction, downstream validation, and a real native
client receiving a rejected payload followed by a corrected one. Existing
native pause/resume/cancel, binding and workflow suites remain required.
The native campaign regression also goes from an invalid global submission to
its correction, parallel local reviews and the actual bound Audit A collector.

Tests of semantic inconsistencies continue to reach the semantic validator:
their blocking findings now contain valid quotation/comparison fields before
asserting that an all-PASS summary is rejected. They do not count an earlier
format error as evidence that the semantic inconsistency was detected.

## Validation record: 2026-11-06

The complete catalogue contains 1,134 tests in 111 modules. All modules were
exercised in four disjoint processes, with 366, 238, 258 and 272 tests. The
parallel split was `sorted(test_modules)[index::4]`; each process used the
standard `tests/run_tests.py` runner and its own cleanup root.

Full discovery caught missing node identities in two new format diagnostics,
outdated error-message assertions, an incomplete old mapping fixture, and a
real migration regression: early mapping validation skipped retained-candidate
and feedback publication. The last issue was fixed by validating inside the
existing saved-candidate path, before any proof patch or acceptance. Rejected
payloads remain unchanged. The regression now exercises missing explanation,
an extra field, an invalid proof-term type, an unknown node, all four retained
feedback records, and a corrected mapping through actual Lean construction.

After the relevant corrections, the 366-test and 272-test shards passed, and
all six mathematical-NL0 policy tests passed. After the final mapping change,
the following affected suites passed; the entire catalogue was not repeated
again after that localized change.

| Final rerun | Tests | Result |
| --- | ---: | --- |
| Artifact protocols, review controllers, native review campaign and progress guard | 58 | PASS |
| Postprocessing, final acceptance and local helpers | 22 | PASS |
| Four complete case-to-export routes and workflow handoffs | 7 | PASS |

All final reruns had zero skips and `CLEANED` cleanup receipts. The native
clients used deterministic loopback services, not a live model. These are
software tests, not a new mathematical benchmark.

An additional read-only replay used the geometry incident's 18 actual saved
judgments. The malformed summary was rejected with
`/summary: missing=[], unexpected=['notes', 'verdict']`; the corrected wrapper
passed the original semantic reader without altering any judgment. The live
progress, tool log and error-state hashes were unchanged. Both existing runs'
168 frozen runtime bindings were also verified. Neither run was resumed,
cancelled, restarted or migrated by this repair.

Package validation (`validate-skill`) and Git whitespace checks passed.
