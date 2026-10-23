import Mathlib
set_option pp.universes true
set_option pp.explicit true
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `MeasureTheory.lintegral_indicator_one with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
#eval IO.println "BEGIN_SIGNATURE:M008"
#check @MeasureTheory.lintegral_indicator_one
#eval IO.println "BEGIN_AXIOMS:M008"
#print axioms MeasureTheory.lintegral_indicator_one
#eval IO.println "END_SOURCE:M008"
