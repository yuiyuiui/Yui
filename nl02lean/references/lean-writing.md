# Lean implementation safeguards

Apply these requirements within the accepted NL0 and the fixed Lean interface.
They govern implementation, not additional NL0 detail or a weaker Audit B.
Use existing library readers and local checking tools; no separate review
model, new premise or mandatory lookup of every familiar declaration is needed.

1. **Check critical library signatures.** Before relying on a critical or
   unfamiliar library application, establish its complete type in the pinned
   environment, including explicit, implicit and instance binders and all
   side conditions. Read the declaration or check a small typed application
   when its signature is uncertain. Do not infer the calling convention from
   its name or pass an implicit argument as though it were an explicit one.
   A previously checked signature in this context need not be looked up again.
2. **Constrain difficult inference.** When coercions or implicit inference
   obscure the intended application, give the intermediate fact an explicit
   type and supply the relevant named parameters, such as the set, exponent
   or ambient space. Prefer this to leaving Lean to discover those choices by
   unfolding large definitions. Routine unambiguous arguments can stay
   implicit; explicit parameters must preserve the existing target and inputs.
3. **Check conversions before combining them.** When an argument crosses Lean
   representations, first establish a small typed conversion fact, then use
   it in the main proof. In particular, distinguish `ℝ`, `ℝ≥0` and `ℝ≥0∞`;
   check the conversion direction, nonnegativity and any finiteness conditions.
   A conversion is not automatically invertible, and matching notation does
   not establish equality of differently typed expressions. Reuse a checked
   fact when available. Do not invent another representation, a global helper
   requirement or an extra hypothesis just to satisfy this instruction.
4. **Isolate an inference failure.** If compiler feedback identifies a library
   application, coercion or expensive inference problem, reduce the next check
   to that application or conversion with explicit local types before adding
   more proof code. Use `check_auxiliary` in a proof worker, or
   `check_lean_types` during preparation when that tool is supplied. Helpers
   use only the current allowed inputs and never become new premises. Once
   the small check succeeds, integrate the result and recheck the complete
   obligation; success of a helper alone does not accept the target.

5. **Diagnose a bounded check.** Translation starts a native check with six
   minutes and the controller-owned 20,000,000 heartbeat budget. After an actual
   native wall timeout a reviewer inspects the exact source and compiler output.
   A located implementation problem returns to the author for a targeted edit at
   the current allowance. A workload-only diagnosis authorizes the same source
   for six more minutes on its next attempt, up to thirty minutes per call.
   Uncertain diagnoses retain the allowance and request a smaller diagnostic.
   A heartbeat error goes straight to local repair. Explicit shorter deadlines
   continue to apply. Only a successful native check can accept the candidate.

A proof worker can send independent private statements and their routes together
through `prove_independent_helpers`. Its enclosing parameters and direct ports stay
fixed. Check the original transition after accumulating helpers. Inspect its native
diagnostic before deciding whether another local lemma or a reviewed public
interface revision is needed. On supported headers a warm auxiliary check imports
compiled declarations and elaborates only the new helper. For file-local scopes
the checker includes only the new helper and its transitive dependencies. Check
each helper as it is written. A failed helper can be corrected independently.
If composition identifies a previously checked helper body, pass its existing
name as `replace` to `check_auxiliary`. Only edit that body. Names, types and
other bodies remain stable. The checker renews any invalidated receipts.
Once all helpers pass, compose them and check the whole node. Final submission,
assembly and Audit B recheck source in their normal environment.

The runtime enforces the per-call wall limit independently of these writing
rules. Whole-case and model-stage execution remain unlimited by default.
Retain failed attempts and actual diagnostics. Standalone assembly, native
trust/signature checks and final machine Audit B remain required.

Before freeze, every complete T declaration must elaborate with exactly its
worker parameters, instances and direct inputs. Explicitly supply parameters
that their argument types cannot determine; a same-named context variable is
not an inference rule. The strict declaration check defines the proposition,
without proving it, and rejects unresolved holes and non-proposition goals.
`#check` is a useful reader aid, not sufficient declaration acceptance. A proof
body cannot resolve a hole in its preceding theorem declaration.

Checked auxiliary propositions receive a `yui_aux_...` name and an explicit
application with the existing local parameters/inputs. Reuse these theorems in
later auxiliary checks and the final body. The controller retains their actual
proof bodies and compiles them into standalone assembly. They are same-node
implementation lemmas, not extra assumptions. Read the helper index after a
context reset; never rebuild a checked helper merely because a turn ended.

Separate diagnostic printing from proving. `show_term` and similar suggestion
output may spend substantial time after the proof tactic runs. If that diagnostic
wrapper is implicated, check the same proof without it; only the new successful
check establishes acceptance. Do not ignore an unsuccessful process exit. If
small helpers pass but a monolithic body exhausts resources, retain the separate
checked helper declarations and compose them rather than repeatedly copying
their bodies into a growing proof.
