import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let name ← resolveGlobalConstNoOverloadCore `HasDerivAt.congr_of_eventuallyEq
  let info ← getConstInfo name
  match info with
  | .thmInfo _ => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? name
  IO.println s!"RESOLVED_NAME:M907:{name}"
  match actual with
  | some source => IO.println s!"RESOLVED_MODULE:M907:{source}"
  | none => throwError "This source has no imported module"
  IO.println "BEGIN_SIGNATURE:M907"
  let printed ← Meta.ppExpr info.type
  IO.println s!"@{name} : {printed}"
#eval IO.println "BEGIN_AXIOMS:M907"
#print axioms HasDerivAt.congr_of_eventuallyEq
#eval IO.println "END_SOURCE:M907"
