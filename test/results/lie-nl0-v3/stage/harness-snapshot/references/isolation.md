# Clean execution boundary

The developer/controller process may inspect the implementation and user inputs.
It is not itself a clean experimental model. Every measured model stage uses a
new carrier session with a temporary home, state and working directory. Only
subscription authentication and the selected model catalog are copied into that
state; authentication files are removed when the stage ends and never logged.

The local carrier is restricted by an OS sandbox to its own state and one
loopback relay. Lean runs offline, can read only the pinned toolchain/library
and its task workspace, and cannot read the developer's project tree. The model
has no shell, arbitrary filesystem, browser, memory or personal-skill tool.

The relay constructs a semantic request allowlist: exact model and reasoning,
explicit Yui or bare instructions, exact authorized user messages, verified
within-stage model history, actual tool results and explicit tool schemas.
Developer/system additions, other user messages, server-conversation references
and unrelated provider metadata are removed or rejected before transmission.
No automatic inherited compaction context or model fallback is allowed.

Allowed mathematical information consists of the frozen problem, definitions,
permitted statements, supplied proof, selected Yui rules in the Yui arm, and
explicit tool results. External primary text must be explicitly staged with its
identity and hash before use. It is not obtained from arbitrary local files.
The direct arm has no Yui strategy/plan/reference-answer material.

Audit both what the carrier attempted to send and what the relay actually sent.
Retain payload hashes, tools, real replies, faults and denied-access controls.
Model self-report is supplementary; it is not proof of isolation. Provider-side
pretraining, undisclosed server state and account infrastructure are outside
this local verification boundary. "Clean" refers to the observable execution
and transmitted-input contract, not an untrained or provably stateless provider.

The Standard policy removes premium-speed request/header hints. Requested and
observed tier metadata must be retained; an incompatible actual tier is a
configuration failure. A missing reported tier remains explicitly unverified.
