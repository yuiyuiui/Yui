# Imported Lean: local reuse before porting

Before rewriting a substantial external Lean compilation unit, the basis author,
frontier worker or interface author uses `check_imported_lean`. Proof workers can
check retained public source but cannot add new imports to a frozen context.

Select the complete original unit from an explicit stage document:

```json
{
  "source": {"document": "material-001.lean"},
  "publish": true
}
```

Alternatively use `source.evidence` with the relative path and SHA-256 returned
by a public-source reader. An exact one-based `start`/`end` range is optional;
the selected unit must include its imports and required local declarations.
Arbitrary host files, symlinks, altered digests and invented input IDs are
rejected. The original bytes and selection remain in the stage's imported-lean
records, alongside full native diagnostics.

A completed current pass returns `LOCAL_REUSED` without looking up upstream.
Reuse that unchanged checked source. A successful cached check is bound to the
exact code, actual compiler/environment and available library identities;
changed artifacts cannot silently reuse it. Explicit unproved declarations or
placeholders cannot become a checked published module.

After a definite current failure, supply the source project's declared exact
Lean and Mathlib versions. The controller chooses among verified local pairs;
ambient current paths cannot replace the requested original version. A missing
pair returns an actionable selection request, without an implicit download.
The upstream import preamble must compile before an original source failure can
be classified. Missing project modules produce `UPSTREAM_CONTEXT_REQUIRED`.
With a working context, an unchanged upstream pass requests a compatibility
port; an unchanged upstream failure requests correction plus porting. These
are native judgments under the declared versions. Ordinary source review must
still establish that those declarations match the actual source project.
Timeouts, cancellation and unknown native results never establish a source bug.

For an import failure from a retained `raw.githubusercontent.com` Lean source at
its full Git commit, the tool can shallow-fetch that revision before freeze. It
downloads the package metadata and the required source files from that tree.
A failed initial fetch has one bounded retry. Subsequent requests in the case
reuse a verified checkout of the same revision. Package metadata supplies the module
root, including nested packages and TOML source directories. For a layout the
static reader cannot resolve, pass the exact Lean import name in `module`; its
corresponding file path must agree with the pinned source. The tool builds that
module and its available same-namespace closure using restricted Lean
invocations, then binds the checked artifacts in the owned registry. Use
`bind_public:true` to request the original module name as a dependency even when
the standalone code already compiles. A failed build returns actual diagnostics
to the author. Bind additional namespaces using their checked public sources or
the explicit library attachment. The original/version branch can diagnose a
port with its own compiled context, whose artifacts stay with that environment.

For a dependency pinned with patches, pass `recipe` to `read_external_source` with
the raw GitHub URL of the module at the base commit. Use a frozen user input ID
for a `yui-lean-patch-recipe-1` JSON file with `repository`, `revision`, and
ordered `patches` entries (`path`, `sha256`). Freeze the actual `.patch` files as
inputs as well. A fixed raw GitHub build recipe may reference patches in its
own checkout. The reader also supports a pinned `lakefile.lean` with an explicit
`post_update` patch list and matching `lake-manifest.json` lock. It reads the
configuration as data. Use an explicitly frozen recipe for other build layouts.
Read and bind the patched sources before publishing that library for the first
time. Submit author-written compatibility edits through the two-environment
port procedure below.

Follow compiler, import and fetch diagnostics through `check_imported_lean`.
Where available, `wait_for_lean_dependency` accepts the outstanding check's
`receipt` if operator intervention is required. After correcting the external
condition, the operator uses `resume-error` for that incident, and the author
rechecks the dependency. Use `MISSING_SOURCE_STATEMENT` for genuinely missing
readable material required to obtain a complete statement.

Supply the complete edited unit as `candidate` with the same source selection
and upstream pins. `PORTED_CHECKED` requires its completed current native check.
A failed or incomplete recheck cannot be reused. Original and edited sources,
environments and all checks remain distinct and content-bound.

Before basis/interface freeze, `publish:true` can install the checked unit in
this case's owned public-library registry. It returns the exact import name.
The normal library reader, native path, worker context and source delivery then
use it. The registry is isolated between cases; recovery copies its exact frozen
bytes. Once a basis or interface is frozen, adding a new import requires the
existing authorized revision route. Availability does not approve a foundation,
change an allowed premise, or grant source/semantic acceptance. Normal basis,
typed-interface, native Audit B and final dependency gates remain mandatory.
