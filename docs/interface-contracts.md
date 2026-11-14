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
