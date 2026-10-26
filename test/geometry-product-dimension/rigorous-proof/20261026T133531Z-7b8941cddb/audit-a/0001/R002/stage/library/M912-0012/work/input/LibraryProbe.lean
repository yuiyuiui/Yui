import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let name ← resolveGlobalConstNoOverloadCore `Int.lt_floor_add_one
  let info ← getConstInfo name
  match info with
  | .thmInfo _ => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? name
  IO.println s!"RESOLVED_NAME:M912:{name}"
  match actual with
  | some source => IO.println s!"RESOLVED_MODULE:M912:{source}"
  | none => throwError "This source has no imported module"
  IO.println "BEGIN_SIGNATURE:M912"
  let printed ← Meta.ppExpr info.type
  IO.println s!"@{name} : {printed}"
#eval IO.println "BEGIN_AXIOMS:M912"
#print axioms Int.lt_floor_add_one
#eval IO.println "END_SOURCE:M912"
