# Translation instructions

## Translation-entry source preparation

Start from the frozen original NL0. Before creating final IR artifacts or
worker packets, use [local source refactoring](source-refactoring.md) to identify
useful already-derived common lemmas and make only allowlisted substitutions.
Keep source statements and unrelated proof text unchanged; review the new
producer and each substitution cut using the baseline's actual evidence.
Do not reconstruct the proof, silently inherit PASS or rerun a full-case audit
by default. If no safely local extraction is useful, keep the baseline.
Use source_preparation.py to validate the current baseline, allowlisted patch,
new producer reviews and substitution reviews. Preserve its actual qualifications;
Audit B consumes this checked incremental result, not the worksheet alone.
Finalize/freeze Lean representations, shared ports and local plans afterwards,
then export the actual worker packets from the accepted source version.

## NL0 to interface contract

1. Receive the exact v2 per-R packet, its spec/graph bindings and Audit A
   receipt. Verify the upstream receipt before claiming production readiness.
   Development may instead use a clearly labeled legacy extract with complete
   mathematical text, original source spans and no current-Audit-A claim.
2. Inventory the direct input propositions, conclusion and all used definitions.
   Copy their mathematical content; never reconstruct an input by consulting
   a producer's proof or a reference Lean solution. Target context is orientation,
   not an additional premise. For a v2 graph, use the existing packet exporter.
3. Choose Lean representations jointly across connected ports. Record domains,
   quotient/representative choices, pointwise/a.e./distributional equality,
   finite/extended norm range, convergence mode, measure and normalizations.
   Ask which operations the proof route actually needs before choosing a type.
4. Elaborate definitions and exact input/output signatures. Check existence and
   nonzero/domain guards. If multiple representations are useful, name their
   conversion obligations explicitly. Do not require boundedness merely to
   compare extended-valued suprema; do not derive fixed-point evaluation from
   a.e. equality without a justified representative condition.
5. Review each port against NL0, including quantifiers, uniformity, exceptional
   branches, constants and structure fields. Freeze the contract with hashes.
   Missing proof content returns to NL0/Audit A; a missing API remains an
   implementation issue. No automatic alternative mathematical proof search.

Current producers/dependencies come from inference outputs and direct-input
lists. An `origin` label may cite the baseline derivation before extraction;
it is historical provenance, not an extra edge or the current producer. Trace
versions when checking provenance and do not invent a cycle from an origin
label. New extraction labels should identify the baseline revision explicitly.

## Contract and NL0 to transition plan

1. Read all supplied NL paragraphs before splitting. Retain the original route.
   Group algebraic normalization into one calculation when that avoids needless
   model/compiler round trips. Split an expensive representation/limit/transport
   bridge from subsequent straightforward applications when it has a useful
   closed interface. Finer splitting is a choice to test, not an objective.
2. For each T, write a complete Lean proposition, exact direct input IDs and
   the NL paragraph IDs it implements. Input IDs are AND premises. Temporary
   assumptions are discharged within a proof or exported as a closed implication.
3. Export every result that another T needs as a statement. Do not rely on
   a previous proof body's local notation, hidden facts or unavailable objects.
   Keep existence guards direct and quantify all locally introduced objects.
4. List representation bridges, library application conditions and computational
   normalization in the explanation. A strategy suggests operations; it never
   supplies a theorem. Source fidelity and direct-premise use remain required.
5. Run structure and type checks. Inspect semantics separately. A plan whose
   transition cannot be justified is not rescued by well-formed syntax.

## IR to Lean

1. Give a worker the frozen contract, its one T packet, and its explicit direct
   input statements. Do not expose reference solutions or sibling proof bodies.
   Shared context contains definitions and parameters, not ambient hypotheses.
2. Generate only the tactic body for the fixed T target. Use the pinned library
   to implement the NL step. Prefer explicit intermediate conclusions and
   `simp only` when they make dependency accounting inspectable. Record library
   results actually used, including substantive facts invoked by automation.
3. Check locally. If it fails, preserve the goal, local context, diagnostic,
   attempted code and hashes. Continue a clear local repair directly. Optional
   obstacle lookup is available after observed lack of progress; it is not a
   mandatory model diagnosis pass. A Lean error category is an observation,
   not a root cause. The current small guidance control did not show an overall
   benefit from mandatory extra guidance.
4. Test the retrieved recipe's preconditions. Prove a missing condition from
   allowed inputs, choose another applicable strategy, or abstain. Never append
   that condition to the target's assumptions. A judged mathematical gap returns
   to NL0/Audit A; elapsed time, search failure or network faults cannot establish
   one. Repeated no-progress retries warrant reconsidering the implementation
   route or an optional bounded diagnosis, charged to the attempt's budget.
5. Freeze accepted proof bytes bound to contract and plan. Assemble the actual
   local proofs, compile P and print its signature/axioms. Recheck in a fresh
   verifier work directory. Local success without root closure is partial.
6. Apply [Audit B](audit-b.md) after actual proof assembly. Freeze source and
   proof bytes, review source-to-actual-type concordance, inspect dependency and
   signature evidence, and perform the fresh kernel gates. Complete the located
   semantic review with its actual scope. These steps, rather than the earlier
   compiler gates alone, govern the new B verdict.

## Use local Audit A notes when they can shorten an implementation route

Use familiar library interfaces directly. For an unfamiliar exact interface,
a relevant local note's checked declaration may save a lookup; otherwise use
ordinary pinned-library search. Neither case requires a preliminary note scan.

The main use is an application or transport obstacle. During the existing
worker's normal reasoning, relate the actual Lean goal and available context
to its mapped NL paragraph. If the local index suggests a useful note:

1. Read that note's full grounds and justification. Identify the intended
   application, the precise premise it needs, and what the current context
   already supplies. A condition's mathematical source may have a different
   Lean representation from the required premise.
   Ground pointers address the audited NL packet, not positions in the current
   Lean context. Match their content to actual binders; never assume that an
   input index or an NL fact label is itself a Lean proof.
2. Form the smallest useful intermediate goal connecting those available
   grounds to the premise. Prove it from permitted inputs and local facts,
   then try the intended application. Do not turn a note into a new assumption,
   require a separate helper theorem per note, or reconstruct a larger source
   argument merely because a routine interface premise is expressed differently.
3. Check the actual Lean types, guards, equality/convergence mode and feedback.
   A verified mathematical note is not an executable proof or a guarantee of
   representation compatibility. If it does not fit, continue ordinary allowed
   search/repair; do not force its route or cycle through every note. A genuine
   source/interface change follows the existing review boundary.

For example, suppose a limit of `f` is established and the NL argument says
`g` agrees with `f` on a sufficiently small punctured neighborhood. To prove
the same limit for `g`, first express that local agreement as
`heq : f =ᶠ[l] g` for the actual filter `l`, then apply
`Filter.Tendsto.congr' heq hf`. The note can identify this intermediate premise
and its existing grounds; the worker still proves `heq`. This is a schematic
interface-bridge example, not a supplied proof of a benchmark obligation.

The canonical packet retains all selected audited notes and source bindings.
Under `local-background-on-demand-1`, a Yui proof worker initially sees only
its task's compact `background_note_index`: ID, location, fact, kind and any
checked declaration name. `read_background_note` returns one selected note's
complete material. No sibling notes/proofs or whole-case supplement are exposed
through that tool. Mathematical inputs and Audit B accounting remain unchanged.
There is no separate diagnosis model, mandatory lookup or claimed speedup.

## Reuse and parallel work

Identify mathematical extraction candidates during translation-entry source
preparation, not after final worker packets exist. During interface/planning
work, identify repeated typed obligations and stable common Lean ports. Freeze
those interfaces without proving the entire project twice. Record object
identity and local views as specified in architecture.md; require explicit
proved bridges. Preserve natural node boundaries and apply shared-lemmas.md.
After freeze, lookup may fill an already declared interface with a compatible
checked proof; it does not discover new mathematical premises or mutate NL0.

When a reviewed shared export is compatible with a supplied store, attempt the
deterministic exact-key lookup and recheck its closed conditional proof in Lean.
On a miss use the ordinary worker. Do not add an LLM call solely to classify a
cache query. A strategy card is advice; a store entry is a checked conditional
proof with all its guards visible. Include source-cache elaboration costs.

Use the bounded scheduler after interfaces are frozen. Queue ownership, state
and cancellation follow [the execution protocol](execution-protocol.md).
Mathematical input dependencies become local binders for body work and actual proofs for final
assembly. A producer's failure leaves the final theorem incomplete. Record the
initial library, all admissions and each node's selected inputs. Never make a
shared theorem silently available through the global definition registry.

## NL0 packet adapter

Run the existing parent tool, without changing its rules:

```sh
python3 ../scripts/nl0.py packet /absolute/case/nl0.json \
  --spec /absolute/case/spec.json --inference R001
```

Store the full output as the source artifact and its hash in the contract.
The translator still authors Lean representations and signatures; the adapter
exports audited information and is not a natural-language compiler.
