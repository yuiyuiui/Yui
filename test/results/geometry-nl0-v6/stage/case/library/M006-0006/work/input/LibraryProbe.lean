import Mathlib
set_option pp.universes true
set_option pp.explicit true
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `MeasureTheory.lintegral_mono with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
#eval IO.println "BEGIN_SIGNATURE:M006"
#check @MeasureTheory.lintegral_mono
#eval IO.println "BEGIN_AXIOMS:M006"
#print axioms MeasureTheory.lintegral_mono
#eval IO.println "END_SOURCE:M006"
