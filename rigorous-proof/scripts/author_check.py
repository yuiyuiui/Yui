"""Same-author closing notes. No reviewer, mathematical verdict or new model call."""
from copy import deepcopy
import hashlib
import json

from execution_state import atomic
import acceptance
import foundations


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
                                     separators=(',',':')).encode()).hexdigest()


class AuthorCheck:
    def __init__(self, contract):
        self.contract=contract
        self.reads={}
        self.notes={}
        self.acceptance=acceptance.current()
        self.open_issues={}
        self.issue_history=[]
        self.import_repair_obligations()

    def import_repair_obligations(self):
        """Import only explicitly declared warm diagnostics, never proof premises."""
        text=self.contract.documents.get('repair-obligations.json')
        if text is None:return
        row=json.loads(text)
        if (not isinstance(row,dict) or set(row)!={'version','baseline_input','baseline_content_sha256','issues'}
                or row['version']!='yui-repair-obligations-1' or row['baseline_input']=='repair-obligations.json'
                or row['baseline_input'] not in self.contract.documents):
            raise ValueError('REPAIR_ISSUES: bind an explicitly declared baseline input')
        baseline=json.loads(self.contract.documents[row['baseline_input']])
        if set(baseline)!={'spec','graph'} or digest(baseline)!=row['baseline_content_sha256']:
            raise ValueError('REPAIR_ISSUES: baseline content hash differs')
        if not isinstance(row['issues'],list):raise ValueError('REPAIR_ISSUES: issues must be an array')
        for issue in row['issues']:
            if (not isinstance(issue,dict) or set(issue)!={'id','criterion','location','note'}
                    or not isinstance(issue['id'],str) or not issue['id'] or issue['id'] in self.open_issues
                    or issue['criterion'] not in self.acceptance.rows or not isinstance(issue['note'],str) or not issue['note'].strip()):
                raise ValueError('REPAIR_ISSUES: each diagnostic needs a unique ID and shared criterion')
            self.location(baseline,issue['location'])
            self.open_issues[issue['id']]={**deepcopy(issue),'content_sha256':digest(baseline),
                'origin':'explicit warm repair-obligations.json','baseline_input':row['baseline_input']}
        self.issue_history.append({'action':'imported_declared_warm_issues','ids':list(self.open_issues),
            'baseline_content_sha256':digest(baseline),'mathematical_acceptance':False})

    @staticmethod
    def read_view(packet):
        """The complete actually displayed mathematical view, without progress metadata."""
        return {k:deepcopy(v) for k,v in packet.items()
                if k not in {'candidate','content_sha256','closing_progress'}}

    def read_receipt(self, packet):
        receipt=self.reads.get(digest(self.read_view(packet)))
        if receipt:
            path=self.contract.directory/receipt['path']
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=receipt['sha256']:
                raise ValueError('AUTHOR_CHECK: actual own-packet read evidence changed')
        return receipt

    def candidate(self, number):
        if type(number) is not int or number not in self.contract.valid_drafts:
            raise ValueError('AUTHOR_CHECK: select a structurally valid candidate from this same author stage')
        value=self.contract.valid_drafts[number]
        return value,digest(value)

    def status(self, number):
        value,key=self.candidate(number)
        graph=value['graph'];spec=value['spec']
        required=[r['id'] for r in graph['inferences']]
        note=self.notes.get(key,{})
        bound=note.get('acceptance_contract')==self.acceptance.metadata()
        receipts={rid:self.read_receipt(self.view(number,rid)) for rid in required}
        remaining=sorted(rid for rid in required if not receipts[rid])
        complete=bool(bound and note.get('coverage_complete') and not remaining)
        ready=bool(complete and note.get('readiness')=='no_known_issue' and not self.open_issues)
        status={'candidate':number,'content_sha256':key,
            'acceptance_contract':self.acceptance.metadata(),
            'criteria_by_note_group':self.acceptance.author_groups(),
            'same_author_closing_notes_complete':complete,
            'reported_readiness':note.get('readiness','not_checked') if bound else 'not_checked',
            'author_release_ready':ready,
            'open_issues':list(deepcopy(self.open_issues).values()),
            'mathematical_acceptance':False,
            'remaining_packet_reads':remaining,
            'retained_packet_reads':[{'inference':rid,**deepcopy(receipt)}
                for rid,receipt in receipts.items() if receipt and receipt['originating_candidate']!=number],
            'required_output_notes':[p['id'] for p in graph['propositions'] if p['kind'] in {'internal','target'}],
            'required_inference_notes':required,
            'original_context':{'full_target':spec['full_target'],'hypotheses':spec['hypotheses'],
                                'conclusion':spec['conclusion']},
            'scope':'Own-stage author inspection only; not Audit A, not an independent review or mathematical certification.'}
        status['next_actions']=self.next_actions(status)
        return status

    @staticmethod
    def next_actions(status):
        number=status['candidate']
        if status['remaining_packet_reads']:
            return [{'tool':'read_author_packet','arguments':{'candidate':number,'inference':rid}}
                    for rid in status['remaining_packet_reads'][:16]]
        if status['author_release_ready']:
            return [{'tool':'submit_draft','arguments':{'artifact':{'accept_candidate':number}}}]
        return [{'tool':'record_author_checks','candidate':number,
                 'required_output_ids':status['required_output_notes'],
                 'required_inference_ids':status['required_inference_notes'],
                 'pending_issue_ids':[row['id'] for row in status['open_issues']],
                 'instruction':'Supply actual located notes using the tool schema. Correct known issues in the stored proof or give a justified located resolution; do not invent readiness. Save unresolved/not_checked when work remains. Do not repeat submit without completing these actions.'}]

    def view(self, number, inference):
        """Build a view without granting an inspection receipt."""
        value,key=self.candidate(number)
        spec,graph=value['spec'],value['graph']
        rows=[r for r in graph['inferences'] if r['id']==inference]
        if len(rows)!=1:raise ValueError('AUTHOR_CHECK: choose an actual inference ID in this candidate')
        step=rows[0];props={p['id']:p for p in graph['propositions']};defs={d['id']:d for d in spec['definitions']}
        ports=[props[x] for x in [*step['inputs'],step['output']]]
        selected=set(step['definitions'])
        for p in ports:selected.update(p['definitions'])
        pending=list(selected)
        while pending:
            for did in defs[pending.pop()]['depends_on']:
                if did not in selected:selected.add(did);pending.append(did)
        def port(p):
            out={k:deepcopy(p[k]) for k in ['id','kind','statement','definitions','binders','objects']}
            if p['kind'] in {'mathlib','external'}:
                out['source_conditions']=deepcopy(p['source']['hypotheses'])
                if p['kind']=='mathlib':out['source_declaration']=p['source']['declaration']
            return out
        packet={'candidate':number,'content_sha256':key,'parameters':deepcopy(spec['parameters']),
            'logic':foundations.packet_logic(spec['logic']),
            'acceptance_contract':self.acceptance.metadata(),
            'definitions':[deepcopy(defs[x]) for x in sorted(selected)],
            'inputs':[port(p) for p in ports[:-1]],'output':port(ports[-1]),'inference':deepcopy(step),
            'warning':'Read this as the same author: only listed inputs, definitions and fixed logic are available. No ancestor/other producer bodies or extra H are supplied. Inspect source types separately in your actual probe. This read produces no judgment.'}
        return packet

    def packet(self, number, inference):
        packet=self.view(number,inference)
        view=self.read_view(packet);key=digest(view)
        if not self.read_receipt(packet):
            path=self.contract.directory/f'author-packet-read-{key}-{number:04d}.json'
            atomic(path,{'packet_sha256':key,'originating_candidate':number,'packet':view,
                'scope':'Actual same-author tool view only; no mathematical judgment or independent review.'})
            self.reads[key]={'originating_candidate':number,'path':path.name,
                'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'packet_sha256':key}
        status=self.status(number)
        packet['closing_progress']={k:status[k] for k in ['remaining_packet_reads','retained_packet_reads','required_output_notes','required_inference_notes','same_author_closing_notes_complete','author_release_ready','open_issues','criteria_by_note_group','next_actions']}
        packet['closing_progress']['next_action']=(
            'Inspect any remaining own packets; if you find a concrete defect, make a coherent local correction. '
            'When the actual proof is complete, record_author_checks with the exact tool fields and submit the same candidate. '
            'Do not repeat an unchanged structural check as a substitute for your closing notes.')
        atomic(self.contract.directory/'author-check-progress.json',status)
        return packet

    @staticmethod
    def location(value, pointer):
        if not isinstance(pointer,str) or not pointer.startswith('/'):
            raise ValueError('AUTHOR_CHECK: locate an issue/resolution in the actual candidate with an absolute JSON pointer')
        try:
            for part in pointer[1:].split('/'):
                part=part.replace('~1','/').replace('~0','~')
                if isinstance(value,list):
                    if not part.isdigit():raise ValueError('invalid array index')
                    value=value[int(part)]
                else:value=value[part]
        except (KeyError,IndexError,TypeError,ValueError) as error:
            raise ValueError('AUTHOR_CHECK: issue/resolution location does not exist: '+pointer) from error

    def record(self, number, context_note, output_notes, inference_notes, *,
               readiness='not_checked', open_issues=None, resolutions=None):
        value,key=self.candidate(number);status=self.status(number)
        if readiness not in {'no_known_issue','unresolved','not_checked'}:
            raise ValueError('AUTHOR_CHECK: readiness is no_known_issue, unresolved or not_checked; it is not a mathematical verdict')
        if readiness=='no_known_issue' and status['remaining_packet_reads']:
            raise ValueError('AUTHOR_CHECK: read each own conditional packet first: '+repr(status['remaining_packet_reads']))
        if not isinstance(context_note,str) or not context_note.strip():
            raise ValueError('AUTHOR_CHECK: give the actual comparison with the original problem, hypotheses and target')
        def check(rows,ids,fields,label):
            if not isinstance(rows,list) or any(not isinstance(row,dict) or set(row)!={'id',*fields} for row in rows):
                raise ValueError('AUTHOR_CHECK: '+label+' must contain records with id and '+repr(fields))
            if any(not isinstance(row['id'],str) for row in rows):
                raise ValueError('AUTHOR_CHECK: note IDs must be existing string IDs')
            actual=[row['id'] for row in rows]
            if (len(set(actual))!=len(actual) or not set(actual)<=set(ids) or
                    (readiness=='no_known_issue' and set(actual)!=set(ids))):
                raise ValueError('AUTHOR_CHECK: exact '+label+' coverage required: '+repr(ids))
            if any(not isinstance(row[f],str) or not row[f].strip() for row in rows for f in fields):
                raise ValueError('AUTHOR_CHECK: write actual located notes; empty notes are not checks')
        check(output_notes,status['required_output_notes'],['note'],'output notes')
        check(inference_notes,status['required_inference_notes'],
              ['dependency_and_local_assumption_check','source_application_check','declaration_check'],'inference notes')
        issues=[] if open_issues is None else open_issues
        resolved=[] if resolutions is None else resolutions
        if not isinstance(issues,list) or not isinstance(resolved,list):
            raise ValueError('AUTHOR_CHECK: open_issues and resolutions are arrays')
        pending=deepcopy(self.open_issues);seen=set();history=[]
        for row in resolved:
            if (not isinstance(row,dict) or set(row)!={'id','location','note'} or
                    not isinstance(row['id'],str) or row['id'] not in pending or row['id'] in seen or
                    not isinstance(row['note'],str) or not row['note'].strip()):
                raise ValueError('AUTHOR_CHECK: each resolution names one existing open ID, an actual location and its correction/justified withdrawal')
            self.location(value,row['location']);seen.add(row['id'])
            history.append({'action':'author_reported_resolved','issue':pending.pop(row['id']),
                            'resolution':deepcopy(row),'content_sha256':key})
        for row in issues:
            if (not isinstance(row,dict) or set(row)!={'id','criterion','location','note'} or
                    not isinstance(row['id'],str) or not row['id'].strip() or row['id'] in seen or
                    not isinstance(row['criterion'],str) or row['criterion'] not in self.acceptance.rows or
                    not isinstance(row['note'],str) or not row['note'].strip()):
                raise ValueError('AUTHOR_CHECK: each open issue needs a unique id, shared criterion, actual location and explanation')
            self.location(value,row['location']);seen.add(row['id'])
            pending[row['id']]=dict(deepcopy(row),content_sha256=key)
            history.append({'action':'author_reported_open','issue':deepcopy(pending[row['id']])})
        if readiness=='no_known_issue' and pending:
            raise ValueError('AUTHOR_CHECK: known unresolved issues still block release: '+repr(sorted(pending))+
                             '. Continue local completion or record readiness=unresolved; omitted old issues remain open until explicit resolutions.')
        if readiness=='unresolved' and not pending:
            raise ValueError('AUTHOR_CHECK: unresolved readiness needs a located open issue; otherwise use not_checked')
        coverage=(not status['remaining_packet_reads'] and
            {r['id'] for r in output_notes}==set(status['required_output_notes']) and
            {r['id'] for r in inference_notes}==set(status['required_inference_notes']))
        record={'content_sha256':key,'same_author':True,'mathematical_acceptance':False,
                'acceptance_contract':self.acceptance.metadata(),
                'readiness':readiness,'coverage_complete':coverage,
                'open_issues':list(pending.values()),'resolutions':deepcopy(resolved),
                'criteria_by_note_group':self.acceptance.author_groups(),
                'original_context_note':context_note,'output_notes':deepcopy(output_notes),
                'inference_notes':deepcopy(inference_notes),
                'scope':'Author notes, not Audit A. No independent feedback was supplied. Exclude these notes from fresh independent audit inputs.'}
        self.notes[key]=record
        self.open_issues=pending
        self.issue_history.extend(history)
        atomic(self.contract.directory/f'author-check-{key}.json',record)
        atomic(self.contract.directory/'author-issue-history.json',self.issue_history)
        atomic(self.contract.directory/'author-check-progress.json',self.status(number))
        return self.status(number)
