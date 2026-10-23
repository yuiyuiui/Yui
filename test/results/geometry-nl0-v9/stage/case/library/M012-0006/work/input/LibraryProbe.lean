import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `MeasureTheory.dimH_le_of_hausdorffMeasure_ne_top with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `MeasureTheory.dimH_le_of_hausdorffMeasure_ne_top
  unless actual == some `Mathlib.Topology.MetricSpace.HausdorffDimension do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.Topology.MetricSpace.HausdorffDimension"
#eval IO.println "BEGIN_SIGNATURE:M012"
#check @MeasureTheory.dimH_le_of_hausdorffMeasure_ne_top
#eval IO.println "BEGIN_AXIOMS:M012"
#print axioms MeasureTheory.dimH_le_of_hausdorffMeasure_ne_top
#eval IO.println "END_SOURCE:M012"
