import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let name ← resolveGlobalConstNoOverloadCore `Real.rpow_nonneg
  let info ← getConstInfo name
  match info with
  | .thmInfo _ => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? name
  IO.println s!"RESOLVED_NAME:M104:{name}"
  match actual with
  | some source => IO.println s!"RESOLVED_MODULE:M104:{source}"
  | none => throwError "This source has no imported module"
  IO.println "BEGIN_SIGNATURE:M104"
  let printed ← Meta.ppExpr info.type
  IO.println s!"@{name} : {printed}"
#eval IO.println "BEGIN_AXIOMS:M104"
#print axioms Real.rpow_nonneg
#eval IO.println "END_SOURCE:M104"
