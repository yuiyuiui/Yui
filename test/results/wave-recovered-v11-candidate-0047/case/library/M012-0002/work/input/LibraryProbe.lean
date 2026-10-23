import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `MeasureTheory.IsFiniteMeasureOnCompacts.of_compact with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `MeasureTheory.IsFiniteMeasureOnCompacts.of_compact
  unless actual == some `Mathlib.MeasureTheory.Measure.MeasureSpace do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.MeasureTheory.Measure.MeasureSpace"
#eval IO.println "BEGIN_SIGNATURE:M012"
#check @MeasureTheory.IsFiniteMeasureOnCompacts.of_compact
#eval IO.println "BEGIN_AXIOMS:M012"
#print axioms MeasureTheory.IsFiniteMeasureOnCompacts.of_compact
#eval IO.println "END_SOURCE:M012"
