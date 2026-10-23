import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `le_dimH_of_hausdorffMeasure_eq_top with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `le_dimH_of_hausdorffMeasure_eq_top
  unless actual == some `Mathlib.Topology.MetricSpace.HausdorffDimension do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.Topology.MetricSpace.HausdorffDimension"
#eval IO.println "BEGIN_SIGNATURE:M014"
#check @le_dimH_of_hausdorffMeasure_eq_top
#eval IO.println "BEGIN_AXIOMS:M014"
#print axioms le_dimH_of_hausdorffMeasure_eq_top
#eval IO.println "END_SOURCE:M014"
