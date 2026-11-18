"""Bind the reviewed local inputs to one manifest per Lean author."""
from pathlib import Path

import ir
from controller_common import bind, write
from private_handoff import run_id, wire

REVIEW_INPUT = 'local-tasks.json'
SOURCE_FIELDS = ('source_steps', 'explanation', 'accepted_background_notes', 'background_supplement_sha256')
INPUT_FIELDS = ('inputs', 'shared_inputs')


def parts(packet):
    return {
        'goal': {key: value for key, value in packet.items() if key not in SOURCE_FIELDS + INPUT_FIELDS},
        'inputs': {key: packet[key] for key in INPUT_FIELDS if key in packet},
        'source': {key: packet[key] for key in SOURCE_FIELDS if key in packet},
    }


def review_inputs(contract, plan):
    return {step['id']: parts(ir.local_packet(contract, plan, step['id'])) for step in plan['steps']}


def review_input(out, digest):
    """Read the exact local tasks declared to the independent reviewer."""
    root = Path(out) / 'inputs'
    path = wire.resolve(root, {'path': REVIEW_INPUT, 'sha256': digest}, '/review/local_tasks')
    ir.need({'id': REVIEW_INPUT, 'path': REVIEW_INPUT, 'sha256': digest}
            in ir.load(root / 'inputs.json')['inputs'], 'Local tasks missing from reviewer inputs')
    return path


def prepare_run(out, contract, receipt):
    """Record the review binding once and load its per-node inputs, if reviewed."""
    root = out / 'local-tasks'
    tasks = None
    review = {'status': 'NO_INTERFACE_RECEIPT'}
    if receipt is not None:
        receipt = Path(receipt).resolve()
        binding = bind(receipt)
        row = ir.load(receipt)
        ir.need(row['contract_sha256'] == ir.digest(contract)
                and row['plan_sha256'] == ir.digest(contract.with_name('plan.json')),
                'Interface review belongs to a different Lean plan')
        review = {'status': 'LEGACY_INTERFACE_REVIEW', 'receipt': binding}
        if 'local_tasks_sha256' in row:
            tasks = ir.load(review_input(receipt.parent, row['local_tasks_sha256']))
            review.update(status='REVIEWED_LOCAL_TASKS', local_tasks_sha256=row['local_tasks_sha256'])
    write(root / 'review.json', review)
    return tasks


def identity(contract, sid):
    return {'run_id': run_id(contract.parent.parent), 'sender': 'frozen-lean-plan', 'node': sid,
            'contract_sha256': ir.digest(contract), 'plan_sha256': ir.digest(contract.with_name('plan.json'))}


def issue(out, contract, sid, packet, reviewed_tasks):
    root = out / 'local-tasks'
    material = parts(packet)
    if reviewed_tasks is not None:
        ir.need(reviewed_tasks.get(sid) == material, 'Reviewed local task changed: ' + sid)
    files = {'review': wire.reference(root, root / 'review.json')}
    for field, value in material.items():
        path = root / sid / (field + '.json')
        write(path, value)
        files[field] = wire.reference(root, path)
    request = root / (sid + '.json')
    write(request, {'schema': wire.LOCAL_TASK, **identity(contract, sid), 'files': files})
    return request


def read(request, contract, plan, sid):
    files = wire.read_local_task(request, identity(contract, sid))
    review = wire.read(files.pop('review'))
    material = {field: wire.read(path) for field, path in files.items()}
    ir.need(material == parts(ir.local_packet(contract, plan, sid)), 'Local task differs from the frozen plan: ' + sid)
    if 'receipt' in review:
        binding = review['receipt']
        ir.need(bind(binding['path']) == binding, 'Local task interface receipt changed')
    return {key: value for row in material.values() for key, value in row.items()}
