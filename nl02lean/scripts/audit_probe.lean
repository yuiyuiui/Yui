/- Trusted inspector for a full source or compiled-prefix wrapper, never a worker tool.
   Substitutions carry escaped checks and controller-owned module names. -/
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

private def moduleOf (env : Environment) (name : Name) : String :=
  match env.getModuleIdxFor? name with
  | some idx => (env.header.moduleNames[idx.toNat]!).toString
  | none => env.mainModule.toString

private def record (name : Name) (direct axioms : Array Name) (owned detailed : Bool) : MetaM Json := do
  let info ← getConstInfo name
  let env ← getEnv
  let imported := env.isImportedConst name
  let fields := [
    ("name", toJson name.toString), ("kind", toJson (kindOf info)),
    ("imported", toJson imported), ("project_owned", toJson owned), ("module", toJson (moduleOf env name)),
    ("proof_valued", toJson (← isProp info.type)),
    ("instance_declaration", toJson (isInstanceCore env name)),
    ("levels", toJson (info.levelParams.map Name.toString)),
    ("direct_constants", toJson (direct.map Name.toString)),
    ("axioms", toJson (axioms.map Name.toString)), ("detail", toJson (if detailed then "full" else "dependency"))]
  if detailed then
    return Json.mkObj (fields ++ [
      ("type", toJson (← showType info.type)), ("signature", ← binderInventory info.type)])
  return Json.mkObj fields

private def inspect (roots : Array Name) : MetaM Json := do
  let env ← getEnv
  let ownedModules : Array String := #[] -- YUI_OWNED_MODULES
  let mut pending := roots
  let mut seen : NameSet := {}
  let mut names : Array Name := #[]
  let mut owned : NameSet := {}
  let mut edges : NameMap (Array Name) := {}
  let mut parents : NameMap (Array Name) := {}
  let mut axiomSets : NameMap NameSet := {}
  let mut queue : Array Name := #[]
  let mut nativeQueries := 0
  let mut rows : Array Json := #[]
  while !pending.isEmpty do
    let name := pending.back!
    pending := pending.pop
    if seen.contains name then continue
    seen := seen.insert name
    let info ← getConstInfo name
    names := names.push name
    let direct := info.getUsedConstantsAsSet.toArray.qsort Name.lt
    edges := edges.insert name direct
    let project := !env.isImportedConst name || ownedModules.contains (moduleOf env name)
    let mut initial : NameSet := {}
    if project then
      owned := owned.insert name
      let mut children := direct
      if let .inductInfo value := info then
        children := children ++ value.ctors.toArray
      for child in children do
        parents := parents.insert child (((parents.find? child).getD #[]).push name)
      pending := pending ++ children
      if let .axiomInfo _ := info then initial := initial.insert name
    else
      nativeQueries := nativeQueries + 1
      for ax in ← collectAxioms name do initial := initial.insert ax
    axiomSets := axiomSets.insert name initial
    if !initial.isEmpty then queue := queue.push name
  -- Monotone propagation reaches the exact fixed point, including cycles.
  -- Imported boundary axioms use Lean's native collector once per boundary.
  let mut cursor := 0
  while cursor < queue.size do
    let child := queue[cursor]!
    cursor := cursor + 1
    let childAxioms := (axiomSets.find? child).getD {}
    for parent in (parents.find? child).getD #[] do
      let before := (axiomSets.find? parent).getD {}
      let after := childAxioms.toArray.foldl (init := before) fun acc ax => acc.insert ax
      if after.toArray.size > before.toArray.size then
        axiomSets := axiomSets.insert parent after
        queue := queue.push parent
  for name in names do
    let info ← getConstInfo name
    let detailed := roots.contains name || isInstanceCore env name ||
      (owned.contains name && ["axiom", "opaque", "constructor", "inductive"].contains (kindOf info))
    rows := rows.push (← record name ((edges.find? name).getD #[])
      (((axiomSets.find? name).getD {}).toArray.qsort Name.lt) (owned.contains name) detailed)
  return Json.mkObj [("declarations", toJson rows), ("truncated", toJson false),
    ("native_axiom_queries", toJson nativeQueries)]

private def actualType (selector : String) (parts : Array String) : TermElabM Expr := do
  if selector.startsWith "decl:" then
    return (← getConstInfo (nameOf parts)).type
  if selector.startsWith "value:" then
    let .defnInfo decl ← getConstInfo (nameOf parts) | throwError "Expected a defined proposition"
    return decl.value
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
    let mut frozenComparisons : Array Json := #[]
    let mut roots : Array Name := #[`AuditBExport.P]
    for (id, selector, expectedText, parts) in checks do
      let expected ← if expectedText.startsWith "value:" then do
        let .defnInfo value ← getConstInfo (nameOf (((expectedText.drop 6).toString.splitOn ".").toArray))
          | throwError "Expected a bound signature definition"
        pure value.value
      else do
        let stx ← ofExcept <| Parser.runParserCategory (← getEnv) `term expectedText
        Term.elabTerm stx none
      Term.synthesizeSyntheticMVarsNoPostponing
      let expected ← instantiateMVars expected
      let actual ← actualType selector parts
      let (equal, method) ← sameSignature actual expected
      let row := Json.mkObj [
        ("id", toJson id), ("selector", toJson selector),
        ("expected_type", toJson (← showType expected)),
        ("actual_type", toJson (← showType actual)), ("definitionally_equal", toJson equal),
        ("comparison_method", toJson method)]
      if id.startsWith "__frozen__" then
        frozenComparisons := frozenComparisons.push row
      else
        comparisons := comparisons.push row
      if selector.startsWith "decl:" then
        roots := roots.push (nameOf parts)
    let dependencies ← inspect roots
    return Json.mkObj [("inspection_schema", toJson "yui-kernel-inspection-2"), ("comparisons", toJson comparisons),
      ("frozen_comparisons", toJson frozenComparisons), ("dependencies", dependencies)]
  liftIO <| IO.FS.writeFile "yui-inspection.json" result.compress
  logInfo "NL2LEAN_AUDIT_FILE:yui-inspection.json"

#nl2lean_audit_probe
end NL2LeanAuditProbe
