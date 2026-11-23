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
the standalone code already compiles. A failed build identifies the actual failed module and returns a reference to its
complete diagnostic and, when available, its original Git source. Call
`read_imported_lean_failure` with that build receipt to read the source or
diagnostic. For an unbound external import, the reply names the missing module.

After selecting the complete natural-language basis route, submit the full edited
module with `bind_public:true`, `source:{"failure": BUILD_RECEIPT}` and
`candidate`. Yui compiles and inspects the edited unit in the current environment,
registers it under its original module name, and retains its source origin. There
is no prerequisite build in the source project's environment. Recheck the consumer
after registering the fixed module.

Use `read_external_source` with `git` containing the GitHub `repository`,
full `revision`, exact `source_path`, and optional Lean `module`. Fixed GitHub
blob and raw links also select this controlled checkout. To apply an existing
or newly written diff, supply its complete text in the ordered `patches` list.
Use the same patch list for files from that checkout. Lake configuration is
read as data. The submitted source and its compiled files are used in review
and delivery.

Follow compiler, import and fetch diagnostics through `check_imported_lean`.
A failed dependency leaves the author working. An unchanged candidate that
failed deterministically returns its previous diagnostic. Continue another
foundation or select a checked alternative. `wait_for_lean_dependency` accepts an outstanding receipt that
requests access authorization or approval of a genuinely unavailable declared
upstream pair. After addressing that action, the operator uses `resume-error`
for the incident and the author rechecks the dependency. Use
`MISSING_SOURCE_STATEMENT` for missing readable material needed for a complete
statement.

Before basis/interface freeze, `publish:true` can install the checked unit in
this case's owned public-library registry. It returns the exact import name.
The normal library reader, native path, worker context and source delivery then
use it. The registry is isolated between cases; recovery copies its exact frozen
bytes. Once a basis or interface is frozen, adding a new import requires the
existing authorized revision route. Availability does not approve a foundation,
change an allowed premise, or grant source/semantic acceptance. Normal basis,
typed-interface, native Audit B and final dependency gates remain mandatory.
