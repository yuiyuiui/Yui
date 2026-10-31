# Mathematically reviewed background in Yui

Audit A's shared section is the mathematical authority. The policy is
mathematical-background-v2-1. Ordinary mathematics is reviewed in NL0; exact
Mathlib implementation is resolved in nl02lean.

## Eligibility and record

A note records a correct, routine local step with actual available premises,
no new hypothesis, no missing project lemma and no new core proof route.
Give id (BG001 etc.), kind (elementary or mathematical), at (an existing
/inference/argument/N/text pointer), fact (precise mathematical statement),
grounds ([{location,reason}] for real available conditions), and justification
(actual mathematical reasoning). A familiar name alone is insufficient.
Non-native notes have no source field or claim of a verified Lean declaration.
The optional record_background_note tool saves a checkpoint; a complete review
may submit all its notes in one artifact without separate tool calls.

For example, continuity of a sum follows from the supplied continuity of the
functions and continuous addition on their actual codomain. Check those
conditions mathematically. The reviewer need not call Lean or identify
Continuous.add before judging that routine step.

Substantive missing arguments, changed quantifiers, missing witness existence,
unsupported limit exchanges and uncertain external statements remain blocking.
The controller validates structure and local pointers; it never decides that
a mathematical fact is true or routine. An actual independent reviewer owns
that decision and may return FAIL or UNVERIFIED.

## Handoff

The immutable author graph and hash-bound review notes jointly describe the
accepted mathematical proof. The format-4 receipt is not a format-3 verified native
background policy. Explicit native mathlib notes can still be inspected only
with their complete matching pinned evidence; they are optional, not a new
requirement for routine mathematical notes.

Normal translation uses node_local_reference. Notes travel with their own
paragraphs and do not become additional premise ports. Workers find appropriate
library declarations or prove auxiliary facts with their actual conditions.
The interface author chooses shared representations, not every local tactic
or implementation lemma in advance. Every required fact must eventually be
established in checked Lean. No note is an axiom or a new external E.

The source supplement hash and exact notes are bound in the interface contract,
worker packets and Audit B source inventory. They cannot be dropped, borrowed
from another node or relabeled as native evidence. Mathematical changes return
to affected Audit A scopes; representation-only changes remain reviewed Lean
work. Ordinary pinned Mathlib use needs no NL0 theorem-use ledger.
