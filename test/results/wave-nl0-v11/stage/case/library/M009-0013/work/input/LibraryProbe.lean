import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `MeasureTheory.IntegrableOn.integrable_indicator with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `MeasureTheory.IntegrableOn.integrable_indicator
  unless actual == some `Mathlib.MeasureTheory.Integral.IntegrableOn do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.MeasureTheory.Integral.IntegrableOn"
#eval IO.println "BEGIN_SIGNATURE:M009"
#check @MeasureTheory.IntegrableOn.integrable_indicator
#eval IO.println "BEGIN_AXIOMS:M009"
#print axioms MeasureTheory.IntegrableOn.integrable_indicator
#eval IO.println "END_SOURCE:M009"
