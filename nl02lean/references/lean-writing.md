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

5. **Repair after a bounded check.** Native checks have a separate per-call wall
   limit, normally 300 seconds, and use Lean's finite default heartbeat budget.
   A timeout or heartbeat diagnostic leaves the goal unaccepted and returns
   control to the same worker. Inspect the retained candidate and diagnostic,
   then check a smaller typed application, conversion or proof fragment before
   integrating it. Do not repeat the unchanged expensive candidate or disable
   limits to avoid diagnosis. Preserve the target, allowed inputs and proof
   requirements; a timeout alone establishes no mathematical gap.

The runtime enforces the per-call wall limit independently of these writing
rules. Whole-case and model-stage execution remain unlimited by default.
Retain failed attempts and actual diagnostics. Standalone assembly, native
trust/signature checks and independent endpoint-fidelity Audit B remain required.
