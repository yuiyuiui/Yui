import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `isCompact_iff_isCompactSpace with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `isCompact_iff_isCompactSpace
  unless actual == some `Mathlib.Topology.Separation.Hausdorff do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.Topology.Separation.Hausdorff"
#eval IO.println "BEGIN_SIGNATURE:M018"
#check @isCompact_iff_isCompactSpace
#eval IO.println "BEGIN_AXIOMS:M018"
#print axioms isCompact_iff_isCompactSpace
#eval IO.println "END_SOURCE:M018"
