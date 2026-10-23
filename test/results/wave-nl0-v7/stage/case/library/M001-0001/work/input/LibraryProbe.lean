import Mathlib
set_option pp.universes true
set_option pp.explicit true
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `Continuous.integrable_of_hasCompactSupport with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
#eval IO.println "BEGIN_SIGNATURE:M001"
#check @Continuous.integrable_of_hasCompactSupport
#eval IO.println "BEGIN_AXIOMS:M001"
#print axioms Continuous.integrable_of_hasCompactSupport
#eval IO.println "END_SOURCE:M001"
