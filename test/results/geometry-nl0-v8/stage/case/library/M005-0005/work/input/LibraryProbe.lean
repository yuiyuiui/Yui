import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `Real.dimH_of_nonempty_interior with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `Real.dimH_of_nonempty_interior
  unless actual == some `Mathlib.Topology.MetricSpace.HausdorffDimension do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.Topology.MetricSpace.HausdorffDimension"
#eval IO.println "BEGIN_SIGNATURE:M005"
#check @Real.dimH_of_nonempty_interior
#eval IO.println "BEGIN_AXIOMS:M005"
#print axioms Real.dimH_of_nonempty_interior
#eval IO.println "END_SOURCE:M005"
