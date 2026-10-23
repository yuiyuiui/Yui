import Mathlib
set_option pp.universes true
set_option pp.explicit true
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `MeasureTheory.lintegral_const_mul'' with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
#eval IO.println "BEGIN_SIGNATURE:M007"
#check @MeasureTheory.lintegral_const_mul''
#eval IO.println "BEGIN_AXIOMS:M007"
#print axioms MeasureTheory.lintegral_const_mul''
#eval IO.println "END_SOURCE:M007"
