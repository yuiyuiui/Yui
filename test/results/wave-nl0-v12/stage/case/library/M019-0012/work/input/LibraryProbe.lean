import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `IsCompact.bddAbove_image with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `IsCompact.bddAbove_image
  unless actual == some `Mathlib.Topology.Order.Compact do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.Topology.Order.Compact"
#eval IO.println "BEGIN_SIGNATURE:M019"
#check @IsCompact.bddAbove_image
#eval IO.println "BEGIN_AXIOMS:M019"
#print axioms IsCompact.bddAbove_image
#eval IO.println "END_SOURCE:M019"
