# Select the complete mathematical target before dispatch

The invoking agent reads the supplied material and the user's request before
starting the author. If one intended target is clear, extract its complete
statement and standing hypotheses and proceed without an extra user question.
An explicit theorem selection already supplied by the user needs no repeated
confirmation. If several independent claims are plausible targets and intent
does not resolve them, ask which claims to include, or whether all are wanted.
Never choose the easiest claim or default to the first numbered theorem.

`yui.py targets PAPER` provides a source-bound heading index. It is an aid to
reading, not a semantic theorem extractor. `TARGET_REVIEW_REQUIRED` is work for
the invoking agent; it does not itself require another human question.
`TARGET_SELECTION_REQUIRED` reports multiple candidates, which can include
auxiliary lemmas: read their relationships before deciding intent is ambiguous.
Bad PDF extraction requires visual readback or a checked transcription.

Record a `yui-target-selection-1` JSON document with the exact original document
path/hash, status `SELECTED`, the selection basis, and `targets`. Each target has
an ID, label, complete `statement` and `start_line` (null for an explicit user
statement without an extracted line). `full_target` is that complete statement,
or the conjunction of all selected complete claims. Use
`target_selection.select(path, targets)` to create the bound record after
readback. Save it beside the problem and pass `--target-file FILE` to prepare/run.
For a short complete user statement, `--target 'FULL STATEMENT'` is equivalent.
A theorem number alone identifies what to read; it does not supply its missing
mathematical content. The invoking agent prepares this record for the user.

The author receives `target-selection.json` as a frozen input. The submission
contract requires the exact `full_target`, and ordinary Audit A still checks
whether hypotheses, definitions and conclusions faithfully represent it.
For independent claims, preserve each implication and its own hypotheses.
Combining all hypotheses into one stronger premise is not an equivalent
conjunction of independently claimed theorems. Do not change the selected
claims during repair. Existing accepted-source translation retains its already
bound target instead of selecting a new one.
