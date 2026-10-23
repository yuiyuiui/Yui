# NL0 v2 authoring template

Use this checklist to create canonical JSON, not a parallel proof authority.
Read the complete [submission example](submission-example.md) for the exact
spec/graph shape and local-witness accounting. This neutral format example is
model-visible through `read_yui`; test fixtures remain outside that boundary.
It is not a benchmark or certification, and its audit remains unperformed.

## Specification

Freeze the full target/conclusion, all original H with origins, parameters,
logical primitives, D pairs, logic/calculations, input hashes and library pins.
Each D records its type, full definition, binders, used objects, D dependencies
and proved guards. Do not introduce a theorem as a definition or primitive.

## Proposition

Record `id`, `kind`, `statement`, `definitions`, `binders`, `objects`, and the
required source/origin fields. Write every formula, binder, condition, constant
dependency, domain and a.e./pointwise convention in the statement itself.
It must be usable without its producer's proof. Source/equation labels belong
in provenance, not as substitutes for content. Input binders are not free locals.

## Inference

Record direct `inputs`, one full `output`, `definitions`, `rules`, `locals`,
`argument` and actual E/M `applications`. Include definition guards as direct
inputs; additional H and ancestors are unavailable. Give each local object
`symbol`, `type`, `scope`, `start`, `end`, `kind`, `declaration`, `from_inputs`,
`from_local`, `objects`. Introduce it before use; justify witness existence.
Naming an object grants none of its required properties.
Keep a local object's symbol, actual type, complete introduction and
definition/existence basis together. After a local patch, check all affected
declarations and uses in that node, including simultaneous names and endpoints.
Each source application records `at: Sddd`; that paragraph must actually use
the source, and application conditions may use only facts available there.

Each S paragraph records `id`, `text`, actual `uses`, prior `uses_local`,
`objects`, full local `produces`, and assumption `introduces`/`discharges`.
Each produced F records `id`, full `statement`, statement-local `binders`,
`objects`, and its remaining `assumptions`. Supply the real derivation; fields
are not proof. Use direct
input IDs or earlier F IDs rather than inherited source equation numbers.
Export any fact needed by another R as a complete proposition.

## Reverse check before freeze

- For every actual object: where is its legitimate declaration and scope?
- For every substantive fact used: which direct input or earlier local proof
  supplies it? Does instantiation discharge all its conditions?
- For every output clause: where is it proved, and is it stated in full?
- Remove original text and all other proof bodies: is the packet still enough?

Run structural checks, render the views and generate packets. Create only an
UNVERIFIED audit scaffold. Author self-checks never fill the auditor's PASS.

In the clean authoring adapter, the controller binds omitted case identity,
input/pin hashes, native source metadata and omitted duplicate statements.
Explicit conflicts remain errors. Use its same-stage draft/patch tools to
preserve work after a rejected check; metadata repair does not require a new
mathematical proof. `find_library_sources` offers a small pinned metadata index;
each selected result still needs an explicit M record and actual Audit A.
