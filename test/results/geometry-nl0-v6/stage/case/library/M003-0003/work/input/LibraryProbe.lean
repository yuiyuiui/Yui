import Mathlib
set_option pp.universes true
set_option pp.explicit true
open Lean Elab Command in
run_elab do
  let env ← getEnv
  match env.find? `LipschitzWith.dimH_image_le with
  | some (.thmInfo _) => pure ()
  | _ => throwError "This source is not a proved theorem declaration"
#eval IO.println "BEGIN_SIGNATURE:M003"
#check @LipschitzWith.dimH_image_le
#eval IO.println "BEGIN_AXIOMS:M003"
#print axioms LipschitzWith.dimH_image_le
#eval IO.println "END_SOURCE:M003"
