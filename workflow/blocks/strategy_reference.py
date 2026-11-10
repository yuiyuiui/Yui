"""Read-only, author-requested reference inside foundation reduction and Lean translation."""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path


TOOL = 'consult_strategy'
CARD_BYTE_LIMIT = 16 * 1024
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


def tool(banks):
    return {'type': 'function', 'name': TOOL, 'inputSchema': query_schema(banks),
            'description': 'Optional general guidance. Omit ids to browse short descriptions; supply up to three IDs to read complete cards. Check their conditions in your own task.'}


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
