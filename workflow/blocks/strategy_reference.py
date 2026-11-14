"""Read-only, author-requested reference inside foundation reduction and Lean translation."""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import re


TOOL = 'consult_strategy'
REPLY_CONTRACT = 'StrategyReply@2'
CARD_BYTE_LIMIT = 16 * 1024
REFERENCE_NOTICE = ('Reference only. The recorded Lean and Mathlib versions describe the '
                    'historical reference context, not compatibility limits or proof verification. '
                    'Adapt and check the strategy in the current task\'s selected environment.')
_ROLES = {
    'basis-authoring': ('basis',), 'basis-frontier': ('basis',),
    'interface-authoring': ('basis', 'lean'), 'interface': ('basis', 'lean'),
    'plan': ('lean',), 'proof': ('lean',),
}


def banks_for(phase, arm):
    return _ROLES.get(phase, ()) if arm == 'yui' else ()


@lru_cache(maxsize=1)
def contracts():
    definition = Path(__file__).resolve().parents[1] / 'workflow.json'
    return json.loads(definition.read_text())['contracts']


def query_schema(banks):
    schema = deepcopy(contracts()['StrategyQuery@1'])
    schema['properties']['bank']['enum'] = list(banks)
    return schema


def reference_header():
    return {'reference_only': True, 'current_environment_verification_required': True,
            'usage_notice': REFERENCE_NOTICE}


def validate_environments(environments):
    """Require paired historical provenance without comparing the active version."""
    if not isinstance(environments, list) or not environments:
        raise ValueError('Missing paired Lean/Mathlib reference environments')
    seen = set()
    for row in environments:
        if (not isinstance(row, dict) or set(row) != {'lean_version', 'mathlib_commit', 'basis'}
                or not isinstance(row['lean_version'], str)
                or not re.fullmatch(r'\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?', row['lean_version'])
                or not isinstance(row['mathlib_commit'], str)
                or not re.fullmatch(r'[0-9a-f]{40}', row['mathlib_commit'])
                or row['basis'] != 'historical_configuration'):
            raise ValueError('Invalid paired Lean/Mathlib reference environment')
        key = (row['lean_version'], row['mathlib_commit'])
        if key in seen:
            raise ValueError('Duplicate reference environment')
        seen.add(key)


def tool(banks):
    return {'type': 'function', 'name': TOOL, 'inputSchema': query_schema(banks),
            'description': ('Optional references available across all Lean/Mathlib versions. '
                            'Omit ids to browse descriptions and source environments; supply up to '
                            'three IDs to read complete cards. Recorded versions are provenance. '
                            'Adapt and check the advice in your current task; reading it grants no proof acceptance.')}


def bounded_cards(cards):
    kept, omitted = [], []
    size = 2  # JSON array brackets, with a comma and space between cards.
    for card in cards:
        extra = len(json.dumps(card, ensure_ascii=False).encode()) + (2 if kept else 0)
        if size + extra > CARD_BYTE_LIMIT:
            omitted.append(card['id'])
        else:
            kept.append(card)
            size += extra
    return kept, omitted
