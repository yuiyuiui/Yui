import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let name ← resolveGlobalConstNoOverloadCore `Real.volume_Icc
  let info ← getConstInfo name
  match info with
  | .thmInfo _ => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? name
  IO.println s!"RESOLVED_NAME:M007:{name}"
  match actual with
  | some source => IO.println s!"RESOLVED_MODULE:M007:{source}"
  | none => throwError "This source has no imported module"
  IO.println "BEGIN_SIGNATURE:M007"
  let printed ← Meta.ppExpr info.type
  IO.println s!"@{name} : {printed}"
#eval IO.println "BEGIN_AXIOMS:M007"
#print axioms Real.volume_Icc
#eval IO.println "END_SOURCE:M007"
