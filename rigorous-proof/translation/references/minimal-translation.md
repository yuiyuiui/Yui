# Minimal translation from accepted NL0

Start with the accepted source map and specification. Read the supplied proof
and definitions where needed to choose faithful types. Other Yui documents,
library searches and individual background notes are available on demand;
there is no requirement to preload the entire skill or all note bodies.

1. Preserve the accepted source and Audit A. Use a source revision only when an
   actual mathematical change or useful shared extraction requires it. Reusing
   unchanged acceptance runs integrity checks, not another model Audit A.
2. Choose the mathematical representation, complete original H/E input types,
   N/P output types and useful local proof obligations. The controller copies
   source paragraphs and note locations. Mathlib is freely available; retain an
   M port only when useful, otherwise apply the library directly. Supply short
   `endpoint_correspondence` notes for every E and complete P (including all
   hypotheses), explaining direct or equivalent translation. Save partial interface drafts, revise
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
   proofs, discharge any retained M ports and compile standalone `Proof.lean`.
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

At Audit B, notes are guidance, not library permissions. All proved results in
the pinned Mathlib environment are available without registration. Review every
external E and complete P against its actual Lean type using the concise author
correspondence explanation; independently check direct or equivalent meaning.
A new external assumption or stronger hypothesis still returns to the source
boundary. See [the complete Audit B standard](audit-b.md).

## Work continuously, report genuine blockers

There is no ordinary `TASK_INCOMPLETE` reporting tool. While unfinished, keep
making concrete edits, queries or proof checks. Submit a completed artifact or
report a supported mathematical/source/input blocker. If a model turn ends
without either, the controller sends one short continuation instruction; it
does not demand a progress essay. State/usage recording is programmatic.

Execution is unlimited by default: no whole-case, stage, native-check, total
token, or call quota is imposed. Keep measuring usage and allow explicit
cancellation. Only a user-requested finite case deadline covers the entire
translation, including preparation, queue waiting, parallel proofs, assembly
and Audit B; later stages cannot reset that optional deadline. Preserve partial
results and report execution health separately from mathematical acceptance.
