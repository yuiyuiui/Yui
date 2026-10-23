import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `MeasureTheory.integral_zero with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `MeasureTheory.integral_zero
  unless actual == some `Mathlib.MeasureTheory.Integral.Bochner.Basic do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.MeasureTheory.Integral.Bochner.Basic"
#eval IO.println "BEGIN_SIGNATURE:M015"
#check @MeasureTheory.integral_zero
#eval IO.println "BEGIN_AXIOMS:M015"
#print axioms MeasureTheory.integral_zero
#eval IO.println "END_SOURCE:M015"
