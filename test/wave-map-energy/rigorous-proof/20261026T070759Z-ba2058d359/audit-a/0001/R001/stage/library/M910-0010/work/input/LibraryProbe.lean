import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let name ← resolveGlobalConstNoOverloadCore `inner_self_eq_norm_sq_to_K
  let info ← getConstInfo name
  match info with
  | .thmInfo _ => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? name
  IO.println s!"RESOLVED_NAME:M910:{name}"
  match actual with
  | some source => IO.println s!"RESOLVED_MODULE:M910:{source}"
  | none => throwError "This source has no imported module"
  IO.println "BEGIN_SIGNATURE:M910"
  let printed ← Meta.ppExpr info.type
  IO.println s!"@{name} : {printed}"
#eval IO.println "BEGIN_AXIOMS:M910"
#print axioms inner_self_eq_norm_sq_to_K
#eval IO.println "END_SOURCE:M910"
