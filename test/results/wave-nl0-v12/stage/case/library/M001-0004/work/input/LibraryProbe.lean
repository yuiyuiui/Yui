import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `Continuous.locallyIntegrable with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `Continuous.locallyIntegrable
  unless actual == some `Mathlib.MeasureTheory.Function.LocallyIntegrable do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.MeasureTheory.Function.LocallyIntegrable"
#eval IO.println "BEGIN_SIGNATURE:M001"
#check @Continuous.locallyIntegrable
#eval IO.println "BEGIN_AXIOMS:M001"
#print axioms Continuous.locallyIntegrable
#eval IO.println "END_SOURCE:M001"
