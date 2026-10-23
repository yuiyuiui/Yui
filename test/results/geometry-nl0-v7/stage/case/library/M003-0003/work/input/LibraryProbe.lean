import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `hausdorffMeasure_of_dimH_lt with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `hausdorffMeasure_of_dimH_lt
  unless actual == some `Mathlib.Topology.MetricSpace.HausdorffDimension do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.Topology.MetricSpace.HausdorffDimension"
#eval IO.println "BEGIN_SIGNATURE:M003"
#check @hausdorffMeasure_of_dimH_lt
#eval IO.println "BEGIN_AXIOMS:M003"
#print axioms hausdorffMeasure_of_dimH_lt
#eval IO.println "END_SOURCE:M003"
