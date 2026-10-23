import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `integral_bilinear_hasFDerivAt_right_eq_neg_left_of_integrable with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `integral_bilinear_hasFDerivAt_right_eq_neg_left_of_integrable
  unless actual == some `Mathlib.Analysis.Calculus.LineDeriv.IntegrationByParts do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.Analysis.Calculus.LineDeriv.IntegrationByParts"
#eval IO.println "BEGIN_SIGNATURE:M010"
#check @integral_bilinear_hasFDerivAt_right_eq_neg_left_of_integrable
#eval IO.println "BEGIN_AXIOMS:M010"
#print axioms integral_bilinear_hasFDerivAt_right_eq_neg_left_of_integrable
#eval IO.println "END_SOURCE:M010"
