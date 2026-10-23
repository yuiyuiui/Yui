import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `MeasureTheory.isAddHaarMeasure_volume_pi with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `MeasureTheory.isAddHaarMeasure_volume_pi
  unless actual == some `Mathlib.MeasureTheory.Measure.Lebesgue.EqHaar do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.MeasureTheory.Measure.Lebesgue.EqHaar"
#eval IO.println "BEGIN_SIGNATURE:M017"
#check @MeasureTheory.isAddHaarMeasure_volume_pi
#eval IO.println "BEGIN_AXIOMS:M017"
#print axioms MeasureTheory.isAddHaarMeasure_volume_pi
#eval IO.println "END_SOURCE:M017"
