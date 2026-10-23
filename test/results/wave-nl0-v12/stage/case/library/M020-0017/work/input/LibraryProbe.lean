import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `Continuous.aestronglyMeasurable with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `Continuous.aestronglyMeasurable
  unless actual == some `Mathlib.MeasureTheory.Function.StronglyMeasurable.AEStronglyMeasurable do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.MeasureTheory.Function.StronglyMeasurable.AEStronglyMeasurable"
#eval IO.println "BEGIN_SIGNATURE:M020"
#check @Continuous.aestronglyMeasurable
#eval IO.println "BEGIN_AXIOMS:M020"
#print axioms Continuous.aestronglyMeasurable
#eval IO.println "END_SOURCE:M020"
