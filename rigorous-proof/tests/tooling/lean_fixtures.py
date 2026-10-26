"""Reusable local Lean fixtures, not tests or mathematical acceptance records."""
import shutil
from harness_support import FIXTURES
import ir

def norm_plan(cpath):
    return {'version':1,'contract_sha256':ir.digest(cpath),
        'representation_notes':'Real norm equality is transported to ENNReal before the indexed supremum.',
        'steps':[{'id':'T001','statement':'∀ r : iota, ‖F r‖ₑ = ‖G r‖ₑ','inputs':['H001'],
                  'source_steps':['S001'],'explanation':'Lift equality of norms to the extended nonnegative range.'},
                 {'id':'T002','statement':'(⨆ r, ‖F r‖ₑ) = ⨆ r, ‖G r‖ₑ','inputs':['T001'],
                  'source_steps':['S002'],'explanation':'Apply indexed supremum congruence.'}],
        'terminal':'T002'}

LIFT = 'exact fun r => (enorm_eq_iff_norm_eq).2 (h_H001 r)'
SUP = 'exact iSup_congr h_T001'

def shared_fixture(directory, *, objects=False):
    directory.mkdir(parents=True, exist_ok=True)
    for name in ('source.json', 'contract.json'):
        shutil.copyfile(FIXTURES/'lean/examples/case1_norm_sup'/name, directory/name)
    path = directory/'contract.json'
    c = ir.load(path)
    c['version'] = 2
    c['objects'] = []
    if objects:
        c['objects'] = [{'id': 'O001', 'definition': 'The nonnegative norm family of F.', 'views': [
            {'id': 'V001', 'lean_type': 'iota → ℝ', 'meaning': 'Real-valued norms.'},
            {'id': 'V002', 'lean_type': 'iota → ℝ≥0∞', 'meaning': 'Extended nonnegative norms.'}]}]
    c['shared_obligations'] = [{'id': 'L001', 'statement': '∀ r : iota, ‖F r‖ₑ = ‖G r‖ₑ',
        'inputs': ['H001'], 'source_steps': ['S001'],
        'route': 'Lift the given equality of real norms to extended nonnegative norms.',
        'review': {'classification': 'implementation_extraction', 'status': 'DEVELOPMENT_OWNER_REVIEW',
                   'reviewer': 'development owner', 'basis': 'Exactly source paragraph S001; no additional mathematical premise.'}}]
    ir.write(path, c)
    plan = norm_plan(path)
    plan['version'] = 2
    plan['steps'][0]['shared_lemma'] = 'L001'
    if objects:
        plan['steps'][0]['representations'] = [{'object': 'O001', 'view': 'V001', 'expression': 'fun r => ‖F r‖'}]
        plan['steps'][1]['representations'] = [{'object': 'O001', 'view': 'V002', 'expression': 'fun r => ‖F r‖ₑ'}]
        plan['steps'][1]['bridges'] = [{'object': 'O001', 'from': 'V001', 'to': 'V002', 'input': 'T001',
                                      'explanation': 'T001 transports the input norm equality into the selected extended range.'}]
    return path, plan
