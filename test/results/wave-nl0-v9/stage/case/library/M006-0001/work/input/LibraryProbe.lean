import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `hasDerivAt_integral_of_dominated_loc_of_deriv_le with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `hasDerivAt_integral_of_dominated_loc_of_deriv_le
  unless actual == some `Mathlib.Analysis.Calculus.ParametricIntegral do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.Analysis.Calculus.ParametricIntegral"
#eval IO.println "BEGIN_SIGNATURE:M006"
#check @hasDerivAt_integral_of_dominated_loc_of_deriv_le
#eval IO.println "BEGIN_AXIOMS:M006"
#print axioms hasDerivAt_integral_of_dominated_loc_of_deriv_le
#eval IO.println "END_SOURCE:M006"
