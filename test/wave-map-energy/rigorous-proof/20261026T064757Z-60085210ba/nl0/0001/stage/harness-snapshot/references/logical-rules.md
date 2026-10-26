# Package local reasoning as true theorem nodes

The main graph has only E/M/H source propositions. A temporary assumption is
an argument-local device, never a trusted graph vertex. Every exported N/P is
a complete claim under the frozen original context. The audit inspects the
local derivation; surface implication syntax alone is insufficient.
The complete [neutral JSON example](../templates/quantified-implication-example.md)
shows an arbitrary binder, a local antecedent, its discharge and the full
quantified output. Follow this accounting rather than silently granting a
property in a local object's type.

## Implication and contradiction

To prove `X -> Y`, introduce X inside one argument, derive Y from the declared
inputs, then discharge X into the antecedent. Output `X -> Y`, not Y. To use Y
unconditionally later, supply an actually proved X and apply implication
elimination. A local X and a proved X are not the same proof object.

To prove `not X`, derive false under local X and discharge X by negation
introduction. To prove P by classical contradiction, first produce the complete
theorem `not P -> false` (equivalently `not not P`), then apply the fixed
classical rule. A single R may combine the operations if every local assumption
is accounted for. No classical double-negation elimination under an
intuitionistic-only policy.

Example graph: N1 `(not P -> Q)`, N2 `not Q`, R1 outputs N3
`(not P -> false)`, R2 outputs P. The argument of R1 locally assumes not P,
applies N1 and N2, and closes that assumption. No `not P` root is added.
The fallacy “assume P, obtain P, discharge and output P” fails: its valid output
would be `P -> P`.

## Cases

From an already proved `A or B or C`, obtain a common target Q by complete
conditional lemmas `A -> Q`, `B -> Q`, `C -> Q`, then disjunction elimination.
Alternatively prove `not A`, `not B` and conclude C using the original
disjunction. Eliminating A/B without a proved exhaustive disjunction cannot
establish C. A branch producing false can produce the common target by false
elimination; it does not make false an unconditional source proposition.

Proof bodies may contain all branches locally instead of exporting every
branch lemma. Check coverage, identical target/ambient context, and the absence
of sibling-branch fact/witness leakage. Introduce/discharge each branch-local
assumption in its actual scope.

## Quantifiers, witnesses, and induction

For universal introduction use an arbitrary variable, then close its binder.
It must not occur free in an undischarged extra assumption. If the intended
theorem has a premise H(x), retain it in the quantified implication.

For existential elimination start from a proved existence statement, choose a
fresh local witness with exactly its stated properties, and prove a conclusion
independent of that witness's private identity. A witness depending on n does
not yield one witness valid for every n. Do not turn a local witness into a
globally available constant without a legitimate, recorded construction.

For natural-number induction prove the base and the complete step
`forall n, Q(n) -> Q(n+1)` and use induction to conclude `forall n, Q(n)`.
The induction hypothesis is local to the step; there is no circular graph edge.
If the step invokes the hypothesis at a transformed point s, include
`forall s` in the induction invariant. Well-founded induction needs the exact
well-founded relation/decrease justification; the word “induct” is not enough.

## Local notation

Global symbols are reserved. Local binders can repeat across separate nodes
or separate binding scopes in a node, but cannot shadow a global symbol.
`sum_{k=1}^N` binds k only in that expression. Source theorem dummy variables
are alpha-renamed locally, not registered as a new global object each time.
Freshness, witness dependencies, constant uniformity, and binder scope are
mathematical audit obligations; a list of names does not verify the formula.
In v2, local declarations identify introduction kind/basis and inclusive S
start/end positions. An input-bound name needs instantiation; a witness needs
an actual existence premise. Local F facts record their complete statement,
statement-local binders, used objects and remaining assumptions. Neither a
fact nor a chosen witness may escape its scope. The checker accounts for
declared scopes; Audit A must also inspect the actual quantifier reasoning.
