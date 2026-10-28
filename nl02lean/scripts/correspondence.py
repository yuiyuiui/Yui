"""Small author explanations for source-facing endpoints, not audit verdicts."""
from __future__ import annotations

import ir

POLICY = 'endpoint-fidelity-2'


def endpoint_ids(propositions):
    return [p['id'] for p in propositions if p['kind'] in {'external', 'target'}]


def validate_note(note, identifier):
    ir.need(isinstance(note, dict) and set(note) == {'mode', 'explanation'},
            identifier + '.correspondence needs mode and explanation')
    ir.need(note['mode'] in {'direct', 'equivalent'},
            identifier + '.correspondence mode must be direct or equivalent')
    ir.need(isinstance(note['explanation'], str) and bool(note['explanation'].strip()),
            identifier + '.correspondence explanation is missing')
    # The independent reviewer checks substance. Length/keyword heuristics
    # cannot establish either fidelity or a mathematical equivalence.


def validate_notes(notes, identifiers):
    ir.need(isinstance(notes, dict) and set(notes) == set(identifiers),
            'provide exactly the external and complete-target correspondence explanations')
    for identifier, note in notes.items():
        validate_note(note, identifier)
