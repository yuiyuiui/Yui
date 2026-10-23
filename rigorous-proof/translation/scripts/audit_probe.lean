/- Trusted inspector appended after the generated proof, never a worker tool.
   Its only substitution is an array of escaped (id, selector, expected type) strings. -/
namespace NL2LeanAuditProbe
open Lean Meta Elab Command Term

private def nameOf (text : String) : Name :=
  (text.splitOn ".").foldl Name.str .anonymous

private def kindOf : ConstantInfo → String
  | .axiomInfo _ => "axiom"
  | .defnInfo _ => "definition"
  | .thmInfo _ => "theorem"
  | .opaqueInfo _ => "opaque"
  | .inductInfo _ => "inductive"
  | .ctorInfo _ => "constructor"
  | .recInfo _ => "recursor"
  | .quotInfo _ => "quotient"

private def binderKind : BinderInfo → String
  | .default => "explicit"
  | .implicit => "implicit"
  | .strictImplicit => "strict_implicit"
  | .instImplicit => "instance"

private def showType (e : Expr) : MetaM String := do
  return (← ppExpr e).pretty

private def binderInventory (type : Expr) : MetaM Json :=
  forallTelescope type fun xs body => do
    let mut rows : Array Json := #[]
    for x in xs do
      let d ← getFVarLocalDecl x
      rows := rows.push <| Json.mkObj [
        ("name", toJson d.userName.toString), ("kind", toJson (binderKind d.binderInfo)),
        ("type", toJson (← showType d.type)), ("proof_valued", toJson (← isProp d.type))]
    return Json.mkObj [("binders", toJson rows), ("result", toJson (← showType body))]

private def record (name : Name) : MetaM Json := do
  let info ← getConstInfo name
  let env ← getEnv
  let imported := env.isImportedConst name
  let moduleName := match env.getModuleIdxFor? name with
    | some idx => (env.header.moduleNames[idx.toNat]!).toString
    | none => env.mainModule.toString
  return Json.mkObj [
    ("name", toJson name.toString), ("kind", toJson (kindOf info)),
    ("imported", toJson imported), ("module", toJson moduleName),
    ("proof_valued", toJson (← isProp info.type)),
    ("type", toJson (← showType info.type)),
    ("signature", ← binderInventory info.type),
    ("levels", toJson (info.levelParams.map Name.toString)),
    ("direct_constants", toJson ((info.getUsedConstantsAsSet.toArray.qsort Name.lt).map Name.toString)),
    ("axioms", toJson ((← collectAxioms name).map Name.toString))]

private def inspect (roots : Array Name) : MetaM Json := do
  let mut pending := roots
  let mut seen : NameSet := {}
  let mut rows : Array Json := #[]
  while !pending.isEmpty && seen.size < 10000 do
    let name := pending.back!
    pending := pending.pop
    if seen.contains name then continue
    seen := seen.insert name
    let info ← getConstInfo name
    rows := rows.push (← record name)
    if !(← getEnv).isImportedConst name then
      pending := pending ++ info.getUsedConstantsAsSet.toArray
      if let .inductInfo value := info then
        pending := pending ++ value.ctors.toArray
  return Json.mkObj [("declarations", toJson rows), ("truncated", toJson (!pending.isEmpty))]

private def actualType (selector : String) : TermElabM Expr := do
  if selector.startsWith "decl:" then
    return (← getConstInfo (nameOf (selector.drop 5).toString)).type
  if selector.startsWith "premise:" then
    let wanted := "h_" ++ (selector.drop 8).toString
    let root ← getConstInfo `Translation.P
    return ← forallTelescope root.type fun xs _ => do
      let mut context : Array Expr := #[]
      for x in xs do
        let binder ← getFVarLocalDecl x
        if binder.userName.toString == wanted then
          return ← mkForallFVars context binder.type
        context := context.push x
      throwError "Missing actual root premise {wanted}"
  throwError "Unsupported selector {selector}"

elab "#nl2lean_audit_probe" : command => do
  let result ← liftTermElabM <| withOptions
      (fun o => (o.setBool `pp.all true).setBool `pp.universes true) do
    let checks : Array (String × String × String) := __AUDIT_CHECKS__
    let mut comparisons : Array Json := #[]
    let mut roots : Array Name := #[`Translation.P]
    for (id, selector, expectedText) in checks do
      let stx ← ofExcept <| Parser.runParserCategory (← getEnv) `term expectedText
      let expected ← Term.elabTerm stx none
      Term.synthesizeSyntheticMVarsNoPostponing
      let expected ← instantiateMVars expected
      let actual ← actualType selector
      let equal ← isDefEq actual expected
      comparisons := comparisons.push <| Json.mkObj [
        ("id", toJson id), ("selector", toJson selector),
        ("expected_type", toJson (← showType expected)),
        ("actual_type", toJson (← showType actual)), ("definitionally_equal", toJson equal)]
      if selector.startsWith "decl:" then
        roots := roots.push (nameOf (selector.drop 5).toString)
    let dependencies ← inspect roots
    return Json.mkObj [("comparisons", toJson comparisons), ("dependencies", dependencies)]
  logInfo m!"NL2LEAN_AUDIT_JSON:{result.compress}"

#nl2lean_audit_probe
end NL2LeanAuditProbe
