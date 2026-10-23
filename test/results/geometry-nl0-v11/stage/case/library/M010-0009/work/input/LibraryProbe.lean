import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `MeasureTheory.lintegral_indicator_const with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `MeasureTheory.lintegral_indicator_const
  unless actual == some `Mathlib.MeasureTheory.Integral.Lebesgue.Basic do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.MeasureTheory.Integral.Lebesgue.Basic"
#eval IO.println "BEGIN_SIGNATURE:M010"
#check @MeasureTheory.lintegral_indicator_const
#eval IO.println "BEGIN_AXIOMS:M010"
#print axioms MeasureTheory.lintegral_indicator_const
#eval IO.println "END_SOURCE:M010"
