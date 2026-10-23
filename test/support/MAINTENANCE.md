# Test maintenance record

This is maintained engineering documentation, not a mathematical test result or
a document supplied to measured model workers.

## Repairs carried into the reset

The earlier local repair separates the serial NL0/preparation/review lane from
per-case Lean proof-worker slots; records actual review coverage and located
blockers; preserves drafts and source boundaries; checks same-case incremental
audit evidence; and distinguishes acceptance, execution health and measured
usage. It also fixes original/copy hash comparison in the workflow adapter.
A small pinned source catalog reuses checked metadata, not mathematical
application verdicts. Review correctness and speedup remain unestablished.

The reset consolidates each exercise into one problem-and-proof input and
removes previous runs and acceptance artifacts as explicitly requested.
Deleted run logs are not current evidence. The harness still requires fresh
actual A/B acceptance under unchanged completeness and source-fidelity rules.

The cleanup implementation adds:

- Scoped generated-output roots and a test-start exclusion lock.
- PID/start/group identities for controllers and children; cancellation followed
  by confirmed graceful or forced stop before deletion.
- Paired controller/output and temporary-workspace ownership records, including
  standalone model carriers. They are controller metadata, never task inputs.
- Automatic removal of short-lived Lean-check, helper, interface and Audit B
  build directories after their durable outputs have been copied.
- Fail-closed handling of corrupt ownership, symlink roots and unconfirmed
  shutdown, plus idempotent cleanup. Other repositories and shared tools remain
  outside the deletion scope.
- Git ignore rules for generated runs, replacing historical per-run exceptions.

The desktop chat Stop button is still not wired to independent CLI processes.
Use the scoped cancel/cleanup command.

## Validation

On 2026-10-24 (Asia/Shanghai), the offline suites passed:

| Suite | Tests | Elapsed seconds |
| --- | ---: | ---: |
| Core runtime | 154 | 63.291 |
| Translation | 117 | 176.440 |
| Test support, including cleanup controls | 44 | 34.445 |
| Total distinct software controls | 315 | |

The final cleanup-specific suite was rerun after its cancellation refinement:
eight controls passed in 8.481 seconds. They cover actual owned parent/child
processes in separate sessions, an unrelated live process, stale PID identity,
SIGTERM-resistant forced shutdown, corrupted markers, symlink escape, unknown
locks, confirmed-stop failure, and repeated cleanup. Test-start lock behavior
and single-digit process-start dates are also checked.

Skill validation, pinned-environment doctor and Git whitespace checks passed.
The cleanup removed the old mathematical/core-control output roots (about
2.2 GiB of working-tree test output); no matching test process or verifiably
owned carrier temporary directory remained at cleanup time. This does not
claim deletion of unrelated temporary folders from other repositories.
Case directories each retain only their fixed problem.md.
No model test, benchmark or new exercise formalization is run by this operation.

## Mathematical input preparation

The statements and source interpretations were consolidated from the existing
case files. The user-approved nonempty compact-set and uniform perturbation-
support interpretations are retained. The Lie proof retains the arbitrary-
lattice localization/matrix-unit route, including characteristic 2 and highest
weight zero. The geometry proof spells out the covering/slicing argument;
the PDE proof justifies the actual integrals and boundary terms.

These proofs are fixed source inputs for a future independent NL0/A and Lean/B
run, not audit receipts. Author preparation used rigorous-proof-development and
mathematical-writing; personal skills/history are not future test inputs.

An author-side Research Cognition query selected algebra-representation 0.21.0
and pde-continuum 0.94.0 with unrated caller selection and low coverage. The
returned unrelated AIM heuristic cards were not used. No reusable method or
bridge was selected. This context is excluded from measured task manifests.
The route receipt below is authoring provenance only:

```json
{
  "schema_version": 2,
  "navigation": {
    "implementation": "domain-object-task-v3",
    "profile_version": 1,
    "profile_fingerprint": "sha256:139150f47742752b5aab2f563353d261b6fa5ad14408c2a699b9cf6c0c58b2c0",
    "aliases": {
      "state": "present",
      "version": 1,
      "fingerprint": "sha256:396edc124d17b1d893cd2f1806ed9eac179525e6f132df95c4577b5ade6caa84"
    }
  },
  "route_status": "selected",
  "scope": {
    "query_fingerprint": "sha256:049a4ced3b0d54d0",
    "matched_terms": [
      "caller semantic assertion"
    ]
  },
  "selected_experts": [
    {
      "id": "algebra-representation",
      "version": "0.21.0",
      "fingerprint": "sha256:6410f96877e715c7",
      "status": "active"
    },
    {
      "id": "pde-continuum",
      "version": "0.94.0",
      "fingerprint": "sha256:aa4af61dec0e210e",
      "status": "active"
    }
  ],
  "confidence": "unrated",
  "coverage_confidence": "low",
  "cards": [
    {
      "id": "aim-411-case-context",
      "version": "0.1.0"
    },
    {
      "id": "aim-380-case-context",
      "version": "0.1.0"
    },
    {
      "id": "aim-416-case-context",
      "version": "0.1.0"
    },
    {
      "id": "aim-379-case-context",
      "version": "0.1.0"
    }
  ],
  "selected_methods": [],
  "method_confidence": "low",
  "method_cards": [],
  "skill_bindings": [],
  "bridges": [],
  "scope_warning_ids": [],
  "skip_reason": null,
  "invalidation_conditions": [
    "query_scope_changed",
    "governing_equation_or_target_claim_changed",
    "physical_regime_scaling_geometry_or_normalization_changed",
    "representation_or_method_family_changed",
    "selected_expert_manifest_or_retrieved_artifact_version_changed",
    "selected_method_manifest_or_retrieved_artifact_version_changed",
    "receipt_missing_after_continuation_or_compaction",
    "navigation_implementation_or_profile_changed",
    "routing_alias_content_or_version_changed",
    "active_expert_catalog_changed_after_caller_semantic_selection"
  ],
  "selection_provenance": {
    "basis": "caller_semantic",
    "decision": "select",
    "expert_ids": [
      "algebra-representation",
      "pde-continuum"
    ],
    "confidence_kind": "caller_assertion_not_calibrated",
    "semantic_review_required": false,
    "inference_performed_by_gateway": false,
    "authenticated_user_intent": false,
    "task_summary": "Consolidate three fixed exercise proofs, with particular attention to arbitrary integral lattices and differentiation under the wave-map energy integral.",
    "rationale": "The two selected domains address the delicate representation and analytic applicability steps. The geometry proof retains its existing covering/slicing route; no expert output is accepted as a proof or passed into model test contexts.",
    "query_fingerprint": "sha256:82c50f14939478e8d92a0baa0f7ac5e7c6556feeceea7118a779e067f1f9fd4c",
    "catalog_fingerprint": "sha256:40aef8b443586b5099d3bd1f357d23ab3080c048040875b34122ca8851a52d3e",
    "verification": "query_catalog_bindings_and_active_eligibility_only"
  },
  "deterministic_baseline": {
    "candidates": [],
    "selected_expert_ids": [],
    "heuristic_strength": "low",
    "confidence_kind": "heuristic_uncalibrated",
    "semantic_review_required": true
  },
  "confidence_kind": "caller_assertion_not_calibrated"
}
```
