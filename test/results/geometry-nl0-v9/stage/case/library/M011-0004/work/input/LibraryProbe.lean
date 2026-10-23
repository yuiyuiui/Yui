import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `MeasureTheory.Measure.real with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `MeasureTheory.Measure.real
  unless actual == some `Mathlib.MeasureTheory.Measure.Lebesgue.Basic do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.MeasureTheory.Measure.Lebesgue.Basic"
#eval IO.println "BEGIN_SIGNATURE:M011"
#check @MeasureTheory.Measure.real
#eval IO.println "BEGIN_AXIOMS:M011"
#print axioms MeasureTheory.Measure.real
#eval IO.println "END_SOURCE:M011"
