import Lean
import YuiAdaptedModule

open Lean Elab Command in
run_cmd do
  let env ← getEnv
  for (name, idx) in env.const2ModIdx do
    if env.header.moduleNames[idx.toNat]!.toString == "YuiAdaptedModule" then
      for axiomName in ← collectAxioms name do
        unless [`propext, `Classical.choice, `Quot.sound].contains axiomName do
          throwError "{name} uses unpermitted axiom {axiomName}"
