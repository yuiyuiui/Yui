import Mathlib
set_option pp.universes true
set_option pp.explicit true
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `IsCompact.isBounded with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
#eval IO.println "BEGIN_SIGNATURE:M005"
#check @IsCompact.isBounded
#eval IO.println "BEGIN_AXIOMS:M005"
#print axioms IsCompact.isBounded
#eval IO.println "END_SOURCE:M005"
