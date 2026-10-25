# Postprocessing: connect checked nodes into the source-facing Lean proof

Use one fresh **postprocessing author thread** after every required local proof
is checked. This is a serial stage per problem and consumes none of the N
parallel proof slots. The existing mapping author serves this role; its output
drives actual assembly. The **independent Audit B reviewer** is a subsequent
fresh thread. Assembly authoring, standalone compilation, kernel inspection
and semantic review have different completion states.

## Entry and immutable inputs

Require all planned proof bodies, exact interface/plan/source bindings and the
accepted NL0/Audit A authority. A missing producer or failed local job keeps
assembly blocked, even if all its consumers passed conditionally. Revalidate
the existing authority; do not rerun unchanged Audit A.

The author receives this problem's actual proof bundle, frozen contract/plan,
original H/E/M/N/P/D inventory, source-output map and own saved assembly
feedback. It may read its own checked proof bodies. Other cases, developer
history and hidden reference proofs remain unavailable. Do not preload all
background notes; retain their original node-local permissions.

## Connection rules

1. **Close the implementation DAG.** Use the frozen topological order and exact
   parameter/binder order. Supply each internal input with its actual checked
   producer; preserve implicit and instance arguments. Source-facing N outputs
   must use their recorded T realizations. Never replace a missing producer by
   an assumption, placeholder, opaque proof or changed target.
2. **Discharge every original M input.** Resolve its exact pinned declaration,
   complete general signature and actual application conditions. Supply a real
   Lean proof for the interface port, retaining required H/E. A declaration
   spelling is not a proof. Unicode name components are data, not evidence of
   a missing theorem. Actual pinned lookup and elaboration decide whether the
   named declaration exists and fits.
3. **Export the original interface.** Retain all original H/E, parameters and
   definitions; remove M as assumptions by supplying the library proofs. Do
   not change representations, domains or hypotheses to force a match. The
   generator inspects the conditional theorem's actual universe parameters.
   Those occurring in retained parameters/H/E/conclusion are inferred from
   that interface. Only implementation-only levels absent from the retained
   interface are instantiated at zero at this application site; the general
   library declarations and reviewed signatures stay intact. Compile the
   result; do not guess that implicit inference succeeded.
4. **Build a standalone artifact.** `Proof.lean` contains definitions, actual
   local proofs, connected conditional root, checked library discharges and
   final `AuditBExport.P`. It is compiled before audit instrumentation is
   appended. `assembly.json` and `assembly-compiler.json` record that real
   complete-file outcome. A conditional fragment is not this gate.
5. **Prepare actual audit evidence.** After standalone assembly passes, inspect
   full kernel signatures, actual dependencies, hidden fields and node-local
   note permissions. Save `Audit.lean`, `compiler.json`, `inspection.json`,
   correspondence, source/proof hashes and the review packet. Inspection has a
   bounded, disclosed internal computation budget. Its timeout is an inspection
   failure, not mathematical rejection or expiry of the model's wall budget.

## Repair and handoff

Use `check_draft` for actual feedback and keep the saved candidate. The result
identifies the candidate and failing layer; compiler errors precede long
printed types. `read_assembly_feedback` reads only this author's candidate,
generated Lean, full compiler output or mechanical records in bounded pages.
Follow pagination when a short excerpt is insufficient. Correct legitimate
mapping/library-application/connection errors without restarting proof authors.
Submitting the identical checked candidate reuses its exact hash-checked native
result; this does not create a semantic review or a new PASS.

An actual missing/changed interface or source premise returns to the affected
boundary. A generator/tool defect is execution engineering; report the concrete
diagnostic and preserve the draft if it is outside the author's allowed edits.
Do not report a source paper unavailable merely because a short log was cut,
or call an unlocated name-format rejection a mathematical gap. No routine
progress essay or periodic model continuation is required.

Hand off only after **standalone assembly and mechanical inspection pass**.
The independent reviewer then reads complete source/formal pairs and actual
evidence under [Audit B](audit-b.md). It receives no author's suggested verdict.
`ASSEMBLY-PASSED`, `AUDIT-B-MECHANICAL-PASSED` and a structurally accepted mapping
are distinct from the actual final Audit B PASS.
