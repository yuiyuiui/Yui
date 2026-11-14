# Local adaptation validation — 2026-11-14

The public installation interface is [setup/README.md](../setup/README.md).
Codex prepares dependencies, registers the complete skill, qualifies the selected
capabilities, and publishes one ignored machine-local configuration. New jobs
freeze their host, profiles and scientific environment. Switching the default
affects future jobs; existing jobs retain their bindings. Versions are not
substituted into tracked source files.

The following versions identify executed checks, not harness defaults.

| Selected Lean | Mathlib revision | Coverage |
| --- | --- | --- |
| 4.35.0 | 56a005855ea17e0b0958f73ec801ae140b0a1679 | Current-environment suite, setup, source archive and fresh installations |
| 4.32.2 | 905b95818eb32af7874a58b427f50c1711a5e96c | Exact history, explicit comparison cases, setup/switching and fixture follow-ups |

## Complete software inventory

The actual unittest loader independently enumerated 1,361 unique test IDs.
Every ID ran once across four isolated batches using the existing owned-cleanup
runner. The complete pass took 1,680.5 seconds. Its inventory had no omissions,
duplicates, unexpected tests, source changes or cancellations.

| Requirement | Tests | Execution |
| --- | ---: | --- |
| No Lean | 274 | Guarded against actual Lean resolution/compilation |
| Current environment | 1,054 | Selected 4.35.0, with an explicitly supplied 4.32.2 comparison environment |
| Exact historical pair | 33 | Explicitly selected original 4.32.2 environment |

The first complete pass had 1,355 passes and six errors in test construction:

- Five evidence-index tests combined current native evidence with an old pin in
  a generic fixture copy. The runtime correctly rejected the mismatched pin.
  The copied fixture now receives the selected pins and a matching graph hash.
- One timeout-advice test wrote the relocated historical lock into a directory
  that its miniature installation fixture had not created. The fixture now
  creates that directory.

Only tests/tooling/audit_a_fixtures.py and tests/test_native_timeout_advice.py
changed after the complete pass. All production source hashes stayed identical.
Every consumer of these corrections was rerun: test_audit_reuse,
test_evidence_index and test_native_timeout_advice, 25 tests in total. All 25
passed on 4.35.0 and again on 4.32.2. The original fixture files were unchanged.
The combined ledger accounts for all 1,361 IDs with no unresolved failure or skip.
Earlier interrupted development runs are excluded from these totals.

The version-mismatch path was also exercised through the actual runner: all 33
historical tests reported their required/current pair and skipped before their
class initialization. Ordinary current-environment failures remain failures.

Software tests use deterministic carrier/reviewer controls. These are not
mathematical reviews or live model-capability benchmarks.

## Actual integration witnesses

- The current checkout reached READY with real host/helper launch, authentication,
  requested-profile metadata and an isolated nonce-only provider request.
- A renamed source-archive copy with spaces in its path, no Yui Git metadata,
  no private configuration and no test helper directory bootstrapped its own
  Python environment and reached READY through the same entry.
- That copy prepared a public job using its saved profiles and a configured
  external-library name. Repeated setup, a failed switch preserving configuration
  bytes, an old-version switch, frozen-job readback and NL0-only setup passed.
- Real checks exercised Mathlib search/read/signature tools, the permanent
  kernel inspector, foundation export with universes/typeclasses, and rejection
  of a project axiom. Native calls on each pair could not read the other pair's
  Mathlib source directory.
- An explicit tiny external library was built, inventoried automatically, read
  through the public tools, imported and inspected in the restricted compiler,
  and checked through job snapshots, child context and source export. Disposable
  qualification tasks live outside the installation; retained copies are evidence.
- A fresh Mathlib destination downloaded its source and locked dependencies,
  restored 9,030 files from the existing local download cache, passed actual
  compilation, and supported repeated reuse. A GitHub TLS failure was recovered
  by repeating the retained owned installation.
- A separate empty Elan home downloaded the actual compiler, installed it under
  a path with spaces, compiled against the selected Mathlib, and supported
  repeated reuse. This took about 708 seconds and preserved the global Elan home.
- An actual empty authentication directory produced NEEDS_USER_ACTION without
  publishing a replacement configuration. The pypdf fallback actually extracted
  the owned PDF when the external converter was unavailable.
- Deliberate false-READY, fake-library-availability and fixed-version-filter
  mutations were rejected by independent expectations.

Elan's installed-name check precedes its path query because
[the query can install a missing override](https://github.com/leanprover/elan/blob/v4.2.3/src/elan/config.rs#L224).
An actual empty-home query confirmed that no implicit download begins; compiler
downloads belong to the explicit install step, without the short query timeout.

## Workflow Builder and limits

Workflow Builder's eight audit gates passed, including 12 registered independent
suites and 15 historical trace replays. Check, plan, generated/independent tests,
skill validation and the single existing workflow guide were refreshed. The
accepted baseline is recorded with the change; Workflow Builder itself was not
modified. [Machine-readable summary](local-adaptation-validation.json)

Clean supported-host qualification remains UNVERIFIED: no fresh macOS VM or
runner was available. These trials reused this host's system tools and Codex
authentication, and the existing Mathlib download cache. They do not establish
cold cache-server downloads, every future Lean/Mathlib release, or Linux/Windows
execution support. The actual setup entry must qualify each requested environment.
