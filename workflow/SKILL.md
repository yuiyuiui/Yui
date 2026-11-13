---
name: yui-workflow
description: Route frozen Yui proof requests through natural-language review, conditional Lean formalization, or explicit checked foundation discharge.
---

# Yui public workflow

Give the Yui operator a proof, its complete target and one of three goals. Use `nl0/scripts/yui.py run` from the parent Yui installation. The `audit` entry ends after independent natural-language Audit A. The `conditional` entry continues to checked Lean assembly and Audit B. The `unconditional` entry additionally prepares the foundation registry before local authoring and checks actual discharge at the end. A residual theorem requires an explicit user decision. Each exit in [the definition](workflow.json) identifies the scope actually achieved.

The unconditional entry freezes the reviewed foundations and supplies a structured route seed. The NL0 global author can keep that seed or revise intermediate statements and edges. Local authors work against one version. A located graph defect goes back to the NL0 global author, who can publish a replacement under the same foundations. Independent Audit A seals the resulting complete graph for delivery or Lean. The native case adapter invokes the mathematical workers and checkers in the pinned Yui runtime. Their prompts, native check policies, compatible cached libraries and recovery histories remain with those workers.

The local author uses `report_graph_issue` for a missing dependency, a wrong inference interface or an incorrect intermediate statement. The report identifies the inference and the affected field. A true mathematical obstacle keeps its own outcome. A protected foundation defect uses `report_basis_defect`. Global Audit A examines the overall proof structure and sources, and local Audit A checks each inference. A changed graph must be reviewed in its new context. An identical rejected graph pauses immediately. The definition bounds distinct global repair rounds. A first-pass request records its first nonpass.

For a basis entry the global author receives a numbered graph. Each directly used foundation has one working M/E label, shared by all its consumers. Graph repairs can rename that label by B identity before the Audit A seal. The Lean translator and final exporter use the same selected revision. An author cites a staged document by its declared input ID. The receiving validator binds the actual local bytes.

## Operators

Foundation planning and Lean authoring expose the optional `consult_strategy`
tool. Omit `ids` to read a short catalog, then select any relevant IDs for
complete guidance. The query and reply contracts live in the same workflow
definition as the case. A zero-lookup run has the same proof and review gates.

The Yui case owns the process group, budget, material requests, decisions, checkpoints, delivery and cleanup. Read `yui.py status RUN`, `observe RUN` or `errors RUN` for the live owner and exact incident. Supply source bytes with `supply-material RUN --incident ID --file FILE`. Use `resume-checkpoint RUN --id ID` at a requested stage boundary. When a user says they sent the requested reference, inspect attachments actually received in the owning chat. Bind the matching file to the open incident. If there are several plausible editions, ask which one to bind. Leave the request waiting while no matching file is available. `verify-delivery RUN/delivery` rechecks the portable graph, evidence and endpoint inventory. Supply `--comparator BINARY` to build and compare the theorem package. `cleanup RUN --apply` explicitly releases owned scratch and preserves the verified delivery.

The standalone protocol CLI accepts a prepared job binding in `{"job":{"path":"…/job.json","sha256":"…"}}`. Run `python scripts/flow.py start PROTOCOL_DIR ENTRY @input.json` from this package with a fresh protocol directory, separate from the case. This runs the frozen case or reads its corresponding completed transitions. Use Yui controls against the case path for operational interaction.

## Maintenance

The private [proof-round policy](blocks/proof_rounds.py) owns graph outcomes and
retained-round reading. `FRAGMENT_ASSEMBLED` and
`GRAPH_ASSEMBLY_REPAIR_REQUIRED` both contain complete local bodies and may
enter assembly preparation; the latter keeps its failed whole-file status.
`GRAPH_REPAIR_REQUIRED` and `GRAPH_UNFINISHED` expose only partial work for
diagnosis or individually bound reuse. With no explicit selection the reader
returns the default location, including before a report exists; each consumer
still applies its own readiness gate. Final acceptance always checks actual
standalone compilation, kernel closure and the semantic authority. Portable
reader/state cases are registered in [checks.json](checks.json); the parent
repository also tests the actual frozen-interface handoff and native repair.

Install [requirements](requirements.txt) in the local Yui Python environment. Use `python scripts/flow.py check`, `plan`, `diagram` and `test` to inspect the same definition the cases execute. Edit a consumer contract at its owner, version incompatible changes, and add an independent expectation to [acceptance.json](acceptance.json) before regenerating path tests. Audit the package with the registered workflow-builder before and after a change. Run the parent Yui regression suite, including native CLI and Lean tests, before recording a new maintenance baseline. The protocol fixtures exercise every declared route using offline adapters. Real proof acceptance comes from the corresponding native reviews, Lean checks and actual output.
