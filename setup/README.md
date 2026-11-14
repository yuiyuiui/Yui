# Adapt Yui to this computer

This is the sole setup entry for Codex. Execute it before running a new Yui
installation, to repair an invalid setup, or to change the default environment.
Do the mechanical work yourself. Ask the user only for material choices that
remain ambiguous, interactive login, or an operating-system action that you
cannot complete. Do not hand a long list of shell commands back to the user.

## Required outcome

Reach an actual READY report for the requested capability using the setup
coordinator. A download, an existing directory, a successful import Mathlib, or
an authenticated metadata request alone is not full readiness.

Current supported execution platform: macOS with sandbox-exec. Report other
platforms as unsupported before making partial system changes.

The coordinator is nl0/scripts/yui.py setup. Its --help describes internal
options for you; the user does not need to learn these options.

## 1. Inventory and bootstrap

1. Resolve this repository's absolute path. A renamed directory, spaces in its
   name, or a GitHub archive without .git must work.
2. Check macOS, Git, Python 3.11+, ripgrep, PDF extraction (pdftotext or pypdf),
   the selected Codex binary and its matching codex-code-mode-host, and Elan if
   a Lean installation is needed.
3. Reuse existing installations. Read .runtime/local-config.json if present.
   Do not search unrelated proof projects or import their instructions.
4. Install missing system dependencies using the user's existing package manager
   where possible. On a Homebrew-equipped Mac, missing Git/Python/ripgrep/Elan
   or Poppler can be installed with the corresponding formula. If Homebrew or
   system developer tools are missing, complete their official supported
   bootstrap, handing off only unavoidable interactive/OS authorization.
   Never disable TLS or install an unrelated compiler to bypass a failure.
5. Create the local Python environment and install the declared requirements:
   run Python 3.11+ on nl0/scripts/yui.py setup --bootstrap. Continue with the
   reported .venv/bin/python. Bootstrap is not a READY result.
6. Locate the native Codex executable and its own matching helper from the
   same installed distribution. Reuse the existing Codex desktop/CLI
   installation when compatible. Do not copy a helper from another release.
   Use --codex-binary, --rg-binary and --auth-home if needed. Keep credentials
   in the authentication directory; never print or copy tokens into receipts.

If a missing component needs current vendor-specific installation instructions,
consult that vendor's official documentation and execute the supported route.
Keep the user's existing installations and data.

## 2. Select the requested capability

For formalization, use --mode lean. For an explicitly natural-language-only
installation, use --mode nl0; this mode must work without Lean.

Respect a version or path already requested by the user. Otherwise reuse a
verified saved default. If no default exists, inspect local candidates with
lean-environments. Reuse one unambiguous compatible pair; with multiple choices,
ask one consolidated question for the intended Mathlib/environment and any
missing model choices. Do not silently select the newest pair.

- Local pair: --lean-root and --mathlib-root.
- Installed version: --mathlib-version (and optionally --lean-version).
- Missing requested pair: add --install. Mathlib's lean-toolchain supplies
  the matching Lean version if the user has not specified it.
- Use a fresh --directory if a conflicting shared installation already exists.

The shared tools stay outside this repository. Do not run lake update in an
existing pinned installation or overwrite old environments.

Model defaults come from the existing local configuration or config.json.
Verify advertised model/reasoning availability. When a different selection is
necessary, write a small owned JSON file containing the nl0 and lean profile
slots, then supply --profiles-file. Never silently substitute a model.

## 3. Execute adaptation and resolve its report

Run .venv/bin/python -B nl0/scripts/yui.py setup with the selected options.
The coordinator:

- Binds real host tools, checks authentication and makes a tiny isolated
  provider request using the normal native carrier.
- Registers this complete checkout as rigorous-proof, preserving an existing
  conflicting skill. Resolve a conflict with an explicit --skill-root or the
  user's existing registration; never overwrite their files.
- In Lean mode, performs real Mathlib search/read/probe, kernel inspection,
  foundation export with universes/typeclasses, and a negative axiom check.
- Atomically publishes one local configuration only after all requested checks
  pass. Failed switches preserve the previous usable configuration.

Interpret the report:

- READY: inspect mode and capabilities; proceed only for the requested scope.
- NEEDS_USER_ACTION: complete the named choice/login/OS action and repeat this
  same entry. For login, use the selected native Codex executable.
- FAILED: read the named attempt and its diagnostics, fix the actual cause and
  repeat. Do not bypass isolation or fabricate a successful check.

Evidence is under .runtime/setup-evidence/. The current report is
.runtime/setup-report.json and the usable default is .runtime/local-config.json.
They are ignored machine-local files. Do not edit tracked source files to fill
in versions, paths or credentials.

## 4. Optional external Lean libraries

Do this only when requested. Base setup does not require downloading an OpenAI
Lean repository or every available theorem library.

Build the requested library using its compatible environment and identify its
public source/build roots, namespace and entry imports. Supply --library-source,
--library-build, --library-name and repeatable --library-import to setup. The
coordinator derives the complete same-namespace source/import inventory, hashes
and compiler companion files. Existing specifications can use --lean-library.
The user should not manually compose hashes or a large manifest. Declare
external dependencies before libraries that import them; the coordinator checks
them together through the actual job context.

READY for a requested external library requires a real prepared job to read
its source through the public tools and import it through the restricted
native compiler, then validate snapshot, child context and source export.
Downloaded but unreadable/unimportable is a failure, not availability.

If another external namespace is needed, declare that attachment explicitly.
If upstream source needs a different environment, retain the existing
local-first/upstream/porting route; do not change an active job's environment.

Configured optional libraries are available as verified specifications, not
implicitly attached to every mathematical job. Attach the required library by
its configured name with --lean-library NAME when preparing that job. Repeat
setup preserves previously requested libraries; use --no-libraries only for an
explicit decision to drop them from the new default.

## 5. Run the appropriate software checks and hand back

Use selftest --group none for an NL0-only installation.
For Lean, selftest runs applicable none/current/exact tests using the chosen
environment; exact historical mismatches are reported as skips. A current
compiler failure must not be converted into a version skip. For routine
maintenance, select affected modules with tests/run_tests.py. A release-level
complete run can use selftest --all.

Before handing back, confirm the READY report, actual selected versions and
skill location. Tell the user they can now ask: Use $rigorous-proof to work on
the supplied proof. Report optional libraries not configured and historical
tests not executed. Do not call fixture-based carrier results live verification.

For a later version change, execute this same entry with the new choice.
New jobs use the new default; existing and resumed jobs keep their frozen
environment. Do not edit their job records or runtime snapshots.
