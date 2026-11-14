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
