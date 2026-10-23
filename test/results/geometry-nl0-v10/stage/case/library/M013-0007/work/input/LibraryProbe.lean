import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `MeasureTheory.measure_mono with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `MeasureTheory.measure_mono
  unless actual == some `Mathlib.MeasureTheory.Measure.MeasureSpace do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.MeasureTheory.Measure.MeasureSpace"
#eval IO.println "BEGIN_SIGNATURE:M013"
#check @MeasureTheory.measure_mono
#eval IO.println "BEGIN_AXIOMS:M013"
#print axioms MeasureTheory.measure_mono
#eval IO.println "END_SOURCE:M013"
