"""Controller-owned mathematical language, not an author-extensible theorem list."""
from copy import deepcopy

PROFILE = 'finite-language-3'
STANDARD_LANGUAGE = (
    'Ordinary typed mathematical language: logical connectives, quantifiers, equality, '
    'sets, functions, tuples, finite indices and their usual notation. A type explicitly '
    'named natural numbers, integers, rationals, reals or complex numbers means that '
    'standard structure, with its usual numerals and arithmetic operations; these '
    'operation tokens need not be redeclared as project objects. The fixed finite '
    'calculation rules below, including a+0=a, are controller permissions, not an '
    'author claim. Project functions/sets and substantive analytic properties still '
    'need their explicit declarations and direct inputs or displayed local proofs.'
)
CALCULATIONS = {
    'equality': 'Equality reflexivity, symmetry, transitivity and substitution.',
    'definitions': 'Unfold an explicitly supplied definition; this proves no extra property.',
    'finite_algebra': 'Displayed finite semiring/ring/field arithmetic, including the usual zero/one laws (a+0=a, a*1=a), distributivity, associativity and finite polynomial identities.',
    'finite_order': 'Displayed ordered-field reasoning: reflexivity, transitivity and antisymmetry; adding inequalities or multiplying/dividing them with their sign conditions; square nonnegativity for an explicitly given real expression. Display the actual reduction, inequality chain or nonnegative expression. Merely naming a theorem or asserting its output inequality is not a displayed calculation.',
    'finite_sums': 'Unfold and rearrange finite sums/products with explicitly given finite indices.',
}
_LANGUAGE = {
    '0': ('typed numeral', 'Zero of the explicitly specified mathematical type.'),
    '1': ('typed numeral', 'One of the explicitly specified mathematical type.'),
    '2': ('typed numeral', 'Two of the explicitly specified mathematical type, including an exponent two.'),
    'ℕ': ('number system', 'The natural numbers with their usual arithmetic.'),
    'ℤ': ('number system', 'The integers with their usual arithmetic.'),
    'ℚ': ('number system', 'The rational numbers with their usual ordered-field operations.'),
    'ℝ': ('number system', 'The real numbers with their usual ordered-field structure.'),
    'ℂ': ('number system', 'The complex numbers with their usual field structure.'),
    '∅': ('typed set notation', 'The empty set in the explicitly specified ambient type.'),
    '∞': ('typed order notation', 'The top element in an explicitly specified extended ordered codomain.'),
    'norm': ('norm notation', 'The norm supplied by the explicitly specified normed-space structure; no estimate is granted.'),
    '∂': ('derivative notation', 'Classical differentiation where the stated derivative exists; no calculus rule is granted.'),
    '∫': ('integral notation', 'The integral for the explicitly specified function, measure and codomain; no integral identity is granted.'),
    'Integrable': ('predicate notation', 'Bochner integrability for the specified function and measure; no integrability is asserted.'),
    'AEStronglyMeasurable': ('predicate notation', 'Almost-everywhere strong measurability for the specified function and measure; no measurability is asserted.'),
}
PRIMITIVES = {symbol: {'symbol': symbol, 'type': kind, 'meaning': meaning}
              for symbol, (kind, meaning) in _LANGUAGE.items()}


def bind_author(logic):
    """Fill omitted language metadata, reject explicit permission/meaning conflicts."""
    if not isinstance(logic, dict):
        raise ValueError('FOUNDATION: logic must be an object')
    calculations = logic.get('calculations', [])
    if not isinstance(calculations, list) or any(not isinstance(value, str) or value not in CALCULATIONS for value in calculations):
        raise ValueError('FOUNDATION_AUTHORITY: calculations is controller-owned. Omit it or use only '+
                         repr(list(CALCULATIONS))+'. Author notes cannot grant analysis or other theorems. '
                         'Removing a permission claim does not prove the fact: register E/M or give a local derivation.')
    requested = logic.get('primitives', [])
    if not isinstance(requested, list):
        raise ValueError('FOUNDATION: primitives must be a list of standard-language symbol selections')
    for row in requested or [{'symbol': key} for key in PRIMITIVES]:
        if not isinstance(row, dict) or not isinstance(row.get('symbol'), str) or row['symbol'] not in PRIMITIVES or not set(row) <= {'symbol', 'type', 'meaning'}:
            raise ValueError('FOUNDATION_PRIMITIVE: choose a standard symbol from '+repr(list(PRIMITIVES))+
                             '; project-dependent objects/notation belong in parameters, D or scoped locals, not primitives.')
        canonical = PRIMITIVES[row['symbol']]
        if any(value != canonical[key] for key, value in row.items()):
            raise ValueError('FOUNDATION_PRIMITIVE: explicit type/meaning conflicts with fixed language for '+
                             row['symbol']+'. Select {symbol:...} to bind its exact metadata, or define the project object in D.')
    logic['calculations'] = list(CALCULATIONS)
    logic['primitives'] = deepcopy(list(PRIMITIVES.values()))


def require_canonical(logic):
    clone = deepcopy(logic)
    bind_author(clone)
    if clone != logic:
        raise ValueError('FOUNDATION_PROFILE: source must explicitly contain current controller-bound language metadata before a new Audit A')


def packet_logic(logic):
    """Author descriptions never become packet permissions, including legacy input."""
    value = deepcopy(logic)
    value['calculations'] = [key+': '+description for key, description in CALCULATIONS.items()]
    return value
