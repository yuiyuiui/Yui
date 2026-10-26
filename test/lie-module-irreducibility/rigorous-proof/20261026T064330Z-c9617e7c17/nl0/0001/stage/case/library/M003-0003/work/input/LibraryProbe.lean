import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let name ← resolveGlobalConstNoOverloadCore `Module.Basis.ofEquivFun
  let info ← getConstInfo name
  match info with
  | .thmInfo _ => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? name
  IO.println s!"RESOLVED_NAME:M003:{name}"
  match actual with
  | some source => IO.println s!"RESOLVED_MODULE:M003:{source}"
  | none => throwError "This source has no imported module"
  IO.println "BEGIN_SIGNATURE:M003"
  let printed ← Meta.ppExpr info.type
  IO.println s!"@{name} : {printed}"
#eval IO.println "BEGIN_AXIOMS:M003"
#print axioms Module.Basis.ofEquivFun
#eval IO.println "END_SOURCE:M003"
