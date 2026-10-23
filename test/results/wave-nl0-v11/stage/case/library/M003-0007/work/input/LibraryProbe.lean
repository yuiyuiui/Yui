import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `MeasureTheory.integral_prod with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `MeasureTheory.integral_prod
  unless actual == some `Mathlib.MeasureTheory.Integral.Prod do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.MeasureTheory.Integral.Prod"
#eval IO.println "BEGIN_SIGNATURE:M003"
#check @MeasureTheory.integral_prod
#eval IO.println "BEGIN_AXIOMS:M003"
#print axioms MeasureTheory.integral_prod
#eval IO.println "END_SOURCE:M003"
