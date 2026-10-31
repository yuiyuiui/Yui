# Native timeout triage: qualified implementation guidance

Retained completed implementations suggest a useful first repair direction:
make the elaborator's local work explicit before increasing its resource
allowance. In bounded replays under the same pinned environment, older
candidates reached a native resource limit while their completed replacements
compiled. The replacements used typed intermediate facts, explicit function
arguments, directed equality bridges, restricted simplification and explicit
composition instead of broad proof search.

This comparison does not identify one universal cause. Multiple edits occurred
between the candidates. A diagnostic located expensive definitional-equality
checking at an equality application. Removing an equality reversal alone did
not resolve the timeout; supplying two previously implicit function arguments
alone also did not complete within a bounded replay. Neither edit is a general
fix. A separate lower-heartbeat diagnostic exposed an ordinary type mismatch
before later resource errors, so error recovery can obscure the useful first
diagnostic. Small diagnostic allowances can themselves exhaust on valid code.

Use the procedure only after actual native resource feedback, and locate the
costly application before choosing its repair branch. A transport failure,
controller cleanup failure, unavailable dependency or changed theorem requires
its own handling. Keep the target and hypotheses fixed, retain failed controls,
check the repaired fragment, then compile the complete candidate again.

The detailed sources, timings, controls and uncertainty belong to the user's
work records outside this live bank. This sanitized note supplies implementation
guidance, not a proof template, a guaranteed speedup or independent mathematical
acceptance. Broader effectiveness remains unestablished.

Additional controlled comparisons isolated diagnostic term-printing wrappers:
the wrapped checks exhausted a native calculation budget while the unchanged
proof tactics, with the diagnostic wrapper removed, compiled. This supports a
diagnostic-overhead branch, not ignoring failed exits or deleting mathematical
steps. A completed modular implementation also motivates retaining separately
checked helper declarations rather than repeatedly elaborating their bodies
inside one large expression. That latter observation does not isolate a
universal performance cause or predict a speedup.
