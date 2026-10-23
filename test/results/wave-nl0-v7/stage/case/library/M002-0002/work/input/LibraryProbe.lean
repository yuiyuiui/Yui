import Mathlib
set_option pp.universes true
set_option pp.explicit true
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `intervalIntegral.integral_eq_sub_of_hasDerivAt with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
#eval IO.println "BEGIN_SIGNATURE:M002"
#check @intervalIntegral.integral_eq_sub_of_hasDerivAt
#eval IO.println "BEGIN_AXIOMS:M002"
#print axioms intervalIntegral.integral_eq_sub_of_hasDerivAt
#eval IO.println "END_SOURCE:M002"
