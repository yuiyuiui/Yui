import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `MeasureTheory.volume_measurePreserving_piCongrLeft with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `MeasureTheory.volume_measurePreserving_piCongrLeft
  unless actual == some `Mathlib.MeasureTheory.Constructions.Pi do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.MeasureTheory.Constructions.Pi"
#eval IO.println "BEGIN_SIGNATURE:M010"
#check @MeasureTheory.volume_measurePreserving_piCongrLeft
#eval IO.println "BEGIN_AXIOMS:M010"
#print axioms MeasureTheory.volume_measurePreserving_piCongrLeft
#eval IO.println "END_SOURCE:M010"
