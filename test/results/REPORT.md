# Initial exercise and clean-runtime test report

Status: **no full mathematical case has passed**. This is a development campaign, not a performance benchmark.

## Scope and fixed profile

The repository contains one `rigorous-proof` skill with NL0/Audit A and typed translation/Audit B stages. The requested profile is gpt-6-luna, high reasoning, Standard service. It uses the existing Codex subscription. Auto concurrency resolves to a disclosed fallback of two because the backend hard limit is unknown. This is not a claim about the subscription maximum.

Every mathematical model stage ran in a fresh home/state/workspace through the request-normalizing relay. Only the explicit documents listed in that stage input manifest and the selected Yui rules were available. The developer/controller had workspace history; it was not itself a clean measured model. Developer/source-context preparation costs remain UNMEASURED.

## Exercise status

| Exercise | Source and exact issue | Current acceptance |
| --- | --- | --- |
| Geometry product dimension | Stein–Shakarchi, Real Analysis, Chapter 7, problem 9, p.388. Hausdorff dimension identified. Empty E conflicts with the pinned dimH(empty)=0 convention. Nonempty version awaits confirmation. | Not run under an altered target; A/Lean/B not passed |
| Lie-module irreducibility | Humphreys, GTM 9, section 27, exercise 7, p.164; the exercise-list convention specifies sl(2). Arbitrary admissible lattices, lambda=0 and characteristic 2 are retained. | Candidate natural proof and bounded repair review completed; latest NL0 author stopped before structural acceptance. A/Lean/B not run |
| Wave-map energy | Evans, PDE, second edition, section 12.6, exercise 14, p.694. Literal zero compact support contradicts the sphere condition from exercise 13. Relative compact support awaits confirmation. | No vacuous proof counted; A/Lean/B not passed |

Textbook PDFs were used only to identify definitions/exercises; no online exercise solution was supplied. Full copyrighted books are not distributed. Source identity, locations and download hashes are in each case source-context file.

## Actual mathematical model stages

Candidate JSON submission is not mathematical acceptance. The corrected natural proof is still unaudited. Every failed/interrupted attempt remains available.

| Run | Model-stage wall seconds | Outcome | Provider total tokens |
| --- | ---: | --- | ---: |
| [lie-context-proof-v1](lie-context-proof-v1/) | 44.98 | ACCEPTED | 17023 |
| [lie-nl0-v1](lie-nl0-v1/) | unavailable | RULE_ENTRY_NOT_DISCOVERABLE | >= 312018 (partial) |
| [lie-nl0-v2](lie-nl0-v2/) | 33.32 | VALIDATOR_RETURN_SHAPE | >= 135704 (partial) |
| [lie-nl0-v3](lie-nl0-v3/) | 61.14 | ARTIFACT_IDENTITY_NOT_DISCLOSED | 183748 |
| [lie-nl0-v4](lie-nl0-v4/) | 64.08 | SUBSTANTIVE_GAP | 229221 |
| [lie-nl0-v5](lie-nl0-v5/) | 140.43 | LOGIC_ENUM_NOT_DISCLOSED | 489473 |
| [lie-nl0-v6](lie-nl0-v6/) | 60.04 | SUBSTANTIVE_GAP | 199922 |
| [lie-obstacle-triage-v1](lie-obstacle-triage-v1/) | 46.65 | ACCEPTED | 67572 |

Usage comes from unique actual provider response IDs. Input includes cached tokens; output includes reasoning tokens. Neither subcategory is added again. Interrupted responses without terminal usage make the run partial, not zero-cost. `status.json` and each usage ledger retain all fields and coverage. Repeated request context is charged each time as reported by the provider.

### Development faults found and repaired

1. The Yui reader had no discoverable entry/path catalog. The prompt now supplies SKILL.md and all frozen rule paths.
2. The new NL0 adapter initially unpacked the parent checker result incorrectly. A positive/negative structural control caught this; the adapter now reads its summary correctly.
3. The structural checker required an undisclosed case ID. Exact case identity and controller-bound pins are now explicit in the initial contract.
4. The logical-rule guide omitted the exact machine enum names. The document now enumerates them, and the prompt obtains the same list from the checker constants. The accepted logical rules did not change.

These attempts are controller faults, not healthy model-budget exhaustion. Their original logs and incident records are retained. No failed run is retroactively promoted to a pass.

### Remaining mathematical-workflow issue

The initial draft wrongly restricted localized lattice coordinates to Q. A fresh review supplied a same-route repair using coordinate submodules of C; this was not a new core proof route. The next NL0 attempt stopped on the standard fact that a finitely generated torsion-free rank-one module over Z_(p) is free. It made no library search or signature probe before declaring a gap.

This is **not an established substantive gap in the exercise**, and it is not a disproof. It shows that this model/prompt workflow can stop too conservatively on an ordinary missing helper or source. The stopped record is retained; no audit PASS or Lean result was manufactured. Completing the helper/source work and rechecking the gap triage is required before claiming a full-flow pass. The latest attempt stopped early, so it is not MODEL_BUDGET_EXHAUSTED.

## Independent engineering controls

- The migrated/adversarial regression suites passed; their exact final count and logs are under `../../rigorous-proof/tests/results/`.
- Native boundary control compiled an allowed Lean proof and rejected a direct attempt to read an external canary file with operation-not-permitted. The canary content did not escape.
- The core was copied outside both repositories. Environment discovery and translation/library regressions passed there. Initial mistaken verification commands remain recorded separately.
- Actual isolated model workers proved two historical norm/supremum conditional obligations concurrently, then assembled them through Lean. Observed peak was two; usage was 32,765 provider tokens. This is a carrier/assembly control, not one of the three new mathematical tests, not Audit B and not a speedup experiment.
- Actual request readback confirmed gpt-6-luna/high and terminal service tier default on completed stages. CLI-injected foreign instruction items were removed before transmission. Header values containing credentials were never logged.
- Skill format validation passed. The original NL2Lean checkout and production skill were not edited.

Observable isolation checks do not prove anything about undisclosed provider state or pretraining. They verify the local tool/filesystem boundary and actual transmitted inputs. Model self-report is supplementary.

## Benchmark boundary and next actions

No papers are selected and no direct/sequential/parallel performance benchmark has run. The benchmark directory supplies a protocol, profile and result schema, not scores. A frozen-port `--arm direct` control is not a direct original-paper baseline.

Before full mathematical acceptance: confirm the geometry/PDE target conventions; finish a valid Lie NL0 and fresh Audit A; author/review typed interfaces; prove and assemble the actual exercise nodes; then complete fresh Audit B. Do not label the repository as full-case validated before these gates pass.
