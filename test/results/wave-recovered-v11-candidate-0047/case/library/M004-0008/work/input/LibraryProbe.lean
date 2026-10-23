import Mathlib
set_option pp.universes true
set_option pp.explicit false
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `IsCompact.uniformContinuousOn with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
  let actual ← findModuleOf? `IsCompact.uniformContinuousOn
  unless actual == some `Mathlib.Topology.UniformSpace.Compact do
    throwError "Declaration source module differs: actual={actual}, requested=Mathlib.Topology.UniformSpace.Compact"
#eval IO.println "BEGIN_SIGNATURE:M004"
#check @IsCompact.uniformContinuousOn
#eval IO.println "BEGIN_AXIOMS:M004"
#print axioms IsCompact.uniformContinuousOn
#eval IO.println "END_SOURCE:M004"
