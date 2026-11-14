"""Elementary calculation policy and core syntax, not a domain vocabulary."""
from copy import deepcopy

PROFILE = 'elementary-language-4'
STANDARD_LANGUAGE = (
    'Ordinary typed mathematical language: logical connectives, quantifiers, equality, '
    'sets, functions, tuples, finite indices and their usual notation. A type explicitly '
    'named natural numbers, integers, rationals, reals or complex numbers means that '
    'standard structure, with its usual numerals and arithmetic operations; these '
    'operation tokens need not be redeclared as project objects. The fixed finite '
    'calculation rules below, including a+0=a, are controller permissions, not an '
    'author claim. The core symbol table below is not a dictionary of all allowed '
    'mathematics. Objects and notation from any subject are introduced by this '
    'problem\'s parameters, D definitions or scoped locals, with their types and '
    'dependencies. Their properties need direct inputs or displayed local proofs; '
    'a familiar name or symbol supplies no theorem.'
)
CALCULATIONS = {
    'equality': 'Equality reflexivity, symmetry, transitivity and substitution.',
    'definitions': 'Unfold an explicitly supplied definition; this proves no extra property.',
    'finite_algebra': 'Routine finite semiring/ring/field arithmetic, including zero/one laws, distributivity, associativity and finite polynomial identities. Correct elementary compression is permitted; a substantive missing argument is not.',
    'finite_order': 'Routine ordered-field reasoning with actual signs/domains: order laws, adding inequalities, multiplication/division with sign conditions, and real square nonnegativity. Ordinary valid elementary inferences need no exhaustive displayed chain. Check that the conclusion follows; substantial named theorems still require inputs or verified-background admission.',
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
                         repr(list(CALCULATIONS))+'. Author notes cannot grant additional theorems. '
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
    """Author descriptions never become packet permissions, including author-supplied metadata."""
    value = deepcopy(logic)
    value['calculations'] = [key+': '+description for key, description in CALCULATIONS.items()]
    return value
