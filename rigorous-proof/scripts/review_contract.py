"""Coverage-aware review completion and own-stage notes. No verdict is invented."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from execution_state import atomic


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
    def __init__(self, directory, base, required, validator, *, row_validator=None, finding_validator=None):
        self.directory=Path(directory)
        self.directory.mkdir(parents=True,exist_ok=True)
        self.base=deepcopy(base)
        self.required=tuple(sorted(required))
        if len(set(self.required))!=len(self.required) or any(not p.startswith('/') for p in self.required):
            raise ValueError('Review keys must be unique absolute pointers')
        self.validator=validator
        self.row_validator=row_validator
        self.finding_validator=finding_validator
        self.items={p:{'coverage':'unread','judgment':None} for p in self.required}
        self.sequence=0
        self._write()

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

    def record(self, pointer, coverage, judgment=None):
        if pointer not in self.items or coverage not in {'unread','read','assessed'}:
            raise ValueError('Use a required review pointer and unread/read/assessed coverage')
        if coverage=='assessed':
            if (not isinstance(judgment,dict) or judgment.get('verdict') not in {'PASS','FAIL','UNVERIFIED'}
                    or not isinstance(judgment.get('notes'),str) or not judgment['notes'].strip()
                    or not isinstance(judgment.get('locations'),list) or not judgment['locations']):
                raise ValueError('An assessed item needs an actual located judgment')
            if self.row_validator: self.row_validator(pointer,judgment)
        elif judgment is not None:
            raise ValueError('Unread/read items have no assessed verdict; use assessed UNVERIFIED for an evaluated uncertainty')
        self.items[pointer]={'coverage':coverage,'judgment':deepcopy(judgment)}
        self._write()
        remaining=[p for p,row in self.items.items() if row['coverage']!='assessed']
        return {'recorded':pointer,'coverage':coverage,'stage_complete':False,
                'assessed_count':len(self.items)-len(remaining),'required_count':len(self.items),
                'remaining':remaining,
                'scope':'Acknowledgment only. Full actual notes remain saved; read_review_progress retrieves them.'}

    def __call__(self, artifact):
        if artifact.get('from_saved_review') is True:
            if set(artifact)!={'from_saved_review','summary'} or not isinstance(artifact['summary'],dict):
                raise ValueError('Saved completion needs {from_saved_review:true,summary:{reviewer-supplied remaining fields}}')
            value=deepcopy(self.base)
            for pointer,row in self.items.items():
                if row['coverage']=='assessed': put(value,pointer,row['judgment'])
            # Summary cannot overwrite a stored judgment or invent a missing one.
            for key,row in artifact['summary'].items():
                if any(p=='/'+key or p.startswith('/'+key+'/') for p in self.required):
                    raise ValueError('Summary may not replace saved review items: '+key)
                value[key]=deepcopy(row)
        else:
            value=deepcopy(artifact)
            coverage=value.pop('coverage',None)
            if not isinstance(coverage,dict) or set(coverage)!=set(self.required):
                raise ValueError('Provide coverage for exactly every required review pointer, or use record_review_item and from_saved_review')
            for pointer,state in coverage.items():
                try: row=get(value,pointer) if state=='assessed' else None
                except (KeyError,TypeError): raise ValueError('Missing assessed review item '+pointer)
                self.record(pointer,state,row)
        remaining=[p for p,row in self.items.items() if row['coverage']!='assessed']
        if remaining:
            raise ValueError('REVIEW_INCOMPLETE: continue these items in this same stage/budget: '+', '.join(remaining))
        checked=self.validator(value)
        artifact.clear();artifact.update(value)
        return {**(checked or {}),'review_coverage':'COMPLETE',
                'scope':'Complete reviewer-reported assessment, not automatic mathematical approval.'}

    def blocker(self, finding):
        if (not isinstance(finding,dict) or finding.get('verdict')!='FAIL'
                or not finding.get('explanation') or not finding.get('locations')
                or not any(r['coverage']=='assessed' and r['judgment']['verdict']=='FAIL' for r in self.items.values())):
            raise ValueError('An early blocker needs a located FAIL finding and a saved assessed FAIL item')
        if self.finding_validator:self.finding_validator(finding)
        return {'status':'REVIEW_BLOCKED_INCOMPLETE','coverage':self.progress(),
                'findings':[deepcopy(finding)],'mathematical_acceptance':False}


INSTRUCTIONS='''
Review completion contract: coverage is separate from verdict. Required review
item pointers are listed below. For a full draft add coverage:{pointer:"assessed"
|"read"|"unread",...}. A not-yet-examined item is unread/read, not an assessed
UNVERIFIED judgment. An actually evaluated uncertainty can be assessed UNVERIFIED
with its specific reason. An ordinary incomplete draft continues in this same
stage and remaining budget. Save work with record_review_item; after a context
reset inspect read_review_progress. To assemble saved actual rows submit
{from_saved_review:true,summary:{...}}; summary supplies remaining required fields
(including your actual overall verdict/notes where requested and findings),
never saved judgment containers. No PASS is filled by the controller. A located
real blocking defect may stop early through submit_review_blocker after saving
its assessed FAIL item; untouched work stays explicitly incomplete. Do not
restart the entire review just to transcribe already saved judgments.
'''
