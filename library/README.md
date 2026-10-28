# Optional personal Mathlib library

This directory is an optional user-maintained search catalog, separate from the
NL0 and Lean runtime code. After a formalization run, you may add useful Mathlib theorems encountered
during that work. Over time, the names and search tags can form a convenient
index for your own mathematical fields. Maintenance is optional and explicit;
Yui does not harvest completed runs or update this directory automatically.

The repository ships only three demonstrations:

| Declaration | Example search topic |
| --- | --- |
| `isCompact_singleton` | Compactness of a singleton |
| `MeasureTheory.integral_finsetSum` | Integrating a finite sum |
| `Module.finrank_pi_fintype` | Dimension of a finite product of modules |

These are examples, not a comprehensive index or a list of the only permitted
theorems. Direct Mathlib search, source reading and native signature queries
remain available when this catalog is absent or has no matching entry.

## Contents and use

- `foundations.json` contains declaration names, defining modules, search tags,
  and references to native-query evidence. Its historical filename does not
  mean that the entries are new axioms or automatically applicable premises.
- `evidence/*.json` preserves complete native-query receipts: the declaration
  type, axiom report, source-file hash, Lean/Mathlib versions, original output
  and recorded query time. The three demonstration receipts retain their
  original bytes. Newly imported receipts use their content hash as a filename.
- This README is maintenance documentation, not a mathematical input supplied
  to proof authors or reviewers.

By default, Yui looks for `library/foundations.json` inside the installed skill
root, beside `SKILL.md` and `config.json`. A standalone skill installation does
not require this folder. To select a catalog stored elsewhere, set its directory before
launching Yui:

```sh
export YUI_LIBRARY_ROOT="/absolute/path/to/my-mathlib-library"
```

If the selected directory has no `foundations.json`, the catalog is empty and
ordinary Mathlib tools remain available. A present but invalid catalog or
invalid selected evidence is reported rather than silently trusted.

Run these commands from the Yui repository root:

```sh
python3 -B nl0/scripts/library_catalog.py check
python3 -B nl0/scripts/library_catalog.py search "finite sum integral"
```

`check` validates the stored hashes and metadata against the currently pinned
Mathlib sources. It does not run Lean again, invoke a model, or grant Audit A/B
acceptance. Search returns candidates; relevance and all application hypotheses
still require checking in the new problem.

## Add a theorem after a run

1. **Locate an actual source-query receipt.** Start with the completed run's
   `case-result.json` and follow its source/evidence paths. The result summary
   and final `Proof.lean` are not substitutes for a native-query receipt. You
   can list the receipts retained anywhere inside a run:

   ```sh
   run_dir="/absolute/path/to/completed/rigorous-proof/run-id"
   rg --files --hidden "$run_dir" | rg '(^|/)library-sources\.json$'
   ```

2. **Select the declaration and its receipt-local source ID.** Open the chosen
   JSON file and inspect `sources`, for example `sources.M005`. Confirm the
   declaration and module you want, the complete signature and conditions,
   successful top-level and native-result exit codes, source hash and matching
   toolchain versions. Use the exact ID in that file; `M005` in another receipt
   can denote a different theorem. A successful signature query is usable
   metadata, not a proof that the theorem applies to a particular task.

3. **Import it explicitly and supply useful search tags.** Replace the example
   path and `M005` below with the actual receipt and ID selected above:

   ```sh
   python3 -B nl0/scripts/library_catalog.py add \
     --receipt "/absolute/path/to/library-sources.json" \
     --source-id M005 \
     --tag integral --tag finite --tag sum
   ```

   The command checks the selected successful theorem record against the
   current pins and source bytes, copies the whole receipt without changing
   its original IDs or timestamps, and adds one catalog entry. It makes no
   model call or new Lean query. It does not copy the surrounding proof, old
   audit judgments or other tasks into the catalog.

   Multiple entries may reference different source IDs in the same unchanged
   receipt. Content-addressed filenames prevent evidence with the same old
   filename or source ID from overwriting another receipt. Reimporting an
   identical declaration deduplicates it and can merge additional search tags;
   conflicting existing metadata is rejected for explicit review.

4. **Check the result and review the change.** Run `check`, try a relevant
   `search`, and inspect `git diff -- library` before committing your personal
   additions. `git status --short -- library` also shows newly copied evidence.
   Keep the original run and its receipts unchanged.

The global `--library-root` option can select a different destination for any
maintenance command, before its subcommand:

```sh
python3 -B nl0/scripts/library_catalog.py \
  --library-root "/absolute/path/to/my-mathlib-library" check
```

## Maintenance boundaries

Choose tags describing mathematical concepts, common synonyms and useful API
terms. A tag is only a retrieval aid. Do not encode a previous task's accepted
answer, applicability judgment or additional assumption as a reusable fact.
The catalog does not index every declaration merely because it appeared in a
Lean file; use a retained successful native-query record. If none exists, keep
the candidate outside this catalog until such evidence is obtained.

Maintain the catalog after affected runs have finished. Jobs bind the selected
catalog and evidence hashes, and stages preserve their own copies. Changing a
prepared job's selection or evidence invalidates that binding; a new run uses
the newly maintained catalog. README edits and unrelated unindexed files are
not mathematical inputs.

If Lean or Mathlib changes, old receipts must not be made current by editing
their version strings or hashes. Preserve the old catalog, obtain fresh native
metadata under the new toolchain, and maintain a separately versioned catalog.
The current Yui installation still enforces its own toolchain lock.

This library can reduce repeated metadata queries and improve discovery in
familiar fields. Neither the number of entries nor a catalog hit establishes
proof correctness, full-workflow reliability or a measured speed improvement.
