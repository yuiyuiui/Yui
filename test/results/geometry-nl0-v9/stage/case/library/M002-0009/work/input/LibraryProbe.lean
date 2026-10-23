import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `MeasureTheory.lintegral_tsum with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `MeasureTheory.lintegral_tsum
  unless actual == some `Mathlib.MeasureTheory.Integral.Lebesgue.Add do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.MeasureTheory.Integral.Lebesgue.Add"
#eval IO.println "BEGIN_SIGNATURE:M002"
#check @MeasureTheory.lintegral_tsum
#eval IO.println "BEGIN_AXIOMS:M002"
#print axioms MeasureTheory.lintegral_tsum
#eval IO.println "END_SOURCE:M002"
