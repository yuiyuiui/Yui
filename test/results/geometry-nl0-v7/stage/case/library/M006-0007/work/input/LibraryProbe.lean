import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `Real.dimH_univ_pi_fin with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `Real.dimH_univ_pi_fin
  unless actual == some `Mathlib.Topology.MetricSpace.HausdorffDimension do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.Topology.MetricSpace.HausdorffDimension"
#eval IO.println "BEGIN_SIGNATURE:M006"
#check @Real.dimH_univ_pi_fin
#eval IO.println "BEGIN_AXIOMS:M006"
#print axioms Real.dimH_univ_pi_fin
#eval IO.println "END_SOURCE:M006"
