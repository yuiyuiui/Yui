"""Case-local proof progress and obstruction routing; never mathematical acceptance."""
from __future__ import annotations

import hashlib
import json
import re

POLICY = {'version':'proof-progress-and-repair-3', 'completed_idle_turns':None,
          'scope':'A diagnosis request keeps the author active; only a qualified defect authorizes handoff.'}


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def resource_only(result):
    """Resource advice can coexist with an earlier ordinary compiler error."""
    from strategy_bank import native_timeout_kind
    if not native_timeout_kind(result):return False
    text=result.get('stdout','')+'\n'+result.get('stderr','')
    errors=re.findall(r'^.*\.lean:\d+:\d+:\s+error(?:\([^\n)]*\))?:([^\n]*)',text,re.MULTILINE)
    return all('timeout' in message and 'heartbeat' in message for message in errors)


class RoundInterrupted(Exception):
    """Retire this proof round for serial diagnosis, distinct from user cancellation."""




class Progress:
    def __init__(self):
        self.seen=set();self.checks=set();self.revision=0;self.last_turn_revision=0
        self.idle_turns=0;self.last_progress_at=None;self.last_check_at=None

    def observe(self, tool, args, result, at):
        # A fresh failed check is useful evidence. Repeating the same candidate,
        # index read or identical lookup cannot indefinitely simulate progress.
        if result.get('error') and 'exit_code' not in result:return
        family='transition' if tool in {'check_transition','submit_transition'} else tool
        if family in {'transition','check_auxiliary'}:
            key=digest([family,args]);self.checks.add(key);self.last_check_at=at
        elif tool in {'search_mathlib','read_mathlib','read_background_note','find_strategies'}:
            key=digest([family,args])
        else:return
        if key not in self.seen:
            self.seen.add(key);self.revision+=1;self.last_progress_at=at

    def completed_turn(self):
        self.idle_turns=self.idle_turns+1 if self.revision==self.last_turn_revision else 0
        self.last_turn_revision=self.revision
        return False

    def metadata(self):
        return {'policy':POLICY['version'],'distinct_actions':len(self.seen),
                'distinct_check_candidates':len(self.checks),'completed_idle_turns':self.idle_turns,
                'last_progress_at_utc':self.last_progress_at,'last_check_at_utc':self.last_check_at}


def obstruction(stage, value, *, automatic=False):
    """Only local resolving locators and actual own checks can enter a report."""
    import audit_b
    import ir
    required={'layer','explanation','locations','candidates'}
    ir.need(isinstance(value,dict) and required <= set(value) <= required|{'source_issue'},
            'Obstruction needs layer, explanation, locations and candidates')
    ir.need(value['layer'] in {'local_proof','interface','source','unknown'},'Unknown alleged obstruction layer')
    ir.need(isinstance(value['explanation'],str) and 1<=len(value['explanation'].strip())<=12000,
            'Provide a bounded concrete obstruction explanation')
    ir.need(isinstance(value['locations'],list) and 1<=len(value['locations'])<=12,'Locate the actual current packet fields')
    packet=ir.local_packet(stage.cpath,stage.plan,stage.step)
    for pointer in value['locations']:
        ir.need(isinstance(pointer,str) and pointer.startswith('/'),'Use an absolute local-packet JSON pointer')
        audit_b.resolve(packet,pointer)
    ir.need(isinstance(value['candidates'],list) and len(value['candidates'])<=6,'Reference at most six own attempts')
    evidence=[]
    for item in value['candidates']:
        ir.need(isinstance(item,dict) and set(item)=={'kind','candidate'},'Reference kind and candidate only')
        kind=item['kind'];number=item['candidate']
        ir.need(kind in {'proof','auxiliary'} and type(number) is int
                and number in stage.own_lean_drafts[kind],'Unknown own-stage candidate')
        row=stage.own_lean_drafts[kind][number]
        ir.need(isinstance(row.get('check'),dict),'No actual check evidence for this candidate')
        evidence.append({'kind':kind,'candidate':number,'sha256':digest(row)})
    ir.need(value['layer']!='local_proof',
            'Ordinary proof-body errors stay with this author; repair locally and recheck')
    if value['layer'] in {'interface','unknown'}:
        ir.need(evidence and any(stage.own_lean_drafts[x['kind']][x['candidate']]['check'].get('exit_code',0)!=0
                                 for x in value['candidates']),
                'A compiler/interface obstruction needs an actual failed own-context check; supply relevant evidence and continue this stage')
    else:
        ir.need(any(p.startswith('/source_steps/') for p in value['locations']),
                'A source obstruction needs a concrete original source location')
        validate_source_issue(value.get('source_issue'),packet)
    report={'version':POLICY['version'],'step':stage.step,'reason':'NO_OBSERVABLE_PROGRESS' if automatic else 'WORKER_REPORTED_OBSTRUCTION',
            **value,'contract_sha256':ir.digest(stage.cpath),'plan_sha256':digest(stage.plan),
            'packet_sha256':digest(packet),'candidate_evidence':evidence,
            'progress':stage.proof_progress.metadata(),
            'acceptance':False,'scope':'Allegation and actual local evidence only; serial diagnosis and fresh review decide the repair boundary.'}
    # This identity excludes prose, counters and timestamps. It records repeated
    # evidence without authorizing a stop or a fresh-context verdict resample.
    stable=[]
    for item in value['candidates']:
        row=stage.own_lean_drafts[item['kind']][item['candidate']]
        helpers=row.get('proof_package',{})
        helpers=helpers.get('helpers',[]) if isinstance(helpers,dict) else []
        stable.append(digest([item['kind'],row['statement'],row['proof'],
            [r['sha256'] for r in helpers],row['check'].get('exit_code'),row['check'].get('error_kind')]))
    report['evidence_key']=digest([report['packet_sha256'], sorted(value['locations']),
                                  sorted(stable), value.get('source_issue')])
    return report


def validate_source_issue(value, packet):
    """Require a concrete mathematical allegation, never certify its truth."""
    import ir
    fields={'kind','source_quote','hypotheses','claim','defect','why_not_lean_difficulty'}
    ir.need(isinstance(value,dict) and set(value)==fields,
            'A source issue needs kind, source_quote, hypotheses, claim, defect and why_not_lean_difficulty')
    ir.need(value['kind'] in {'FALSE_IMPLICATION','MISSING_JUSTIFICATION'},'Unknown mathematical issue kind')
    for key in fields-{'kind'}:
        ir.need(isinstance(value[key],str) and 1<=len(value[key].strip())<=12000,
                'Provide concrete mathematical source evidence: '+key)
    source='\n'.join(str(s.get('text','')) for s in packet['source_steps'])
    ir.need(value['source_quote'] in source,'The source issue must quote the current NL step verbatim')
    return value
