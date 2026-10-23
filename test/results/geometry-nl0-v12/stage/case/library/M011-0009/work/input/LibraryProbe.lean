import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `volume_Icc with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `volume_Icc
  unless actual == some `Mathlib.MeasureTheory.Measure.Lebesgue.Basic do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.MeasureTheory.Measure.Lebesgue.Basic"
#eval IO.println "BEGIN_SIGNATURE:M011"
#check @volume_Icc
#eval IO.println "BEGIN_AXIOMS:M011"
#print axioms volume_Icc
#eval IO.println "END_SOURCE:M011"
