"""Case-local proof progress and obstruction routing; never mathematical acceptance."""
from __future__ import annotations

import hashlib
import json
import threading

POLICY = {'version':'proof-progress-and-repair-2', 'completed_idle_turns':None,
          'scope':'Passive progress accounting; only explicit located reports request repair.'}


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


class RoundInterrupted(Exception):
    """Retire this proof round for serial diagnosis, distinct from user cancellation."""


class RoundControl:
    """Legacy report container; a node report does not cancel sibling work."""
    def __init__(self):
        self.event=threading.Event();self.lock=threading.Lock();self.reports={}

    def request(self, step, report):
        with self.lock:self.reports[step]=report

    def check(self):
        return None


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
    ir.need(isinstance(value,dict) and set(value)==required,'Obstruction needs layer, explanation, locations and candidates')
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
    report={'version':POLICY['version'],'step':stage.step,'reason':'NO_OBSERVABLE_PROGRESS' if automatic else 'WORKER_REPORTED_OBSTRUCTION',
            **value,'contract_sha256':ir.digest(stage.cpath),'plan_sha256':digest(stage.plan),
            'packet_sha256':digest(packet),'candidate_evidence':evidence,
            'progress':stage.proof_progress.metadata(),
            'acceptance':False,'scope':'Allegation and actual local evidence only; serial diagnosis and fresh review decide the repair boundary.'}
    # This identity excludes prose, counters and timestamps. It records repeated
    # evidence without authorizing a stop or a fresh-context verdict resample.
    report['evidence_key']=digest([report['packet_sha256'],sorted(stage.proof_progress.seen)])
    return report
