import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let name ← resolveGlobalConstNoOverloadCore `isFiniteMeasureOnCompacts_of_isLocallyFiniteMeasure
  let info ← getConstInfo name
  match info with
  | .thmInfo _ => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? name
  IO.println s!"RESOLVED_NAME:M115:{name}"
  match actual with
  | some source => IO.println s!"RESOLVED_MODULE:M115:{source}"
  | none => throwError "This source has no imported module"
  IO.println "BEGIN_SIGNATURE:M115"
  let printed ← Meta.ppExpr info.type
  IO.println s!"@{name} : {printed}"
#eval IO.println "BEGIN_AXIOMS:M115"
#print axioms isFiniteMeasureOnCompacts_of_isLocallyFiniteMeasure
#eval IO.println "END_SOURCE:M115"
