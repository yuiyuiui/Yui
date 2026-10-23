import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `Measure.hausdorffMeasure_of_lt_dimH with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `Measure.hausdorffMeasure_of_lt_dimH
  unless actual == some `Mathlib.Topology.MetricSpace.HausdorffDimension do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.Topology.MetricSpace.HausdorffDimension"
#eval IO.println "BEGIN_SIGNATURE:M001"
#check @Measure.hausdorffMeasure_of_lt_dimH
#eval IO.println "BEGIN_AXIOMS:M001"
#print axioms Measure.hausdorffMeasure_of_lt_dimH
#eval IO.println "END_SOURCE:M001"
