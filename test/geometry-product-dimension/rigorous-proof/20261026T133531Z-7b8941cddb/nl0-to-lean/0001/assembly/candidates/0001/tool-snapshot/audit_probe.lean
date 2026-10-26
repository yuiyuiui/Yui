/- Trusted inspector appended after the generated proof, never a worker tool.
   Its only substitution is an array of escaped (id, selector, expected type) strings. -/
namespace NL2LeanAuditProbe
open Lean Meta Elab Command Term

private def nameOf (parts : Array String) : Name :=
  parts.foldl Name.str .anonymous

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

private def mergeUses (a b : NameSet × NameSet) : NameSet × NameSet := Id.run do
  let mut result := a
  for name in b.1.toArray do result := (result.1.insert name, result.2)
  for name in b.2.toArray do result := (result.1, result.2.insert name)
  return result

/- Distinguish actual proof use from canonical typeclass evidence inserted as
   an instance argument. Never infer this distinction from a name prefix. -/
private partial def proofUses (e : Expr) (insideInstance := false) : MetaM (NameSet × NameSet) := do
  match e with
  | .const name _ =>
    let info ← getConstInfo name
    if ← isProp info.type then
      if insideInstance then return ({}, ({} : NameSet).insert name)
      else return (({} : NameSet).insert name, {})
    return ({}, {})
  | .app .. =>
    let fn := e.getAppFn
    let mut result ← proofUses fn insideInstance
    let mut type ← inferType fn
    for arg in e.getAppArgs do
      if !type.isForall then type ← whnf type
      match type with
      | .forallE _ _ body bi =>
        result := mergeUses result (← proofUses arg (insideInstance || bi == .instImplicit))
        type := body.instantiate1 arg
      | _ => throwError "Application has no function binder in dependency inspection"
    return result
  | .lam name type body bi | .forallE name type body bi =>
    let before ← proofUses type insideInstance
    let after ← withLocalDecl name bi type fun x => proofUses (body.instantiate1 x) insideInstance
    return mergeUses before after
  | .letE name type value body _ =>
    let before := mergeUses (← proofUses type insideInstance) (← proofUses value insideInstance)
    let after ← withLetDecl name type value fun x => proofUses (body.instantiate1 x) insideInstance
    return mergeUses before after
  | .mdata _ value | .proj _ _ value => proofUses value insideInstance
  | _ => return ({}, {})

private def record (name : Name) : MetaM Json := do
  let info ← getConstInfo name
  let env ← getEnv
  let imported := env.isImportedConst name
  let uses ← if imported then pure (({} : NameSet), ({} : NameSet))
    else match info.value? (allowOpaque := true) with
      | some value => proofUses value
      | none => pure (({} : NameSet), ({} : NameSet))
  let moduleName := match env.getModuleIdxFor? name with
    | some idx => (env.header.moduleNames[idx.toNat]!).toString
    | none => env.mainModule.toString
  return Json.mkObj [
    ("name", toJson name.toString), ("kind", toJson (kindOf info)),
    ("imported", toJson imported), ("module", toJson moduleName),
    ("proof_valued", toJson (← isProp info.type)),
    ("instance_declaration", toJson (isInstanceCore env name)),
    ("proof_uses", Json.mkObj [
      ("ordinary", toJson (uses.1.toArray.map Name.toString)),
      ("instance_argument", toJson (uses.2.toArray.map Name.toString))]),
    ("type", toJson (← showType info.type)),
    ("signature", ← binderInventory info.type),
    ("levels", toJson (info.levelParams.map Name.toString)),
    ("direct_constants", toJson ((info.getUsedConstantsAsSet.toArray.qsort Name.lt).map Name.toString)),
    ("axioms", toJson ((← collectAxioms name).map Name.toString))]

private def inspect (roots : Array Name) : MetaM Json := do
  let mut pending := roots
  let mut seen : NameSet := {}
  let mut rows : Array Json := #[]
  while !pending.isEmpty do
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

private def actualType (selector : String) (parts : Array String) : TermElabM Expr := do
  if selector.startsWith "decl:" then
    return (← getConstInfo (nameOf parts)).type
  if selector.startsWith "premise:" then
    let wanted := "h_" ++ (selector.drop 8).toString
    let root ← getConstInfo `AuditBExport.P
    return ← forallTelescope root.type fun xs _ => do
      let mut context : Array Expr := #[]
      for x in xs do
        let binder ← getFVarLocalDecl x
        if binder.userName.toString == wanted then
          return ← mkForallFVars context binder.type
        context := context.push x
      throwError "Missing actual root premise {wanted}"
  throwError "Unsupported selector {selector}"

/- Universe parameter names belong to each declaration's binder scope.
   Rename them bijectively, retaining repetitions and all level expressions.
   This is alpha-equivalence, not a proof of logical equivalence. -/
private def sameSignature (actual expected : Expr) : MetaM (Bool × String) := do
  if ← withoutModifyingState <| isDefEq actual expected then
    return (true, "definitional")
  let actualParams := (collectLevelParams {} actual).params.toList
  let expectedParams := (collectLevelParams {} expected).params.toList
  if actualParams.length != expectedParams.length then
    return (false, "different_universe_binders")
  let levels := (List.range actualParams.length).map fun i =>
    Level.param (Name.mkSimple ("_yuiAuditLevel" ++ toString i))
  let equal ← withoutModifyingState <| isDefEq
    (actual.instantiateLevelParams actualParams levels)
    (expected.instantiateLevelParams expectedParams levels)
  return (equal, "bijective_universe_renaming")

elab "#nl2lean_audit_probe" : command => do
  let result ← liftTermElabM <| withOptions
      (fun o => (o.setBool `pp.all true).setBool `pp.universes true) do
    let checks : Array (String × String × String × Array String) := __AUDIT_CHECKS__
    let mut comparisons : Array Json := #[]
    let mut roots : Array Name := #[`AuditBExport.P]
    for (id, selector, expectedText, parts) in checks do
      let stx ← ofExcept <| Parser.runParserCategory (← getEnv) `term expectedText
      let expected ← Term.elabTerm stx none
      Term.synthesizeSyntheticMVarsNoPostponing
      let expected ← instantiateMVars expected
      let actual ← actualType selector parts
      let (equal, method) ← sameSignature actual expected
      comparisons := comparisons.push <| Json.mkObj [
        ("id", toJson id), ("selector", toJson selector),
        ("expected_type", toJson (← showType expected)),
        ("actual_type", toJson (← showType actual)), ("definitionally_equal", toJson equal),
        ("comparison_method", toJson method)]
      if selector.startsWith "decl:" then
        roots := roots.push (nameOf parts)
    let dependencies ← inspect roots
    return Json.mkObj [("comparisons", toJson comparisons), ("dependencies", dependencies)]
  logInfo m!"NL2LEAN_AUDIT_JSON:{result.compress}"

set_option maxHeartbeats 0 in
#nl2lean_audit_probe
end NL2LeanAuditProbe
