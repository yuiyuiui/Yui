import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `IsCompact.isBounded with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `IsCompact.isBounded
  unless actual == some `Mathlib.Topology.MetricSpace.Bounded do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.Topology.MetricSpace.Bounded"
#eval IO.println "BEGIN_SIGNATURE:M016"
#check @IsCompact.isBounded
#eval IO.println "BEGIN_AXIOMS:M016"
#print axioms IsCompact.isBounded
#eval IO.println "END_SOURCE:M016"
