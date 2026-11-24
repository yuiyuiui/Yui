"""Coverage-aware review completion and own-stage notes. No verdict is invented."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from execution_state import atomic
import artifact_protocol as protocol
from read_views import resolve


class ReviewProgressGuard:
    """Return current review work and wait only after an unanswered continuation."""
    checks = {'check_artifact', 'check_draft'}
    checkpoints = {'record_review_item', 'record_background_note'}
    submissions = checks | checkpoints | {'submit_artifact', 'submit_draft', 'submit_review_blocker'}
    submit_guidance = ('If you checked a subset, assemble the complete intended review including its notes. '
                       'Call submit_draft with the complete review when ready.')

    def __init__(self, contract):
        self.contract = contract
        self.reset()

    def reset(self):
        self.saved = self.saved_digest()
        self.seen = set()
        self.feedback = {'state':'incomplete', 'message':'Review is incomplete.',
                         'next_action':'Read the remaining items and record or submit your judgments.'}
        self.blocked = None
        self.activity = False
        self.awaiting_action = False

    @staticmethod
    def digest(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def saved_digest(self):
        # Own-stage checkpoints include optional fields such as saved background notes.
        return self.digest([self.contract.items, self.contract.base,self.contract.part_sequence])

    def resume(self):
        feedback = self.blocked['last_validation'] if self.blocked else self.feedback
        self.reset()
        self.feedback = feedback

    def candidate(self, args):
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
        return value

    def mark_work(self, work):
        key = self.digest(work)
        if key not in self.seen:
            self.seen.add(key)
            self.activity = True

    def current_feedback(self):
        remaining = [pointer for pointer, row in self.contract.items.items() if row['coverage']!='assessed']
        return {**self.feedback, 'remaining':remaining}

    def observe(self, name, args, result, *, checked=None):
        if result.get('stage_complete'):
            self.reset()
            return
        if name == 'read_review_progress':
            if 'error' not in result:
                return self.current_feedback()
            return
        if name not in self.submissions:
            if 'error' not in result:
                self.mark_work([name, args])
            return

        saved = self.saved_digest()
        if saved != self.saved:
            self.saved = saved
            self.seen.clear()
            self.activity = True
        if 'error' in result:
            self.mark_work(['correction', self.candidate(args)])
            self.feedback = {'tool':name, 'state':'validation_error', 'message':str(result['error'])[:1500],
                             'next_action':'Correct the reported field and complete any remaining review items.'}
        elif name in self.checks and result.get('accepted'):
            self.mark_work(['preview', checked if checked is not None else self.candidate(args)])
            self.feedback = {'tool':name, 'state':'preview_valid', 'message':'This preview passed validation.',
                             'next_action':self.submit_guidance}
        elif name in self.checkpoints and 'recorded' in result:
            self.feedback = {'tool':name, 'state':'checkpoint_saved', 'message':'This checkpoint is saved.',
                             'next_action':'Complete the remaining work. '+self.submit_guidance}
        else:
            return
        return self.current_feedback()

    def completed_turn(self):
        if self.activity:
            self.awaiting_action = False
        elif self.awaiting_action:
            message = 'The review did not advance after the controller asked to continue from the saved checklist.'
            self.feedback = {**self.feedback, 'pause_reason':message}
            self.blocked = {'code':'workflow_blocked','reason':'REVIEW_NO_PROGRESS',
                            'message':message,'last_validation':self.current_feedback(),
                            'progress':str(self.contract.directory/'progress.json')}
        else:
            # The next turn explicitly asks for the saved checklist and its next action.
            self.awaiting_action = True
        self.activity = False


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
        self.sequence=0;self.parts={};self.part_sequence=0;self.context=None
        self.pending_restore=(self.directory/'progress.json').exists()
        if not self.pending_restore:self._write()

    def bind_context(self, context):
        identity=ReviewProgressGuard.digest([context,self.base,self.required,self.schema])
        file=self.directory/'context.json'
        if file.exists() and json.loads(file.read_text()).get('sha256')!=identity:
            raise ValueError('Changed review inputs; preserve the old judgments and start a new review')
        if self.pending_restore:
            if not file.exists():raise ValueError('Original review inputs are not bound; do not overwrite old progress')
            saved=json.loads((self.directory/'progress.json').read_text())
            if set(saved['items'])!=set(self.required):raise ValueError('Changed review inputs or required items')
            self.items={p:self.validated_item(p,row['coverage'],row['judgment']) for p,row in saved['items'].items()}
            self.sequence=saved['sequence'];self.pending_restore=False
        self.context=identity
        if not file.exists():atomic(file,{'sha256':identity})
        for path in sorted((self.directory/'parts').glob('*/*.json')):
            value=json.loads(path.read_text())
            if value['context']!=identity:raise ValueError('Changed review inputs in a saved subjudgment')
            item=self.validated_item(value['pointer'],value['item']['coverage'],value['item']['judgment'],partial=True)
            self.parts[(value['pointer'],value['part'])]={**value,'item':item}
            self.part_sequence=max(self.part_sequence,value['sequence'])

    @classmethod
    def structured(cls, directory, shape, validator, **kwargs):
        return cls(directory, shape.base, shape.required, validator, shape=shape, **kwargs)

    def _write(self):
        if self.pending_restore:raise ValueError('Bind original review inputs before changing saved judgments')
        self.sequence+=1
        row={'schema':'yui-review-progress-1','sequence':self.sequence,'items':self.items,
             'scope':'Coverage is reviewer-reported; reading alone is not mathematical assessment.'}
        atomic(self.directory/'progress.json',row)
        atomic(self.directory/'history'/f'{self.sequence:04d}.json',row)

    def progress(self, *, pointer=None, part=None, offset=0, limit=100):
        if self.pending_restore:raise ValueError('Bind original review inputs before reading saved judgments')
        if pointer is not None or part is not None:
            if (pointer,part) not in self.parts:raise ValueError('Unknown saved review subjudgment')
            return deepcopy(self.parts[(pointer,part)])
        if type(offset) is not int or type(limit) is not int or offset<0 or not 1<=limit<=250:
            raise ValueError('Read at most 250 review subjudgment index entries')
        index=[{'pointer':p,'part':label,'coverage':row['item']['coverage']} for (p,label),row in sorted(self.parts.items())]
        return {'required':list(self.required),'items':deepcopy(self.items),
                'remaining':[p for p,row in self.items.items() if row['coverage']!='assessed'],
                'part_count':len(index),'parts':index[offset:offset+limit],
                'next_offset':offset+limit if offset+limit<len(index) else None,
                'scope':'Actual own-stage notes only; no new premise or generated PASS.'}

    def validated_item(self, pointer, coverage, judgment=None, *, partial=False):
        if pointer not in self.items or coverage not in {'unread','read','assessed'}:
            raise ValueError('Use a required review pointer and unread/read/assessed coverage')
        if coverage=='assessed':
            if not isinstance(judgment,dict):
                raise ValueError(f'{pointer}: an assessed item needs a judgment object')
            if self.shape and not partial: protocol.validate(judgment, self.shape.rows[pointer], pointer)
            if self.row_validator and not partial:self.row_validator(pointer,judgment)
            if (judgment.get('verdict') not in ('PASS','FAIL','UNVERIFIED')
                    or not isinstance(judgment.get('notes'),str) or not judgment['notes'].strip()
                    or not isinstance(judgment.get('locations'),list) or not judgment['locations']):
                raise ValueError('An assessed item needs an actual located judgment')
        elif judgment is not None:
            raise ValueError('Unread/read items have no assessed verdict; use assessed UNVERIFIED for an evaluated uncertainty')
        return {'coverage':coverage,'judgment':deepcopy(judgment)}

    def record(self, pointer, coverage, judgment=None, *, part=None):
        if part is not None:
            if self.context is None:raise ValueError('Bind review inputs before saving subjudgments')
            if not isinstance(part,str) or not part.strip() or len(part)>200:raise ValueError('Use a short stable review-part label')
            item=self.validated_item(pointer,coverage,judgment,partial=True)
            if self.parts.get((pointer,part),{}).get('item')!=item:
                self.part_sequence+=1
                value={'pointer':pointer,'part':part,'context':self.context,'sequence':self.part_sequence,'item':item,
                       'scope':'Own partial judgment only; the parent review item remains incomplete.'}
                key=ReviewProgressGuard.digest([pointer,part])
                atomic(self.directory/'parts'/key/f'{self.part_sequence:06d}.json',value)
                self.parts[(pointer,part)]=value
            return {'recorded':pointer,'part':part,'coverage':coverage,'stage_complete':False,
                    'parent_coverage':self.items[pointer]['coverage']}
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
Use record_review_item for useful checkpoints; after a context reset inspect read_review_progress.
For a long definition, premise or obligation use record_review_item with a short stable part label
to save its actual judgment now. Read part indexes, then retrieve one with read_review_progress(pointer,part).
Subjudgments do not assess the parent automatically; finish each required parent judgment yourself.
To assemble saved actual rows submit
{from_saved_review:true,summary:{...}}; use exactly the summary fields in the
generated submission schema, never saved judgment containers or fields copied
from another stage's format. No PASS is filled by the controller. A located
real blocking defect may stop early through submit_review_blocker after saving
its assessed FAIL item; untouched work stays explicitly incomplete. Do not
restart the entire review just to transcribe already saved judgments.
'''
