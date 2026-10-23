import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `MeasureTheory.integrableOn_const with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `MeasureTheory.integrableOn_const
  unless actual == some `Mathlib.MeasureTheory.Integral.IntegrableOn do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.MeasureTheory.Integral.IntegrableOn"
#eval IO.println "BEGIN_SIGNATURE:M008"
#check @MeasureTheory.integrableOn_const
#eval IO.println "BEGIN_AXIOMS:M008"
#print axioms MeasureTheory.integrableOn_const
#eval IO.println "END_SOURCE:M008"
