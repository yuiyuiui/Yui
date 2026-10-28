# Ordered retrieval of external theorem sources

Use this procedure for each literature E whose original text is missing. Both
the NL0 author and global Audit A reviewer follow it. Reuse an already supplied,
hash-bound primary document instead of downloading it again. The invoking agent
may retrieve sources before dispatch, but every supplied document must be an
explicit input; never insert files into an active run's frozen inputs.

## 1. Identify the requested work and edition

Read the actual citation and its use in the supplied proof. Record author,
title, known arXiv ID/version or DOI, source kind, and expected theorem/lemma,
page or equation. Search terms must come from that material. Do not invent an
identifier or accept a nearby search hit. A shared title does not establish
that two editions have the same statements or numbering.

## 2. Try arXiv first

Call `search_external_sources(query=title_and_authors, engine="arxiv")`. If an
arXiv ID is already given, use that exact ID, including its version suffix.
Read the matching abstract/version record, then use `read_external_source` on
the actual PDF link. The search tool exposes PDF locators from arXiv abstract
links; those locators are not a substitute for downloading the PDF.

Check identity, version, page count and the complete relevant result. Follow
its definitions and standing hypotheses. If only another version is available,
compare the relevant statements and their conventions, or continue searching
for the cited edition. Never copy a page number from a different version.
Stop retrieval when an adequate original has actually been obtained.

## 3. Search Google for the complete text

If the needed original is still missing, call
`search_external_sources(query=title_and_authors, engine="google")`. Open
plausible author, institution, repository or publisher links and download the
full document with `read_external_source`. A title-only result, catalog,
abstract, search snippet or AI overview does not verify an external theorem.

For `BROWSER_REQUIRED` or a verification page, retry the same search/read with
`browser=true`. The controller can use an installed, isolated local Chrome
through the fixed optional helper. It performs real navigation and rendered
readback, preserves screenshots and uses no personal browser profile. This
also works for CLI stages without a desktop tab-control tool. Missing browser
dependencies, unresolved challenges and browser failures are explicit records;
they do not stop the mathematical workflow by themselves.

An invoking agent with an actual built-in-browser control tool may instead use
that frontend and stage the downloaded original before dispatch. Opening or
queuing a tab alone is never readback evidence. Do not claim that a headless
Chrome session is the user's visible in-app tab.

## 4. Find and confirm a DOI, then try Sci-Hub

When full text remains missing, search Google again using the exact title,
authors and `DOI`. Inspect `doi_candidates` and the linked publisher or DOI
metadata; confirm title, author and edition. These strings are only candidate
identifiers. Reuse a DOI already established by the supplied bibliography or
matching primary metadata; a blocked Google page need not prevent that lookup.
Do not guess a DOI or request an unrelated article just to make retrieval pass.

Call `search_external_sources(query=confirmed_doi, engine="scihub", browser=true)`.
The controller navigates to `https://sci-hub.box/<DOI>`. Ordinary site controls,
including its own ALTCHA verification button when present, may complete normal
access. Follow the returned PDF/object link through `read_external_source`.
Record any redirect, including a different mirror's final hostname, rather
than claiming the bytes came from the initial host. Do not fabricate challenge
tokens, import personal cookies, silently purchase access or change system
proxy settings. If a challenge cannot be completed normally, retain the failure
and move to the disclosed conditional route.

## 5. Establish source fidelity after retrieval

Retain the actual URL, final URL, retrieval timestamp, document/text hashes and
access receipt. A fetched PDF is a readable source candidate, not an automatic
truth or theorem-fidelity judgment. Apply [external-theorem review](external-theorems.md):
confirm author/title/version, locate the result, read the full statement and
governing definitions, check corrections/version history where available, and
map every hypothesis, conclusion and constant dependency to E. Each application
still needs its own verified substitutions and premise checks. A source that
states a different theorem is a mismatch, not an inaccessible-text deferral.

For a changed edition, retain both document hashes and a locator/statement map.
Do not silently substitute the journal version for a cited preprint. Any
substantive normalization bridge belongs in an internal proved node.

## 6. Record unavailable verification and continue

After actual unsuccessful retrieval, follow [conditional sources](conditional-sources.md).
Supply `defer_primary_source` with the E ID, a complete exact quotation already
present in a declared secondary input, its input ID and own failed
`access_records` paths. An unavailable original does not justify inventing a
statement from memory or treating a known contradiction as an assumption.
If the statement itself is missing or incomplete, identify that missing content
instead of pretending the source-only route closes the proof.

Retain `UNVERIFIED_PRIMARY`, `warn.json` and `warn.md`. Continue all other
mathematical, Lean, assembly and audit work normally. The final result remains
`WORKFLOW-CONDITIONAL` (or the corresponding stage's conditional status) until
the actual source and affected review are completed. Display each warning to
the user when it arises and in the final answer. A compile pass does not remove
source uncertainty. Do not repeat indefinitely an unchanged blocked query;
preserve its failure and advance to the next route.

## Optional local browser setup

No browser package is installed automatically. `nl0/scripts/source_browser.py`
looks for Node on PATH or the bundled Codex runtime, its bundled Playwright,
and an installed Chrome/Chromium. Other installations can set:

```sh
export YUI_SOURCE_BROWSER_NODE="/absolute/path/to/node"
export YUI_SOURCE_BROWSER_MODULE="/absolute/path/to/playwright/index.mjs"
export YUI_SOURCE_BROWSER_EXECUTABLE="/absolute/path/to/chrome"
```

These select existing host tools, not model-generated commands or scripts. An
invalid explicit override is reported without silently choosing another tool.
The trusted driver is included in frozen runtime hashes. Each call owns its
temporary Chrome profile and process group; cancellation and a transport wait
timeout close those processes. The wait timeout is a browser operation limit,
not a case/proof budget. Source readback keeps the existing 32 MiB file limit.
An unavailable browser leaves ordinary HTTPS and conditional continuation usable.
