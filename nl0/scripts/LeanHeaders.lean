import Lean

open Lean

def describeHeader (path : String) : IO Json := do
  let source ← IO.FS.readFile path
  let (header, state, messages) ← Parser.parseHeader (Parser.mkInputContext source path)
  if messages.hasErrors then
    let first := messages.toList.find? (·.severity == MessageSeverity.error)
    return Json.mkObj [("error", toJson (← (first.getD messages.toList.head!).toString))]
  let names := (Elab.headerToImports header).map (·.module.toString)
  return Json.mkObj [("imports", toJson names), ("endBytes", toJson state.pos.byteIdx)]

def main : IO Unit := do
  let input ← IO.getStdin
  let output ← IO.getStdout
  repeat
    let line ← input.getLine
    if line.isEmpty then break
    let answer ← match Json.parse line >>= fromJson? (α := Array String) with
      | .ok paths => pure (toJson (← paths.mapM describeHeader))
      | .error error => pure (Json.mkObj [("error", toJson error)])
    output.putStrLn answer.compress
    output.flush
