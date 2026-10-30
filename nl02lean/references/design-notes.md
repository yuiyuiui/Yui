# Design basis and deliberate limits

The architecture makes representation and local proof obligations explicit
without creating a new universal mathematical language. Its backend is Lean
propositions under fixed contexts; the local worker produces a proof of each
conditional transition. Python performs bookkeeping and assembly, not semantic
mathematical inference.

[Chain of States](https://arxiv.org/html/2512.10317v1) studies the related
two-stage idea of extracting formal states from an informal proof and then
generating tactics between adjacent states. It motivates making intermediate
targets explicit. This prototype is a separate local implementation, not a
reproduction of CoSProver, its training or its benchmark. Its reported results
do not establish our speed. Here a correspondence review still constrains
which route a worker may implement; successful proof search alone does not
establish faithful translation.

[Official Codex app-server documentation](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server)
documents the local conversation/turn carrier and plan-authenticated model
transport. The current implementation uses isolated native Codex processes and explicit
Yui dynamic tools. Python communicates over stdio and owns workflow gates;
Codex owns direct model-service communication and native context management.
Configuration/input/tool receipts describe the observable boundary. Built-in
Codex instructions are retained, and raw provider HTTP payloads are not certified.
The former request-normalizing relay exists only in historical run snapshots.

The design leaves general natural-language semantic verification, automatic
global-definition discovery, arbitrary dependent witness export and optimal
representation selection outside its implementation. Audit B is implemented
for the generated conditional graphs: it inspects actual project dependencies
and direct imported mathematical proofs, with named approved library theorems
as trusted boundaries. It is not an unrestricted multifile Lean-project auditor.
The local revision adapter and workflow controller preserve source authority
and require actual scoped reviews; neither turns metadata into mathematics.
