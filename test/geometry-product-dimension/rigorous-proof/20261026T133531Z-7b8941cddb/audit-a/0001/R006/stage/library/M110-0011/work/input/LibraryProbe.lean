import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let name ← resolveGlobalConstNoOverloadCore `tendsto_rpow_neg_nhdsGT_zero
  let info ← getConstInfo name
  match info with
  | .thmInfo _ => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? name
  IO.println s!"RESOLVED_NAME:M110:{name}"
  match actual with
  | some source => IO.println s!"RESOLVED_MODULE:M110:{source}"
  | none => throwError "This source has no imported module"
  IO.println "BEGIN_SIGNATURE:M110"
  let printed ← Meta.ppExpr info.type
  IO.println s!"@{name} : {printed}"
#eval IO.println "BEGIN_AXIOMS:M110"
#print axioms tendsto_rpow_neg_nhdsGT_zero
#eval IO.println "END_SOURCE:M110"
