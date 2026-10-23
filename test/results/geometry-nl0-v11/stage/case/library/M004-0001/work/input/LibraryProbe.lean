import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `Metric.hausdorffDim_le_of_lipschitz with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `Metric.hausdorffDim_le_of_lipschitz
  unless actual == some `Mathlib.Topology.MetricSpace.HausdorffDimension do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.Topology.MetricSpace.HausdorffDimension"
#eval IO.println "BEGIN_SIGNATURE:M004"
#check @Metric.hausdorffDim_le_of_lipschitz
#eval IO.println "BEGIN_AXIOMS:M004"
#print axioms Metric.hausdorffDim_le_of_lipschitz
#eval IO.println "END_SOURCE:M004"
