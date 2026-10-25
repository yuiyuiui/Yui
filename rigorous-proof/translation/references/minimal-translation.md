# Minimal translation from accepted NL0

Start with the accepted source map and specification. Read the supplied proof
and definitions where needed to choose faithful types. Other Yui documents,
library searches and individual background notes are available on demand;
there is no requirement to preload the entire skill or all note bodies.

1. Preserve the accepted source and Audit A. Use a source revision only when an
   actual mathematical change or useful shared extraction requires it. Reusing
   unchanged acceptance runs integrity checks, not another model Audit A.
2. Choose the mathematical representation, complete original H/E/M input types,
   N/P output types and useful local proof obligations. The controller copies
   source paragraphs and note locations. Save partial interface drafts, revise
   those drafts, and use small Lean probes for uncertain types. Do not restart
   from an empty interface after an ordinary error.
3. Type-check and mechanically freeze the source correspondence, dependency
   boundaries and complete interface. The default route defers semantic
   interface review to final Audit B. Record `PENDING_AUDIT_B`, never a synthetic
   review PASS. An explicitly requested separate interface review remains
   available for legacy/recovery runs.
4. Run local proof workers on frozen conditional obligations. Each gets its
   input statements, matched source paragraphs and own compact note index.
   Read a full note only if useful. No sibling proof bodies, other cases,
   developer history or additional personal skills are supplied.
5. Start the serial [postprocessing author](assembly.md) to connect actual
   proofs, discharge original M ports and compile standalone `Proof.lean`.
   Inspect signatures/dependencies separately, then start the fresh independent
   semantic Audit B reviewer. A type check or conditional lemma is not full
   acceptance. A failed final fidelity review remains a failed attempt; do not
   relabel it as a success because its interface was frozen.

## Background notes are references, not extra ports

New contracts select `source.background_mode: node_local_reference`. Original
H/E/M/N/P entries remain unchanged; Audit A's verified supplement remains
hash-bound. Do not turn every note into a new M root, retype its entire library
signature, or require an extra theorem merely to restate it. The frozen
stage-one text's historical `background.effective` expansion is still supported
as `promoted_inputs` for old contracts; it is not the new translation default.

At Audit B, actual use of a note's library declaration is checked against the
notes belonging to that source inference. Its conditions and semantic use must
still be correct. Another node's note does not grant permission. Elementary
notes do not authorize arbitrary additional imported mathematical theorems.
Substantive new results or stronger assumptions return to the source boundary.

## Work continuously, report genuine blockers

There is no ordinary `TASK_INCOMPLETE` reporting tool. While unfinished, keep
making concrete edits, queries or proof checks. Submit a completed artifact or
report a supported mathematical/source/input blocker. If a model turn ends
without either, the controller sends one short continuation instruction; it
does not demand a progress essay. State/usage recording is programmatic.

Each configured case deadline covers the entire translation, including
preparation, parallel proof work, assembly and Audit B. A three-hour budget is
10,800 wall-clock seconds per case, not per worker or per stage. Native checks
and model stages use the remaining budget. Preserve partial results on expiry
and report execution health separately from an unfinished model task.
