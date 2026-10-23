import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `LipschitzWith.dimH_image_le with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `LipschitzWith.dimH_image_le
  unless actual == some `Mathlib.Topology.MetricSpace.HausdorffDimension do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.Topology.MetricSpace.HausdorffDimension"
#eval IO.println "BEGIN_SIGNATURE:M004"
#check @LipschitzWith.dimH_image_le
#eval IO.println "BEGIN_AXIOMS:M004"
#print axioms LipschitzWith.dimH_image_le
#eval IO.println "END_SOURCE:M004"
