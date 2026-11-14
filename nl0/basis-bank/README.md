# Foundation strategy bank

Foundation authors can use `consult_strategy` while they still own the route and the Lean types. Call it with `{"bank":"basis"}` for short descriptions. Select complete cards with, for example, `{"bank":"basis","ids":["ST021"]}`. An author who already has a route can go directly to drafting and submission. The Lean interface author may consult the same catalog when choosing a representation.

The original source determines the theorem, resource model and permitted hypotheses. Each card offers a possible method under stated conditions and includes a misuse example. A lookup records what the author read. Decisions to adopt a method, its mathematical verification and any measured benefit require separate evidence.

All cards are available across Lean/Mathlib versions. Catalog descriptions and complete cards disclose paired `reference_environments`: the historical Lean version and exact Mathlib revision associated with the reference context. These values are provenance, not a compatibility whitelist or a claim of successful compilation. Adapt and check the strategy in the current task's selected environment. Reading advice does not select an environment or grant proof acceptance.

The [reference policy and acceptance witnesses](../../nl02lean/references/strategy-reference.md) define the cross-version behavior and its verification scope.

Maintain `strategies.json` and its qualified evidence. Use a stable ID across both banks, increment the revision when a card changes and describe a concrete class of decisions rather than a particular case. A plausible observation can be added as general guidance and later narrowed or withdrawn. Rebuild the derived files from the Yui root with `python3 -B nl02lean/scripts/strategy_bank.py build --bank basis`.
