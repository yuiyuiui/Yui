"""Move the verified local graph-return boundary into a fresh native case."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys

import basis
from controller_common import CORE, bind, verify_bindings, write
import execution_state
import frozen_graph
import graph_repair
import jobs


VERSION = 'yui-graph-continuation-1'
FILENAME = 'graph-continuation.json'


def load(path):
    return json.loads(Path(path).read_bytes())


def descriptor(job):
    root = Path(job['root'])
    reference = job['graph_continuation']
    if (job.get('resume') or job.get('workflow_protocol') != 'yui-workflow-1'
            or job['track'] != 'full' or basis.mode(job) != 'unconditional'
            or Path(reference['path']) != root/FILENAME):
        raise ValueError('Invalid graph continuation job')
    verify_bindings([reference])
    value = load(reference['path'])
    fixed = [value['global'], value['repair'], value['basis'], *value['historical_jobs']]
    if (value['version'] != VERSION or value['current_run_id'] != job['run_id']
            or value['current_directory'] != str(root) or not value['historical_jobs']
            or any(not Path(row['path']).is_relative_to(root) for row in fixed)
            or value['basis']['path'] != str(root/'handoffs/foundations.json')):
        raise ValueError('Continuation evidence escapes its owned run')
    verify_bindings(fixed)
    return value


def repair_input(job):
    record = descriptor(job)
    if load(Path(job['root'])/'global-selection.json') != record['global']:
        raise ValueError('The continuation working graph changed before launch')
    basis.verify_foundations(job, record['basis'])
    value = load(record['repair']['path'])
    [evidence] = value['evidence']
    verify_bindings([evidence])
    if (value['job'] not in record['historical_jobs'] or value['global'] != record['global']
            or graph_repair.verify_local(Path(evidence['path']).parent,record['global']) != value['obligations']):
        raise ValueError('Relocated graph return differs from its verified checkpoint')
    return {'job':bind(Path(job['root'])/'job.json'), 'goal':'unconditional',
            'global':record['global'], 'repair':record['repair']}


def saved_input(root, job_ref):
    """Read the exact typed handoff without resuming any old controller."""
    sys.path.insert(0,str(CORE/'workflow/scripts'))
    try:
        from wfcore.engine import Run, replay
        run = Run(root/'protocol', read_only=True)
        replay(run.s,run.model)
    finally:
        sys.path.pop(0)
    data = run.s['data']
    if (run.s['node'] not in {'nl0-local/await-local-revision','nl0-local/revise-graph','continue-graph'}
            or data.get('job') != job_ref or data.get('goal') != 'unconditional'
            or load(root/'global-selection.json') != data.get('global')):
        raise ValueError('Select an exited case at a formal local NL0 graph revision')
    verify_bindings([data['global'],data['repair']])
    return data


def remaining(deadline):
    if deadline is None:
        return None
    end = datetime.fromisoformat(deadline)
    if end.tzinfo is None:
        raise ValueError('Original case deadline is not timezone aware')
    seconds = (end - datetime.now(timezone.utc)).total_seconds()
    if seconds <= 0:
        raise ValueError('Original case deadline is exhausted')
    return seconds


class Checkpoint:
    def __init__(self, root, job):
        self.root, self.job = root, job
        self.job_ref = bind(root/'job.json')
        state = execution_state.inspect(root)
        inspection = state['inspection']
        if (inspection['controller_identity_matches'] or inspection['residual_owned_processes']
                or inspection['process_inspection_error']):
            raise ValueError('Confirm exit of the original controller and owned processes before continuing')
        self.deadline = state['time_budget'].get('deadline_at_utc')
        if (job['time_budget_seconds'] is None) != (self.deadline is None):
            raise ValueError('Original case deadline is unavailable')
        result = root/'case-result.json'
        if result.is_file() and load(result).get('result',{}).get('completion',{}).get('workflow_completed'):
            raise ValueError('The original workflow has already completed')
        self.data = saved_input(root,self.job_ref)
        self.active = basis.problem_inputs(job)
        self.context = bind(self.active/basis.CONTEXT)
        self.foundation = bind(root/'handoffs/foundations.json')
        basis.verify_foundations(job,self.foundation)
        if load(self.context['path'])['approval'] is not None:
            raise ValueError('This continuation entry requires a closed 2basis without residual premises')
        self.jobs = [self.job_ref]
        if job.get('graph_continuation'):
            self.jobs.extend(descriptor(job)['historical_jobs'])
        self.graphs, self.reports = self.lineage()

    def lineage(self):
        graphs = []
        selected = self.data['global']
        for graph, record in frozen_graph.prior_versions(selected,self.root):
            if record['owner'] != frozen_graph.BASIS or record.get('foundation') != self.foundation:
                raise ValueError('NL0 history changed the reviewed foundations')
            graphs.append((selected,graph,record))
            selected = record.get('previous')
        versions = {row['path']:row for row,_,_ in graphs}
        reports, seen = [], set()
        ref = self.data['repair']
        while ref:
            verify_bindings([ref])
            path = Path(ref['path'])
            if path.parent != self.root/'handoffs' or path in seen:
                raise ValueError('Invalid graph return history')
            seen.add(path)
            value = load(path)
            selection = value['global']
            if (versions.get(selection['path']) != selection or value['job'] not in self.jobs
                    or value['baseline'] or value['campaigns'] or len(value['evidence']) != 1):
                raise ValueError('This continuation entry requires a formal local author graph return')
            [evidence] = value['evidence']
            verify_bindings([evidence])
            stage = Path(evidence['path']).parent
            if not stage.is_relative_to(self.root/'nl0') or Path(evidence['path']) != stage/'accepted.json':
                raise ValueError('Graph return evidence is outside the local author stage')
            if graph_repair.verify_local(stage,selection) != value['obligations']:
                raise ValueError('Graph return is inconsistent with the qualified author result')
            reports.append((ref,value))
            ref = value.get('previous_repair')
        if reports[0][1]['global'] != self.data['global']:
            raise ValueError('Formal graph return does not belong to the selected graph')
        graph_repair.consecutive_reports(self.root,self.data['repair'])
        return list(reversed(graphs)), list(reversed(reports))

    def copy_to(self, job):
        from graph_continuation_evidence import Evidence

        root = Path(job['root'])
        evidence = Evidence(self.root, root, job['lean_environment'])
        historical = {}
        for row in self.jobs:
            path = root/'continuation-jobs'/(row['sha256']+'.json')
            raw = Path(row['path']).read_bytes()
            if sha256(raw).hexdigest() != row['sha256']:
                raise ValueError('Original execution identity changed during migration')
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(raw)
            historical[row['path']] = bind(path)
        context = evidence.basis(self.active)
        for reference, graph, record in self.graphs:
            selected = evidence.working(reference,graph,record,context)
        write(root/'global-selection.json',selected)
        for reference,value in self.reports:
            evidence.local_return(reference,value,historical[value['job']['path']])
        original = {'run_id':self.job['run_id'], 'directory':str(self.root),
                    'job_sha256':self.job_ref['sha256'], 'repair_sha256':self.data['repair']['sha256'],
                    'graph_sha256':self.data['global']['sha256'], 'basis_sha256':self.foundation['sha256']}
        carrier = {}
        for label,job_record in (('previous',self.job),('current',job)):
            components = job_record['native_components']
            carrier[label] = {'version':components['version'],'sha256':components['sha256'],
                              'code_mode_host_sha256':components['code_mode_host']['sha256'],
                              'package_manifest_sha256':(components.get('package_manifest') or {}).get('sha256')}
        record = {'version':VERSION,'origin':original,'carrier':carrier,'deadline':self.deadline,
                  'current_run_id':job['run_id'], 'current_directory':str(root),
                  'historical_jobs':list(historical.values()), 'global':selected,
                  'basis':evidence.reference(self.foundation),
                  'repair':evidence.reference(self.data['repair'])}
        write(root/FILENAME,record)
        return bind(root/FILENAME)


def prepare(previous, *, output=None):
    import local_config
    root = Path(previous).expanduser().resolve(strict=True)
    old = load(root/'job.json')
    if old.get('root') != str(root) or old.get('track') != 'full' or basis.mode(old) != 'unconditional':
        raise ValueError('Graph continuation needs an owned unconditional case')
    with jobs.scientific_context(old):
        jobs._validate(old, verify_host=False)
        checkpoint = Checkpoint(root,old)
    local = local_config.current()
    if (local is None or local.get('version') != local_config.rules.VERSION
            or local.get('mode') != 'lean'):
        raise local_config.rules.SetupRequired('Run Yui setup in Lean mode for the new carrier')
    local_config.verify(local)
    with local_config.use(local):
        return jobs.prepare(old['problem'], track=old['track'], profiles=old['profiles'],
                            formalization=basis.mode(old), policy=old['policy'], output=output,
                            time_budget_seconds=remaining(checkpoint.deadline), graph_checkpoint=checkpoint)
