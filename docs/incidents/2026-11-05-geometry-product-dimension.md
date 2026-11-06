# Geometry product-dimension: cancelled unconditional run

Run: `20261105T120350Z-de9cce1dea`.

The unconditional full workflow reached a valid retained Audit A receipt and
partial local Lean proofs, then paused during internal interface repair. The
user cancelled it. Audit B and b2lean did not complete. Owned process exit was
verified and cleanup returned `CLEANED`.

The detailed retrospective is stored beside the original run:

- [Incident report](https://github.com/yuiyuiui/Yui-results/blob/d38d546484fd8f36a7d2a232f85c027773bbf755/test_uncond/geometry-product-dimension/rigorous-proof/20261105T120350Z-de9cce1dea/incident-analysis/INCIDENT_REPORT.md)
- [Exact evidence appendix](https://github.com/yuiyuiui/Yui-results/blob/d38d546484fd8f36a7d2a232f85c027773bbf755/test_uncond/geometry-product-dimension/rigorous-proof/20261105T120350Z-de9cce1dea/incident-analysis/EVIDENCE_APPENDIX.md)
- [Stage timeline](https://github.com/yuiyuiui/Yui-results/blob/d38d546484fd8f36a7d2a232f85c027773bbf755/test_uncond/geometry-product-dimension/rigorous-proof/20261105T120350Z-de9cce1dea/incident-analysis/STAGE_TIMELINE.md)

These links pin the published evidence snapshot. Absolute local paths inside
the historical records describe their original execution and are not rewritten.

The report separates three findings:

1. Copied generic dependency propositions elaborated with unrelated rigid
   universes, preventing intended consumer applications.
2. The internal repair contract preserved the header but supplied no working
   declaration-universe/dependency-specialization field for the attempted repair.
3. After cancellation and verified process exit, historical pause counts blocked
   the entry's standard final report, while owned cleanup succeeded.

The report also corrects an owner progress count: ten proof nodes were planned;
the reported thirteen mixed proof and diagnostic activity. It preserves exact
compiler/diagnostic evidence, configuration bindings, partial usage, known limits,
and proposed acceptance tests. The finalization predicate was reproduced without
model or Lean execution. No software repair or new experiment is claimed.

Use the run's frozen runtime and the report's file manifest to diagnose this
attempt. Do not treat the current checkout as proof of the historical version,
modify bound evidence, or automatically resume/replay this cancelled run.

## Subsequent verification: November 6

A fresh unconditional run, `20261106T125831Z-222bcbd7a3`, completed with the
shared runtime at `8bd6c72bd0123a830f95d1ee81535a050909614c` and normal automatic
repair enabled. All 14 local Lean proof nodes completed, the bound Audit A and
Audit B receipts passed, and b2lean accepted `YuiClosed.P` with no residual
class-4 dependency. Recorded elapsed time was 4,203 seconds; observed usage was
17,831,046 tokens with `PARTIAL` accounting coverage.

The repairs address shared artifact protocols, declaration universes,
dependency applications and error recovery. They do not dispatch a special
product-dimension solution. At closeout, all 163 corresponding files in the
frozen `nl0`/`nl02lean` runtime matched the shared installation byte for byte.
Existing acceptance receipts were revalidated without a new model or proof
run; no owned process or registered temporary workspace remained. This is an
end-to-end regression result for this input, not proof of all workflow cases.

[Outcome and cleanup verification](https://github.com/yuiyuiui/Yui-results/blob/d38d546484fd8f36a7d2a232f85c027773bbf755/test_uncond/geometry-product-dimension/rigorous-proof/20261106T125831Z-222bcbd7a3/OWNER_CLOSEOUT_VERIFICATION.json)
· [Published result index](https://github.com/yuiyuiui/Yui-results/blob/d38d546484fd8f36a7d2a232f85c027773bbf755/docs/run-records-2026-11-06.md).
