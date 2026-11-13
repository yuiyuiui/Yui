# Per-run Lean and Mathlib selection

Every new `yui-case-job-3` formalization freezes one verified local Lean/Mathlib pair in
`job.json:lean_environment`. Pure NL0 runs freeze `null`; their source metadata
uses `NOT_SELECTED` and their host carrier needs no Lean installation. Native
library probing in an NL0 run requires an explicitly selected environment.
Use `doctor --no-lean` to check only the carrier and isolation for pure NL0.

Discover the declared shared installations with:

```sh
python -B nl0/scripts/yui.py lean-environments
```

Discovery considers `~/formalization-tools/lean-mathlib*/{lean,mathlib}`,
installed elan toolchains, and additional Mathlib roots explicitly listed in
`YUI_MATHLIB_SEARCH_PATH` (separated by the platform path separator). It does not
search unrelated research folders. Aliases of the same pair count once.
Each candidate must match Mathlib's `lean-toolchain`, have clean tracked source
and pinned dependencies, and pass an actual isolated `import Mathlib` proof.

One unambiguous pair is selected automatically. Missing, incompatible or
ambiguous choices return `LEAN_ENVIRONMENT_SELECTION_REQUIRED` before proof
work. Ask once for matched paths or the desired versions, preserving any choice
already supplied by the user. Do not silently select the newest available pair.

Pass `--lean-root /path/to/lean --mathlib-root /path/to/mathlib` to `prepare` or
`run`, or use `--lean-version 4.35.0 --mathlib-version v4.35.0` when that pair is
already installed. The environment variables `YUI_LEAN_ROOT`,
`YUI_MATHLIB_ROOT`, `YUI_LEAN_VERSION` and `YUI_MATHLIB_VERSION` provide explicit
host selections for low-level tools. A job's frozen selection takes precedence
over later host changes.

If the selected versions are missing, explicitly install them first:

```sh
python -B nl0/scripts/yui.py lean-environments --install \
  --lean-version 4.35.0 --mathlib-version v4.35.0
```

This creates a new shared directory and obtains the official Lean toolchain,
the exact Mathlib checkout and its pinned caches. `--directory` can select a new
destination. Existing directories and pinned projects are never overwritten.
An installation failure retains its partial directory for inspection; it does
not qualify the pair or authorize work. A Mathlib full commit is also accepted.

The descriptor records the binary hash, actual Lean version/toolchain, Mathlib
commit and manifest/toolchain hashes, dependency revisions and completed native
compatibility output. Parent/parallel/nested workers and case subprocesses use
the same descriptor. Native checks and public delivery retain the selected
identity. Recovery inherits the prior run's choice, never a fresh default.
Older jobs without this field retain their declared legacy scientific pins in
their executable snapshot; `toolchain/lock.json` is that historical baseline,
not a universal version requirement for new work.
The previous `yui-case-job-2` reader remains supported for those historical jobs;
a new v3 job cannot omit its selected descriptor or explicit NL0 null.

Selection establishes execution compatibility. It does not establish theorem
fidelity, mathematical correctness of an imported source, or Audit A/B success.
