import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `Measure.hausdorffMeasure_apply with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `Measure.hausdorffMeasure_apply
  unless actual == some `Mathlib.MeasureTheory.Measure.Hausdorff do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.MeasureTheory.Measure.Hausdorff"
#eval IO.println "BEGIN_SIGNATURE:M006"
#check @Measure.hausdorffMeasure_apply
#eval IO.println "BEGIN_AXIOMS:M006"
#print axioms Measure.hausdorffMeasure_apply
#eval IO.println "END_SOURCE:M006"
