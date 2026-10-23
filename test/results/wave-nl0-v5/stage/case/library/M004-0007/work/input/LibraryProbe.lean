import Mathlib
set_option pp.universes true
set_option pp.explicit true
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `IsCompact.uniformContinuousOn_of_continuous with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
#eval IO.println "BEGIN_SIGNATURE:M004"
#check @IsCompact.uniformContinuousOn_of_continuous
#eval IO.println "BEGIN_AXIOMS:M004"
#print axioms IsCompact.uniformContinuousOn_of_continuous
#eval IO.println "END_SOURCE:M004"
