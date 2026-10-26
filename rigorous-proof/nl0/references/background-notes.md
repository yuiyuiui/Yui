# Verified background notes

Audit A's shared acceptance section is the single mathematical authority.
`verified-background-1` preserves all ten per-R checks and permits ordinary
mathematical compression plus positively checked omitted basic mathlib uses.

## Admission

An eligible step is correct, routine and local, has all material conditions
already available, and needs neither a new hypothesis nor a new core argument.
Check mathematical content, not length or familiarity alone. Major tools remain
explicit inputs. Wrong quantifiers, unjustified witnesses/limits, hidden project
lemmas and inaccessible external citations still block. A source guess is not
verification; API difficulty alone is not a mathematical error.

For example, continuity of a pointwise sum follows from the input continuity
and the codomain's continuous addition. A reviewer can probe `Continuous.add`
and record that application instead of demanding an epsilon-delta proof or an
author rewrite. Arbitrary codomains do not supply continuous addition by name.
Elementary arithmetic need not display every intermediate chain; a useful short
completion can remain an elementary note, with no imported theorem.

## Record

The reviewer calls `record_background_note` with:

- `id`: local BG001-style ID; `at`: exact `/inference/argument/0/text` pointer;
- `kind`: `elementary` or `mathlib`; `fact`: precise statement and conditions;
- `grounds`: `{location,reason}` records for actual available inputs,
  definitions, parameters or prior in-scope argument;
- `justification`: actual correctness/eligibility judgment, not a future TODO;
- optional `hint`: short Lean guidance;
- for mathlib, `source_id`: the M001-style selector actually checked using
  `probe_background`. The controller binds its source/signature/version/evidence;
  the reviewer still owns faithful meaning and applicability.

The receipt stores these as `inference_reviews[R].background_notes`; source
metadata is case-relative and hash-bound. Existing PASS/FAIL/UNVERIFIED values
remain. PASS with notes describes disclosed routine completion, not unqualified
author pre-registration, Lean verification, or success under the old policy.

## Review and handoff boundary

Local review sees its frozen packet plus logged pinned-mathlib tool responses;
it never receives another project proof, author repair history or owner hints.
The replay mode and material list disclose this expanded boundary. The actual
source probes and tool trace accompany the receipt. Source verification may
reuse pinned evidence; it does not require a second model per note.

`nl0.validate` returns the checked note supplement and its hash.
`background.effective` creates a derived dependency view adding basic M ports
to the appropriate R, without changing author graph bytes or proof paragraphs.
At translation entry, retain that supplement and bind its hash in
`contract.source.background_supplement_sha256` when notes exist. Include all
notes in the local plan; elementary notes need no new theorem root. Mathlib
notes become actual library applications, with no new H/axiom/sorry. Audit B
checks the same effective inventory and actual Lean closure.

Unchanged note evidence may be inherited with its actual review context. A
source extraction changing a consumer with notes requires its affected local
review first; the current adapter rejects that case explicitly rather than
dropping the notes. Zero extraction and unchanged consumers remain supported.
Changed math/conditions return to scoped Audit A; ordinary Lean binding work
stays in translation. Historical strict results are preserved, not relabeled.

The interface source also retains the complete `background_supplement`, not
just its hash. Plan steps list the relevant qualified note IDs, for example
`background_notes:["R004.BG001"]`. Workflow freeze checks the paragraph mapping;
local Lean packets receive only their selected notes.
