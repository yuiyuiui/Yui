"""Read-only artifact-scoped progress. Submission/lifecycle are not proof verdicts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import nl0


def load(path):
    return json.loads(Path(path).read_text())


def binding(path):
    path=Path(path).resolve()
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def project(source, *, interface=None, interface_review=None, workflow=None):
    source=Path(source).resolve()
    value={'schema':'yui-case-status-1','source':str(source),
        'gates':{'nl0_structure':'NOT_CHECKED','audit_a':'NOT_PASSED','ir_types':'NOT_CHECKED',
                 'ir_semantics':'NOT_PASSED','lean_assembly':'NOT_PASSED','audit_b':'NOT_PASSED'},
        'bindings':{},'findings':[], 'full_acceptance':False,
        'scope':'Exact supplied artifact revisions only; no raw report is changed or model called.'}
    data=nl0.validate(source/'nl0.json',source/'spec.json')
    value['case_id']=data[0]['case_id'];value['gates']['nl0_structure']='VALID'
    value['bindings'].update({name:binding(source/name) for name in ['nl0.json','spec.json']})
    for name in ['audit-a.json','audit-a.pending.json']:
        if not (source/name).is_file():continue
        try:
            inspected=nl0.validate(source/'nl0.json',source/'spec.json',source/name,allow_unresolved=True)[0]
            value['gates']['audit_a']='PASSED' if name=='audit-a.json' and inspected['current_standard_receipt_valid'] else 'NOT_PASSED'
            value['bindings']['audit_a']=binding(source/name)
            value['audit_a_unresolved']=inspected.get('unresolved_reviews',[])
        except ValueError as error:value['findings'].append({'gate':'audit_a','error':str(error)})
        break
    if interface:
        interface=Path(interface)
        paths=interface/'accepted-interface-paths.json'
        if paths.is_file():
            c=Path(load(paths)['contract']);contract=load(c)
            if contract['source']['sha256']==value['bindings']['nl0.json']['sha256']:
                result=c.parent/'types/result.json'
                if result.is_file() and load(result).get('exit_code')==0:
                    value['gates']['ir_types']='CHECKED_NOT_PROVED';value['bindings']['typed_contract']=binding(c)
    if interface_review:
        review=Path(interface_review)
        pairs=load(review/'bindings.json')
        if pairs['source_graph']['sha256']!=value['bindings']['nl0.json']['sha256']:
            value['findings'].append({'gate':'ir_semantics','error':'Review belongs to a different source revision'})
        else:
            value['bindings']['interface_review']=binding(review/'bindings.json')
            raw=load(review/'stage/accepted.json') if (review/'stage/accepted.json').is_file() else {}
            if (review/'report.json').is_file():
                value['gates']['ir_semantics']='PASSED' if load(review/'report.json').get('all_checks_passed') else 'NOT_PASSED'
            value['interface_actual_judgments']=raw.get('checks',{})
    if workflow:
        workflow=Path(workflow)
        if (workflow/'manifest.json').is_file():
            # Use the authority reader rather than trusting a report label.
            import sys
            sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'nl02lean/scripts'))
            import workflow as controller
            frozen=controller.bound(workflow)
            if binding(frozen['authority']['graph'])!=value['bindings']['nl0.json']:
                raise ValueError('Workflow/source revisions differ')
            proof=workflow/'proof-run/report.json'
            if proof.is_file():value['gates']['lean_assembly']=load(proof).get('status','NOT_PASSED')
            final=workflow/'report.json'
            if final.is_file() and load(final).get('status')=='WORKFLOW-PASSED':
                # The stored result must still pass the existing bound-input gate.
                report=load(final)
                for item in report['bindings']:
                    if binding(item['path'])!=item:raise ValueError('Final workflow evidence changed')
                value['gates']['audit_b']='PASSED';value['full_acceptance']=True
    return value
