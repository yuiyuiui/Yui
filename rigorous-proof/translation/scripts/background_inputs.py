"""Consume accepted Audit A notes without expanding the Lean premise inventory.

The historical promoted-input mode remains readable. New translation runs keep
the original NL0 boundary and carry notes as node-local, verified references.
This adapter never changes the accepted NL0 or its Audit A authority.
"""
from copy import deepcopy

import background

REFERENCE_ONLY = 'node_local_reference'
LEGACY = 'promoted_inputs'


def mode(contract):
    selected = contract.get('source', {}).get('background_mode', LEGACY)
    if selected not in {REFERENCE_ONLY, LEGACY}:
        raise ValueError('Unsupported background consumption mode: '+str(selected))
    return selected


def effective(data, selected=REFERENCE_ONLY):
    if selected == LEGACY:
        return background.effective(data)
    if selected != REFERENCE_ONLY:
        raise ValueError('Unsupported background consumption mode')
    return deepcopy(data[3]), deepcopy(data[4])


def attach_notes(steps, source_map, supplement):
    """Copy exact note locations mechanically; authors need not retype note IDs."""
    result = deepcopy(steps)
    locations = {}
    for rid, notes in (supplement or {}).get('notes', {}).items():
        for note in notes:
            index = int(note['at'].split('/')[3])
            locations.setdefault(rid, []).append((index, rid+'.'+note['id']))
    order = {}
    for sid, row in source_map['paragraph_mapping'].items():
        order.setdefault(row['inference'], []).append(sid)
    for step in result:
        allowed = set()
        for rid, rows in locations.items():
            for index, key in rows:
                if order[rid][index] in step.get('source_steps', []):
                    allowed.add(key)
        supplied = step.get('background_notes', [])
        if not set(supplied) <= allowed:
            raise ValueError('A step cannot borrow another paragraph\'s background note')
        step['background_notes'] = sorted(allowed)
    return result


def library_notes(inventory, inference):
    """Only already-verified notes at this inference may license library use."""
    if inventory.get('background_mode') != REFERENCE_ONLY:
        return {}
    rows = (inventory.get('background_supplement') or {}).get('notes', {}).get(inference, [])
    result = {}
    for note in rows:
        if note['kind'] == 'mathlib':
            source = note['source']
            result.setdefault(source['declaration'], []).append({
                'id': inference+'.'+note['id'], 'source': source, 'fact': note['fact'],
                'at': note['at'], 'grounds': note['grounds']})
    return result
