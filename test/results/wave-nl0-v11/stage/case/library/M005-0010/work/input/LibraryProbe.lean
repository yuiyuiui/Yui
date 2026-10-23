import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `IsCompact.prod with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `IsCompact.prod
  unless actual == some `Mathlib.Topology.Compactness.Compact do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.Topology.Compactness.Compact"
#eval IO.println "BEGIN_SIGNATURE:M005"
#check @IsCompact.prod
#eval IO.println "BEGIN_AXIOMS:M005"
#print axioms IsCompact.prod
#eval IO.println "END_SOURCE:M005"
