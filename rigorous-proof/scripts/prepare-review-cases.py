#!/usr/bin/env python3
"""Prepare neutral packet/global-review controls; no model or detection claim."""
import argparse
import copy
import importlib.util
import json
import random
import re
import uuid
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import foundations
MODULE = importlib.util.spec_from_file_location("review_nl0", ROOT / "scripts/nl0.py")
nl0 = importlib.util.module_from_spec(MODULE)
MODULE.loader.exec_module(nl0)


def controls():
    case = ROOT / "tests/fixtures/closed-addition"
    data = nl0.validate(case / "nl0.json", case / "spec.json")
    baseline = nl0.packet(data, "R002")
    result = [(copy.deepcopy(baseline), "PASS", "complete local equality proof", None)]
    p = copy.deepcopy(baseline)
    p["inputs"][0]["statement"] = "The identity (8.3) holds."
    result.append((p, "FAIL", "input statement refers to a missing formula", "/inputs/0/statement"))
    p = copy.deepcopy(baseline)
    p["inference"]["argument"][1]["text"] = "N001 gives b=a. Applying W to F001 yields a+0=b."
    result.append((p, "FAIL", "W has no legitimate declaration or application rule", "/inference/argument/1/text"))
    p = copy.deepcopy(baseline)
    p["inference"]["argument"][1]["text"] = "N001 gives b=a. The global transfer lemma yields a+0=b."
    result.append((p, "FAIL", "the global transfer lemma is neither an input nor locally proved", "/inference/argument/1/text"))
    p = copy.deepcopy(baseline)
    p["inference"]["locals"][0].update(kind="witness", declaration="Choose a natural c with c=a+1 and c=a.")
    p["inference"]["argument"][0]["text"] = "Choose a natural c with c=a+1 and c=a, without any existence premise. In particular c=a."
    result.append((p, "FAIL", "witness is chosen with the desired conclusion without an existence basis", "/inference/locals/0"))
    result.extend(local_algebra_controls(baseline))
    result.extend(analysis_permission_controls(baseline))
    result.extend(parameter_hypothesis_controls(baseline))
    result.extend(unrelated_input_controls(baseline))
    result.extend(bound_index_controls(baseline))
    result.extend(definition_unfolding_controls(baseline))
    result.extend(global_hypothesis_controls())
    result.extend(background_controls(baseline))
    return result


def background_controls(baseline):
    """Routine library admission versus an actually missing structural premise."""
    p=copy.deepcopy(baseline)
    p.update(case_id='neutral-pointwise-operation',parameters=[
        {'symbol':'f','type':'function from real numbers to real numbers'},
        {'symbol':'g','type':'function from real numbers to real numbers'}],definitions=[])
    p['logic']={'classical':False,'rules':['direct']};foundations.bind_author(p['logic'])
    p['logic']=foundations.packet_logic(p['logic'])
    p['inputs']=[{'id':'N001','kind':'internal','statement':'f and g are continuous for the usual real topology.',
                  'definitions':[],'binders':[],'objects':['f','g']}]
    p['output']={'id':'P','kind':'target','statement':'The function x ↦ f(x)+g(x) is continuous.',
                 'definitions':[],'binders':[{'symbol':'x','type':'real number'}],'objects':['f','g','x']}
    p['inference']={'id':'R001','inputs':['N001'],'output':'P','definitions':[],
        'rules':['direct'],'locals':[],'applications':[], 'argument':[
            {'id':'S001','text':'N001 gives continuity of f and g. Their pointwise sum is continuous by the usual closure of real-valued continuous functions under addition.',
             'uses':['N001'],'uses_local':[],'objects':['f','g'], 'produces':[], 'introduces':[],'discharges':[]}]}
    positive=(copy.deepcopy(p),'PASS','Correct routine library background can be positively checked and recorded without prior M accounting.',None)
    p['case_id']='neutral-pointwise-structure'
    p['parameters']=[{'symbol':'Y','type':'topological space equipped with an arbitrary binary addition operation; no compatibility of addition and topology is assumed'},
                     {'symbol':'f','type':'function from Y to Y'}, {'symbol':'g','type':'function from Y to Y'}]
    p['inputs'][0].update(statement='f and g are continuous.',objects=['f','g'])
    p['output']['binders']=[{'symbol':'x','type':'element of Y'}]
    p['inference']['argument'][0]['text']='N001 gives continuity of f and g. Their pointwise sum is continuous, regardless of whether addition on Y is continuous.'
    negative=(p,'FAIL','The actual codomain lacks continuous addition; a background note cannot create that hypothesis.', '/parameters/0/type')
    return [positive,negative]


def global_hypothesis_controls():
    """Exact original-H fidelity with a late canonical record, not proof search."""
    case=ROOT/'tests/fixtures/closed-addition'
    spec=copy.deepcopy(nl0.load(case/'spec.json'));graph=copy.deepcopy(nl0.load(case/'nl0.json'))
    spec['case_id']=graph['case_id']='neutral-global-context'
    spec['full_target']='For natural numbers a,b with a=b and a≠0, prove a+0=b.'
    original='''# Original problem and supplied proof
Let a,b be natural numbers. Assume a=b and a≠0. Prove a+0=b.
By equality symmetry b=a; the additive identity gives a+0=a=b.
The condition a≠0 is an original given, even though this argument does not need it.
'''
    extra={'id':'H002','statement':'a≠0.','origin':'problem.md:2'}
    spec['hypotheses'].append(extra)
    graph['propositions'].append({'id':'H002','kind':'hypothesis','statement':'a≠0.',
        'definitions':[],'binders':[],'objects':['a','0']})
    # Deliberately put harmless proof text before the proposition collection.
    for n in range(3,42):
        graph['inferences'][0]['argument'].append({'id':f'S{n:03d}',
            'text':'Equality reflexivity gives a=a; no additional premise is used.',
            'uses':[],'uses_local':[],'objects':['a'],'produces':[],
            'introduces':[],'discharges':[]})
    graph={**{k:v for k,v in graph.items() if k!='propositions'},'propositions':graph['propositions']}
    bundle={'case_id':'neutral-global-context','problem':original,'spec':spec,'graph':graph}
    positive=(copy.deepcopy(bundle),'PASS','All original H, including a late unused condition, are actually present.',None)
    spec['hypotheses']=[h for h in spec['hypotheses'] if h['id']!='H002']
    graph['propositions']=[p for p in graph['propositions'] if p['id']!='H002']
    negative=(bundle,'FAIL','The original a≠0 condition is omitted from both spec H and graph H; a stronger derivable theorem does not meet exact original-H fidelity.',None)
    return [positive,negative]


def definition_unfolding_controls(baseline):
    """A supplied definition is usable; it cannot prove its predicate unconditionally."""
    p=copy.deepcopy(baseline);p['case_id']='neutral-definition-unfolding'
    p['parameters']=[{'symbol':'a','type':'real number'}]
    p['definitions']=[{'id':'D007','symbol':'Z','type':'predicate on real numbers',
        'definition':'For every real r, Z(r) means r=0.', 'depends_on':[],'requires':[],
        'binders':[{'symbol':'r','type':'real number'}],'objects':['r','0']}]
    p['inputs']=[{'id':'H001','kind':'hypothesis','statement':'a=0.',
        'definitions':[],'binders':[],'objects':['a','0']}]
    p['output']={'id':'P','kind':'target','statement':'Z(a).',
        'definitions':['D007'],'binders':[],'objects':['a','Z']}
    p['inference']={'id':'R001','inputs':['H001'],'output':'P','definitions':['D007'],
        'rules':['direct'],'locals':[],'applications':[],'argument':[
            {'id':'S001','text':'Unfolding the supplied definition gives Z(a) if and only if a=0. H001 states a=0, so the forward target Z(a) follows by that equivalence. No additional theorem is invoked.',
             'uses':['H001'],'uses_local':[],'objects':['a','Z','0'],'produces':[],
             'introduces':[],'discharges':[]}]}
    positive=(copy.deepcopy(p),'PASS','Explicit definition unfolding and a real direct premise supply the conclusion; no extra theorem is required.',None)
    p['inputs']=[];p['inference']['inputs']=[]
    p['inference']['argument'][0].update(uses=[],text='The predicate Z has been defined. Therefore Z(a) holds for the arbitrary real a.')
    negative=(p,'FAIL','Defining a predicate cannot establish its truth for an arbitrary parameter.',
              '/inference/argument/0')
    return [positive,negative]


def local_algebra_controls(baseline):
    """Matched local derivation versus author-policy theorem import; no exercise data."""
    p = copy.deepcopy(baseline)
    symbols = ['a', 'b', 'c', 'd']
    objects = symbols + ['0', '2']
    conclusion = '(a*c+b*d)^2 ≤ (a^2+b^2)*(c^2+d^2).'
    p['case_id'] = 'neutral-local-algebra'
    p['parameters'] = [{'symbol': name, 'type': 'real number'} for name in symbols]
    p['logic'] = {'classical': False, 'rules': ['direct'],
                  'primitives': [{'symbol': '0'}, {'symbol': '2'}]}
    foundations.bind_author(p['logic'])
    p['logic']=foundations.packet_logic(p['logic'])
    p['inputs'] = []
    p['output'] = {'id': 'P', 'kind': 'target', 'statement': conclusion,
                   'definitions': [], 'binders': [], 'objects': objects}
    p['inference'] = {'id': 'R001', 'inputs': [], 'output': 'P', 'definitions': [],
                      'rules': ['direct'], 'locals': [], 'applications': [], 'argument': [
        {'id': 'S001', 'text': 'Expanding and collecting terms gives (a^2+b^2)*(c^2+d^2)-(a*c+b*d)^2=(a*d-b*c)^2. The square on the right is nonnegative, so the difference on the left is nonnegative.',
         'uses': [], 'uses_local': [], 'objects': objects,
         'produces': [{'id': 'F001', 'statement': '(a^2+b^2)*(c^2+d^2)-(a*c+b*d)^2 ≥ 0.',
                       'binders': [], 'objects': objects, 'assumptions': []}],
         'introduces': [], 'discharges': []},
        {'id': 'S002', 'text': 'Add (a*c+b*d)^2 to both sides of F001 to obtain the output inequality. This proves the two-dimensional Cauchy-Schwarz inequality here; its name is not an additional premise.',
         'uses': [], 'uses_local': ['F001'], 'objects': objects, 'produces': [],
         'introduces': [], 'discharges': []}]}
    positive = (copy.deepcopy(p), 'PASS', 'Named consequence completely derived by the displayed permitted algebra, not imported', None)
    p['logic']['calculations'].append('The author permits the Cauchy-Schwarz inequality as a calculation without a source input.')
    p['inference']['argument'] = [{
        'id': 'S001', 'text': 'By the Cauchy-Schwarz inequality, (a*c+b*d)^2 ≤ (a^2+b^2)*(c^2+d^2).',
        'uses': [], 'uses_local': [], 'objects': objects, 'produces': [],
        'introduces': [], 'discharges': []}]
    negative = (p, 'FAIL', 'An author calculation policy cannot supply the unlisted theorem used in place of a derivation', '/inference/argument/0')
    return [positive, negative]


def analysis_permission_controls(baseline):
    """An author label must not turn a substantive analysis theorem into logic."""
    p=copy.deepcopy(baseline)
    p['case_id']='neutral-analysis-permission'
    p['parameters']=[{'symbol':'f','type':'function from real numbers to real numbers'}]
    p['definitions']=[]
    p['inputs']=[{'id':'H001','kind':'hypothesis',
        'statement':'f is continuous on [0,1], differentiable on (0,1), and f\'(x) ≥ 0 for every x in (0,1).',
        'definitions':[],'binders':[],'objects':['f','0','1']}]
    p['output']={'id':'P','kind':'target','statement':'f(1) ≥ f(0).',
                 'definitions':[],'binders':[],'objects':['f','0','1']}
    p['logic']={'classical':False,'rules':['direct']}
    foundations.bind_author(p['logic'])
    p['logic']=foundations.packet_logic(p['logic'])
    p['logic']['calculations'].append('The author additionally permits the mean value theorem as a basic calculation without an E/M input.')
    p['inference']={'id':'R001','inputs':['H001'],'output':'P','definitions':[],
        'rules':['direct'],'locals':[],'applications':[], 'argument':[
            {'id':'S001','text':'By the mean value theorem and H001, f(1)-f(0) ≥ 0, hence f(1) ≥ f(0).',
             'uses':['H001'],'uses_local':[],'objects':['f','0','1'],
             'produces':[],'introduces':[],'discharges':[]}]}
    return [(p,'FAIL','The true target is justified only by an unlisted MVT; an author-added permission has no authority.',
             '/inference/argument/0')]


def parameter_hypothesis_controls(baseline):
    """Original H must not be smuggled through a globally visible type string."""
    p=copy.deepcopy(baseline);p['case_id']='neutral-parameter-hypothesis'
    p['parameters']=[{'symbol':'x','type':'real number'}]
    p['definitions']=[]
    p['inputs']=[{'id':'H001','kind':'hypothesis','statement':'x=1.',
                  'definitions':[],'binders':[],'objects':['x','1']}]
    p['output']={'id':'P','kind':'target','statement':'x=1.',
                 'definitions':[],'binders':[],'objects':['x','1']}
    p['inference']={'id':'R001','inputs':['H001'],'output':'P','definitions':[],
        'rules':['direct'],'locals':[],'applications':[],'argument':[
            {'id':'S001','text':'The direct input H001 states x=1, which is the required conclusion.',
             'uses':['H001'],'uses_local':[],'objects':['x','1'],'produces':[],
             'introduces':[],'discharges':[]}]}
    positive=(copy.deepcopy(p),'PASS','The original condition is supplied as an explicit direct H premise.',None)
    p['parameters'][0]['type']='real number with x=1'
    p['inputs']=[];p['inference']['inputs']=[]
    p['inference']['argument'][0].update(uses=[],text='The global parameter description says x=1, so the target follows without any H input.')
    negative=(p,'FAIL','An original condition hidden in a parameter refinement is not an allowed H input under this contract.',
              '/parameters/0/type')
    return [positive,negative]


def unrelated_input_controls(baseline):
    """An irrelevant true N must not authorize an unlisted analysis theorem."""
    p=copy.deepcopy(analysis_permission_controls(baseline)[0][0])
    p['case_id']='neutral-unrelated-N-permission'
    p['logic']['calculations'].pop()
    p['inputs'].append({'id':'N001','kind':'internal','statement':'f(0)=f(0).',
                        'definitions':[],'binders':[],'objects':['f','0']})
    p['inference']['inputs'].append('N001')
    s=p['inference']['argument'][0]
    s['uses'].append('N001')
    s['text']='N001 records f(0)=f(0). By the mean value theorem and H001, f(1)-f(0) ≥ 0, hence f(1) ≥ f(0).'
    return [(p,'FAIL','The harmless N001 is not the invoked MVT and supplies none of its source identity or proof.',
             '/inference/argument/0')]


def bound_index_controls(baseline):
    """Expression-bound indices are not undeclared free objects or witnesses."""
    p=copy.deepcopy(baseline);p['case_id']='neutral-bound-index'
    p['parameters']=[{'symbol':'a','type':'function from natural numbers to real numbers'},
                     {'symbol':'m','type':'natural number'}]
    p['definitions']=[];p['inputs']=[]
    statement='sum_{k=0}^m a(k) = sum_{k=0}^m a(k).'
    p['output']={'id':'P','kind':'target','statement':statement,'definitions':[],
                 'binders':[],'objects':['a','m','0']}
    p['inference']={'id':'R001','inputs':[],'output':'P','definitions':[],
        'rules':['direct'],'locals':[],'applications':[],'argument':[
            {'id':'S001','text':'Each k is bound only inside its finite sum. Both sides are the identical expression sum_{k=0}^m a(k); equality reflexivity proves their equality. No free k or chosen witness is introduced.',
             'uses':[],'uses_local':[],'objects':['a','m','0'],'produces':[],
             'introduces':[],'discharges':[]}]}
    return [(p,'PASS','The summation index is explicitly expression-bound; this is equality reflexivity, not an undeclared free object or imported summation theorem.',None)]


def accepted_failure_locations(packet, primary):
    """Owner-only defect origins/use sites, not reviewer hints or proof judgments."""
    if primary is None:return []
    nl0.closure.resolve(packet,primary)
    locations=[primary]
    # An exact indexed record is also a specific defect location. Do not
    # generalize upward to the whole input list, argument list or inference.
    record=re.match(r'(/(?:inputs|parameters|definitions)/[0-9]+|/inference/(?:argument|locals|applications)/[0-9]+)(?:/|$)',primary)
    if record:locations.append(record[1])
    port=re.fullmatch(r'/inputs/([0-9]+)/statement',primary)
    global_object=re.match(r'/(parameters|definitions)/([0-9]+)(?:/|$)',primary)
    local=re.match(r'/inference/locals/([0-9]+)(?:/|$)',primary)
    if port:
        pid=packet['inputs'][int(port[1])]['id']
        locations.extend(f'/inference/argument/{i}'
            for i,step in enumerate(packet['inference']['argument']) if pid in step['uses'])
    elif global_object:
        symbol=packet[global_object[1]][int(global_object[2])]['symbol']
        locations.extend(f'/inference/argument/{i}'
            for i,step in enumerate(packet['inference']['argument']) if symbol in step['objects'])
    elif local:
        declaration=packet['inference']['locals'][int(local[1])]
        steps=packet['inference']['argument'];positions={step['id']:i for i,step in enumerate(steps)}
        if declaration['start'] in positions and declaration['end'] in positions:
            start,end=positions[declaration['start']],positions[declaration['end']]
            locations.extend(f'/inference/argument/{i}' for i,step in enumerate(steps)
                if i==start or (start<=i<=end and declaration['symbol'] in step['objects']))
    for pointer in locations:nl0.closure.resolve(packet,pointer)
    return list(dict.fromkeys(locations))


def prepare(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    reviewer, owner = destination / "reviewer", destination / "owner"
    reviewer.mkdir()
    owner.mkdir()
    cases = controls()
    random.SystemRandom().shuffle(cases)
    expected = {}
    for packet, verdict, reason, location in cases:
        name = uuid.uuid4().hex + ".json"
        packet["packet_sha256"] = nl0.closure.digest(packet)
        (reviewer / name).write_text(json.dumps(packet, indent=2) + "\n")
        expected[name] = {"expected_verdict": verdict, "reason": reason, "location": location,
                          "requires_library_note":packet.get('case_id')=='neutral-pointwise-operation',
                          "kind":"global" if {'problem','spec','graph'}<=packet.keys() else "packet",
                          **({'expected_target_verdict':verdict} if {'problem','spec','graph'}<=packet.keys() else {}),
                          "accepted_locations":accepted_failure_locations(packet,location),
                          "packet_sha256": packet["packet_sha256"]}
    prompt = (
        "Use the supplied clean behavioral controller to stage each record independently. "
        "Conditional packets use the actual packet math instructions; records containing an "
        "original problem/spec/graph use the actual global Audit A prompt, contract and overview. "
        "No owner key, expected label, other proof or old review is reviewer material. "
        "Judge actual content under the shared Audit A requirements; do not repair a missing proof.\n"
    )
    (reviewer / "REQUEST.txt").write_text(prompt)
    manifest = {"status": "NOT_RUN", "purpose": "Small behavioral controls, not a performance benchmark",
                "execution": "No model or isolated reviewer has been run by this preparation script.",
                "disclosure": "Only reviewer/ plus the procedure may be disclosed; keep owner/ out of the reviewing context.",
                "expected": expected}
    (owner / "expected.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return {"status": "NOT_RUN", "prepared_cases": len(expected), "reviewer_input": str(reviewer),
            "owner_only_key": str(owner / "expected.json")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="New directory; existing data is never overwritten")
    args = parser.parse_args()
    print(json.dumps(prepare(args.out), indent=2))


if __name__ == "__main__":
    main()
