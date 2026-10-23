import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `integral_deriv_mul_eq_sub_of_hasDerivAt with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `integral_deriv_mul_eq_sub_of_hasDerivAt
  unless actual == some `Mathlib.MeasureTheory.Integral.IntervalIntegral.IntegrationByParts do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.MeasureTheory.Integral.IntervalIntegral.IntegrationByParts"
#eval IO.println "BEGIN_SIGNATURE:M007"
#check @integral_deriv_mul_eq_sub_of_hasDerivAt
#eval IO.println "BEGIN_AXIOMS:M007"
#print axioms integral_deriv_mul_eq_sub_of_hasDerivAt
#eval IO.println "END_SOURCE:M007"
