import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `IsCompact.measure_lt_top with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `IsCompact.measure_lt_top
  unless actual == some `Mathlib.MeasureTheory.Measure.Typeclasses.Finite do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.MeasureTheory.Measure.Typeclasses.Finite"
#eval IO.println "BEGIN_SIGNATURE:M012"
#check @IsCompact.measure_lt_top
#eval IO.println "BEGIN_AXIOMS:M012"
#print axioms IsCompact.measure_lt_top
#eval IO.println "END_SOURCE:M012"
