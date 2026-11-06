"""Small author explanations for source-facing endpoints, not audit verdicts."""
from __future__ import annotations

import ir
import artifact_protocol as protocol

POLICY = 'endpoint-fidelity-2'


def endpoint_ids(propositions):
    return [p['id'] for p in propositions if p['kind'] in {'external', 'target'}]


def note_schema():
    return protocol.obj({'mode':{'enum':['direct','equivalent']},'explanation':protocol.TEXT})


def validate_note(note, identifier):
    protocol.validate(note,note_schema(),'/'+identifier+'/correspondence',error_type=ir.Invalid)
    # The independent reviewer checks substance. Length/keyword heuristics
    # cannot establish either fidelity or a mathematical equivalence.


def validate_notes(notes, identifiers):
    ir.need(isinstance(notes, dict) and set(notes) == set(identifiers),
            'provide exactly the external and complete-target correspondence explanations')
    for identifier, note in notes.items():
        validate_note(note, identifier)
