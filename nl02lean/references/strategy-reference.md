# Strategy references across Lean and Mathlib versions

Every card in the basis and Lean banks is available as a reference regardless
of the current task's Lean/Mathlib version. Reference lookup itself needs no
selected Lean installation. Existing author permissions, optional use, bounded
responses and immutable bank snapshots still apply.

Each catalog entry and full card discloses `reference_environments`, pairing a
Lean version with an exact Mathlib revision. `basis: historical_configuration`
describes the recorded reference context. It does not claim the procedure was
compiled or proven effective in that environment. The current curated cards
retain the Lean 4.32.2 / Mathlib 905b95818eb32af7874a58b427f50c1711a5e96c
configuration present in their historical repository revisions.

Current replies use `StrategyReply@2` and explicitly carry `reference_only` and
`current_environment_verification_required`. A reader must adapt APIs, syntax,
types and hypotheses and check its actual implementation in the task's selected
environment. Reading a card never grants a premise, review verdict, frozen
interface or proof acceptance. The historical `StrategyReply@1` contract is
retained for prior snapshots. New bank indexes use format 3.

Explicit ID lookup can read every card. Ranked search still reports missing
prerequisites and can omit a recommendation because of relevance or reported
contraindications; source/current version differences never exclude it. Frozen
ST020 native-timeout advice uses the same cross-version policy and does not
turn a failed native check into a pass.

## Acceptance witnesses

| User requirement | Behavioral witness |
| --- | --- |
| All 22 cards remain available under old, new, unlisted and Lean-free contexts | `test_bank_versions.CrossVersionReferences.test_every_card_is_listed_and_readable_for_old_new_unlisted_and_no_lean` |
| Both catalog and complete-card output disclose paired source versions | The same host consumer test, plus the catalog/full-card origin cases in `workflow/tests/test_strategy_reference_versions.py` |
| Lookup never selects a compiler or changes the task environment | `test_reference_lookup_never_selects_or_queries_a_native_environment`; the actual public-entry selected-environment control |
| Ranked search and ST020 follow the same policy | `test_ranked_search_keeps_reference_versions_without_using_them_as_a_filter`; `test_timeout_advice_is_available_cross_version_without_accepting_the_failure` |
| Advice cannot provide proof authority | `PairedReference.test_reading_a_reference_cannot_supply_a_proof_handoff`, plus actual native-timeout submission controls |
| Unknown IDs, malformed provenance and changed snapshots remain explicit failures | Host unknown-ID/corruption controls and portable missing-pair/authority controls |
| A newer actual environment can read old-context advice and still compile/export with its own selection | `test_lean_environment.SelectedEnvironment.test_real_public_entry_uses_its_selected_pair_through_delivery_and_cleanup`, including real native clients, Lean, cleanup and fresh source rebuilding |

These are software acceptance checks. Native-provider responses and semantic
review judgments in the integration fixture are scripted; Lean compilation is
real. Historical configuration provenance is not an independent effectiveness
study or a research-theorem benchmark rerun.

This change covers bank references. Cross-version theorem-metadata-cache
handling and general test-environment parameterization remain separate work;
passing these checks does not establish complete version independence of Yui.
