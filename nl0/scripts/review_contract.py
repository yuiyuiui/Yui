"""Coverage-aware review completion and own-stage notes. No verdict is invented."""
from __future__ import annotations

from copy import deepcopy
from collections import deque
import hashlib
import json
from pathlib import Path

from execution_state import atomic
import artifact_protocol as protocol


class ReviewProgressGuard:
    """Bound repeated rejected review operations; elapsed time is never progress evidence."""
    submissions = {'check_artifact', 'submit_artifact', 'check_draft', 'submit_draft', 'record_review_item',
                   'submit_review_blocker'}

    def __init__(self, contract):
        self.contract = contract
        self.reset()

    def reset(self):
        self.sequence = self.contract.sequence
        self.failures = deque(maxlen=12)
        self.reads = deque(maxlen=64)
        self.feedback = {'message':'Review is incomplete. Read the remaining items and record or submit your judgments.'}
        self.blocked = None
        self.activity = False
        self.empty_turns = 0

    @staticmethod
    def digest(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def observe(self, name, args, result):
        if self.contract.sequence != self.sequence:
            self.sequence = self.contract.sequence
            self.empty_turns = 0
            self.activity = True
            self.feedback = {'message':'Saved review progress; complete the remaining items or submit.'}
        if name not in self.submissions:
            if self.feedback and 'error' not in result and name != 'read_review_progress':
                key = self.digest([name,args])
                if key not in self.reads:
                    self.reads.append(key)
                    self.activity = True
            return
        if result.get('stage_complete'):
            self.reset()
            return
        error = result.get('error')
        if error is None:
            if not (result.get('accepted') or result.get('remaining') == []):
                return
            error = 'All required items checked; submit the completed review or revise its judgments.'
        value = args.get('artifact', args)
        if 'artifact_json' in args:
            try: value = json.loads(args['artifact_json'])
            except (ValueError,TypeError): pass
        # Compare materialized content across JSON/string, check/submit and saved wrappers.
        if isinstance(value, dict) and value.get('from_saved_review') is True:
            try:
                value = self.contract.saved_value(value)
                value['coverage'] = {p:row['coverage'] for p,row in self.contract.items.items()}
            except ValueError:
                pass  # Invalid wrapper: preserve it as the rejected candidate.
        error = str(error)
        saved = self.digest(self.contract.items)
        key = self.digest([value, saved, error])
        location, _, detail = error.partition(':')
        family = location if location.startswith('/') and 'unexpected=' in detail else error
        self.failures.append((key, (saved, family)))
        self.activity = True
        self.feedback = {'tool':name, 'message':error[:1500], 'candidate_sha256':key}
        if sum(k == key for k, _ in self.failures) >= 3:
            self.stop('The same effective review and validation error recurred three times.')
        elif sum(f == (saved, family) for _, f in self.failures) >= 6:
            self.stop('Six attempts repeated the same validation defect without a new saved assessment.')

    def completed_turn(self):
        if not self.feedback:
            return
        self.empty_turns = 0 if self.activity else self.empty_turns + 1
        self.activity = False
        if self.empty_turns >= 3:
            self.stop('Three completed turns made no new review attempt, saved assessment or evidence read.')

    def stop(self, message):
        self.blocked = {'code':'workflow_blocked','reason':'REVIEW_NO_PROGRESS',
                        'message':message, 'last_validation':self.feedback,
                        'progress':str(self.contract.directory/'progress.json')}


def put(document, pointer, value):
    parts=pointer[1:].split('/')
    parent=document
    for part in parts[:-1]: parent=parent.setdefault(part,{})
    parent[parts[-1]]=deepcopy(value)


def get(document, pointer):
    value=document
    for part in pointer[1:].split('/'): value=value[part]
    return value


class ReviewContract:
    """Wrap a mathematical review adapter with factual coverage accounting.

    `base` contains only controller-owned identities and empty containers. Every
    verdict/summary/finding is still supplied by the actual reviewer. Old raw
    judgments remain inspectable; only new stages require this completion form.
    """
    def __init__(self, directory, base, required, validator, *, row_validator=None, finding_validator=None,
                 complete_assessment=False, judgment_schema=None, shape=None):
        self.directory=Path(directory)
        self.directory.mkdir(parents=True,exist_ok=True)
        self.base=deepcopy(base)
        self.required=tuple(sorted(required))
        if len(set(self.required))!=len(self.required) or any(not p.startswith('/') for p in self.required):
            raise ValueError('Review keys must be unique absolute pointers')
        self.validator=validator
        self.shape=shape
        self.schema=deepcopy(shape.schema) if shape else None
        self.row_validator=row_validator
        self.judgment_schema = judgment_schema or {'type':['object','null'],'additionalProperties':True}
        self.finding_validator=finding_validator
        self.complete_assessment=complete_assessment
        self.items={p:{'coverage':'unread','judgment':None} for p in self.required}
        self.sequence=0
        self._write()

    @classmethod
    def structured(cls, directory, shape, validator, **kwargs):
        return cls(directory, shape.base, shape.required, validator, shape=shape, **kwargs)

    def _write(self):
        self.sequence+=1
        row={'schema':'yui-review-progress-1','sequence':self.sequence,'items':self.items,
             'scope':'Coverage is reviewer-reported; reading alone is not mathematical assessment.'}
        atomic(self.directory/'progress.json',row)
        atomic(self.directory/'history'/f'{self.sequence:04d}.json',row)

    def progress(self):
        return {'required':list(self.required),'items':deepcopy(self.items),
                'remaining':[p for p,row in self.items.items() if row['coverage']!='assessed'],
                'scope':'Actual own-stage notes only; no new premise or generated PASS.'}

    def validated_item(self, pointer, coverage, judgment=None):
        if pointer not in self.items or coverage not in {'unread','read','assessed'}:
            raise ValueError('Use a required review pointer and unread/read/assessed coverage')
        if coverage=='assessed':
            if not isinstance(judgment,dict):
                raise ValueError(f'{pointer}: an assessed item needs a judgment object')
            if self.shape: protocol.validate(judgment, self.shape.rows[pointer], pointer)
            if self.row_validator: self.row_validator(pointer,judgment)
            if (judgment.get('verdict') not in ('PASS','FAIL','UNVERIFIED')
                    or not isinstance(judgment.get('notes'),str) or not judgment['notes'].strip()
                    or not isinstance(judgment.get('locations'),list) or not judgment['locations']):
                raise ValueError('An assessed item needs an actual located judgment')
        elif judgment is not None:
            raise ValueError('Unread/read items have no assessed verdict; use assessed UNVERIFIED for an evaluated uncertainty')
        return {'coverage':coverage,'judgment':deepcopy(judgment)}

    def record(self, pointer, coverage, judgment=None):
        item = self.validated_item(pointer,coverage,judgment)
        self._commit({pointer:item})
        remaining=[p for p,row in self.items.items() if row['coverage']!='assessed']
        return {'recorded':pointer,'coverage':coverage,'stage_complete':False,
                'assessed_count':len(self.items)-len(remaining),'required_count':len(self.items),
                'remaining':remaining,
                'scope':'Acknowledgment only. Full actual notes remain saved; read_review_progress retrieves them.'}

    def _commit(self, items):
        if any(self.items[p] != row for p,row in items.items()):
            self.items.update(items)
            self._write()

    def saved_value(self, artifact):
        if set(artifact)!={'from_saved_review','summary'} or not isinstance(artifact['summary'],dict):
            raise ValueError('Saved completion needs {from_saved_review:true,summary:{reviewer-supplied remaining fields}}')
        value=deepcopy(self.base)
        for pointer,row in self.items.items():
            if row['coverage']=='assessed': put(value,pointer,row['judgment'])
        for key,row in artifact['summary'].items():
            if any(p=='/'+key or p.startswith('/'+key+'/') for p in self.required):
                raise ValueError('Summary may not replace saved review items: '+key)
            value[key]=deepcopy(row)
        return value

    def __call__(self, artifact):
        if self.shape: protocol.validate(artifact, self.schema)
        candidate = self.items
        if artifact.get('from_saved_review') is True:
            value = self.saved_value(artifact)
        else:
            value=deepcopy(artifact)
            coverage=value.pop('coverage',None)
            if not isinstance(coverage,dict) or set(coverage)!=set(self.required):
                raise ValueError('Provide coverage for exactly every required review pointer, or use record_review_item and from_saved_review')
            candidate = {}
            for pointer,state in coverage.items():
                try: row=get(value,pointer) if state=='assessed' else None
                except (KeyError,TypeError): raise ValueError('Missing assessed review item '+pointer)
                candidate[pointer] = self.validated_item(pointer,state,row)
        remaining=[p for p,row in candidate.items() if row['coverage']!='assessed']
        if remaining:
            # Explicit partial coverage can add validated work, but cannot erase an assessment.
            self._commit({p:row for p,row in candidate.items()
                          if row['coverage']=='assessed' or self.items[p]['coverage']=='unread'})
            raise ValueError('REVIEW_INCOMPLETE: continue these items in this same stage/budget: '+', '.join(remaining))
        if self.shape: self.shape.validate(value)
        checked=self.validator(value)
        self._commit(candidate)
        artifact.clear();artifact.update(value)
        return {**(checked or {}),'review_coverage':'COMPLETE',
                'scope':'Complete reviewer-reported assessment, not automatic mathematical approval.'}

    def blocker(self, finding):
        if self.complete_assessment:
            raise ValueError('Complete all assigned global checks and return the findings together; an ordinary finding cannot end global review early')
        protocol.validate(finding,self.blocker_schema(),'/finding')
        if (not isinstance(finding,dict) or finding.get('verdict')!='FAIL'
                or not finding.get('explanation') or not finding.get('locations')
                or not any(r['coverage']=='assessed' and r['judgment']['verdict']=='FAIL' for r in self.items.values())):
            raise ValueError('An early blocker needs a located FAIL finding and a saved assessed FAIL item')
        if self.finding_validator:self.finding_validator(finding)
        return {'status':'REVIEW_BLOCKED_INCOMPLETE','coverage':self.progress(),
                'findings':[deepcopy(finding)],'mathematical_acceptance':False}

    def blocker_schema(self):
        base=protocol.obj({'verdict':protocol.literal('FAIL'),'explanation':protocol.TEXT,
                           'locations':protocol.array({},minItems=1)},extra=True)
        if self.shape and 'findings' in self.shape.summary_schema['properties']:
            return {'type':'object','allOf':[base,self.shape.summary_schema['properties']['findings']['items']]}
        return base


INSTRUCTIONS='''
Review completion contract: coverage is separate from verdict. Required review
item pointers are listed below. For a full draft add coverage:{pointer:"assessed"
|"read"|"unread",...}. A not-yet-examined item is unread/read, not an assessed
UNVERIFIED judgment. An actually evaluated uncertainty can be assessed UNVERIFIED
with its specific reason. An ordinary incomplete draft continues in this same
stage and remaining budget. Prefer a complete artifact with all actual judgments and coverage in one submission.
Use record_review_item for useful checkpoints; after a context reset inspect read_review_progress. To assemble saved actual rows submit
{from_saved_review:true,summary:{...}}; use exactly the summary fields in the
generated submission schema, never saved judgment containers or fields copied
from another stage's format. No PASS is filled by the controller. A located
real blocking defect may stop early through submit_review_blocker after saving
its assessed FAIL item; untouched work stays explicitly incomplete. Do not
restart the entire review just to transcribe already saved judgments.
'''
