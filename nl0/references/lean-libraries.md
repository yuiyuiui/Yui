# Explicit non-Mathlib Lean libraries

Run [the adaptation entry](../../setup/README.md) to derive and qualify a public
library specification. `prepare` and `run` accept repeatable
`--lean-library specification.json` or a verified configured library name.
This attaches checked implementation material to a fresh job. It never changes
the pinned Lean/Mathlib environment, an active runtime, the selected proof track,
the allowed axioms, or a foundation's semantic acceptance requirements.

The operator supplies the exact source and compiled module inventory:

```json
{
  "version": "yui-lean-library-1",
  "name": "ExampleLibrary",
  "lean_version": "4.35.0",
  "mathlib_commit": "<exact installed pin>",
  "source_root": "/absolute/source/root",
  "build_root": "/absolute/olean/root",
  "imports": ["ExampleLibrary.Entry"],
  "modules": [{
    "module": "ExampleLibrary.Entry",
    "source_sha256": "<64 hexadecimal characters>",
    "olean_sha256": "<64 hexadecimal characters>"
  }]
}
```

Enumerate the complete non-Mathlib import closure. Each module maps to
`source_root/<module path>.lean` and `build_root/<module path>.olean`.
First retain a successful native build with the matching sources, toolchain,
and actual full theorem types and transitive axioms. A manifest is an inventory,
not proof that an arbitrary binary was built from the displayed source.

Preparation independently copies only enumerated files to the owned
`RUN/lean-libraries/NAME/` directory, using the normal storage reservation and
copy-on-write path. It freezes the source/olean hashes and a manifest binding
in `job.json`, and declares a short environment summary as a task input.
Library namespaces cannot shadow pinned libraries or generated exports.
Job validation rehashes the complete snapshot. Native calls check its identity
again; cached content verification is invalidated by file identity, size,
mtime, or ctime changes. Extra files and symlinks are rejected.

The offline compiler receives only these explicit library paths. Model carriers
retain their normal filesystem boundary. Source tools expose only attached
modules, with bounded views and complete retained source evidence. These are
public library sources, not another worker's private proof drafts. Bindings
follow the same explicit job and copied worker context as phase profiles.

A basis header still begins with `import Mathlib`. Immediately following it,
the author may import only modules listed in the attachment's `imports` field.
Object definitions follow those imports. All original restrictions on axioms,
theorem declarations, executable metaprogramming, and placeholders remain.
Class-2 foundations still require actual native proofs and independent review
of their printed propositions, defining environment, source, and intended uses.
Import availability grants no source fidelity or mathematical PASS.

For Lean module-system outputs, each module may declare a `companions` object
with hashes for `.olean.private`, `.olean.server`, `.ir` and `.ir.sig`. Include
the artifacts emitted by the selected compiler; omitting a required companion
will fail actual native import. Original module files and parent directories
cannot be symlinks. Resumed jobs copy the frozen bytes rather than rereading
mutable upstream sources.

Native basis/Audit B environments include portable attachment identities. Final b2lean
checks the actual closed export and transitive axioms in that same environment.
Public Lean delivery includes the complete bound library sources and manifest,
with an explicit Lake source directory and the same `autoImplicit` setting.
A missing library root file is generated deterministically from its listed
entry imports. Compiler binaries are not copied to the public delivery.
Portable verification compares the exported source hashes and library inventory;
the ordinary native build and trust checks remain necessary.

An installation update does not add a library to an existing frozen job.
Changing the library environment requires a fresh preparation and the affected
native and independent semantic reviews. Never patch active snapshots or place
unbound modules in the shared Mathlib cache. Preserve prior runs and use the
ordinary authorized lifecycle for any cancellation or continuation.

Checked imported units may enter the same availability mechanism through the
[imported-code tool](imported-lean.md) before freeze. This case-owned registry
is separate from immutable operator attachments; both contribute portable
content identities and are copied into resumed jobs and source deliveries.
