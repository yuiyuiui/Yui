"""Copy the file closure consumed at an NL0 graph-return checkpoint."""
import json
from pathlib import Path

from controller_common import bind, manifest, verify_bindings, write
from staging_storage import copy_input


EVIDENCE_ROOTS = {'inputs','active-inputs','2basis','imported-lean','lean-libraries',
                  'basis-selection.json','global-graphs','handoffs','nl0'}


class Evidence:
    def __init__(self, source, root, environment):
        self.source, self.root = source, root
        self.toolchain = tuple(Path(environment[key]['local_path']) for key in ('lean','mathlib'))
        self.copies = {}

    def destination(self, path):
        path = Path(path)
        relative = path.relative_to(self.source)
        if (relative.parts[0] not in EVIDENCE_ROOTS or path.resolve(strict=True) != path
                or not path.is_file()):
            raise ValueError('Invalid owned continuation evidence: '+str(path))
        return self.root/relative

    def remember(self, old, new):
        self.copies[old['path']] = (old, new)
        return new

    def write(self, old, value):
        verify_bindings([old])
        path = self.destination(old['path'])
        write(path, value)
        return self.remember(old, bind(path))

    def copy(self, old):
        return self.reference(old, transform=False)

    def reference(self, old, *, transform=True):
        if old['path'] in self.copies:
            before, after = self.copies[old['path']]
            if old != before:
                raise ValueError('Conflicting evidence bindings: '+old['path'])
            return after
        path = Path(old['path'])
        verify_bindings([old])
        if not path.is_relative_to(self.source):
            # Native acceptance also names files in the unchanged, pinned Lean pair.
            if any(path.is_relative_to(root) for root in self.toolchain):
                return old
            raise ValueError('Continuation evidence belongs to another run: '+str(path))
        if transform and path.relative_to(self.source).parts[0] == '2basis':
            value = self.basis_record(path)
            if value is not None:
                return self.write(old,value)
        target = self.destination(path)
        if not target.exists():
            target.parent.mkdir(parents=True,exist_ok=True)
            copy_input(path,target)
        after = bind(target)
        if after['sha256'] != old['sha256']:
            raise ValueError('Evidence changed while copying: '+str(path))
        return self.remember(old,after)

    @staticmethod
    def json(path):
        return json.loads(path.read_bytes())

    def bindings(self, value):
        if isinstance(value, list):
            return [self.bindings(row) for row in value]
        if isinstance(value, dict):
            if set(value) == {'path','sha256'} and Path(value['path']).is_absolute():
                return self.reference(value)
            return {key:self.bindings(item) for key,item in value.items()}
        return value

    def documents(self, directory, contextual=None):
        for row in self.json(directory/'inputs.json')['inputs']:
            path = directory/row['path']
            self.document(path, row['sha256'], contextual)

    def document(self, path, digest, contextual):
        ref = {'path':str(path),'sha256':digest}
        if contextual and path.name == 'proof-context.json':
            if digest != contextual[0]['sha256']:
                raise ValueError('Working graph refers to different foundation evidence')
            verify_bindings([ref])
            target = self.destination(path)
            if target != Path(contextual[1]['path']):
                target.parent.mkdir(parents=True,exist_ok=True)
                copy_input(Path(contextual[1]['path']),target)
            return self.remember(ref,bind(target))
        return self.copy(ref)

    def stage_result(self, path):
        old = bind(path)
        if old['path'] in self.copies:
            return self.reference(old)
        value = self.json(path)
        target_stage = self.destination(path).parent
        # The role identity and exposure still match the original execution manifest.
        if value.get('error_pauses'):
            value['error_pauses'] = [self.copy(row) for row in value['error_pauses']]
        if value.get('temporary_workspace_removed') is False:
            from run_resources import RELEASE_AUTHORIZATIONS

            retention = value['workspace_retention']
            owner = Path(retention['logs'])/'result.json'
            target_owner = self.destination(owner).parent
            release = owner.parent/'resources/release.json'
            if not release.is_file():
                raise ValueError('Retained stage workspace needs an authorized release before continuation')
            receipt = self.json(release)
            if (receipt['workspace_retention'] != retention or receipt['cleanup_confirmed'] is not True
                    or receipt['authorization'] not in RELEASE_AUTHORIZATIONS
                    or receipt['result_sha256'] != bind(owner)['sha256']
                    or self.json(owner)['workspace_retention'] != retention):
                raise ValueError('Changed stage workspace release evidence: '+str(release))
            if owner != path:
                self.stage_result(owner)
            value['workspace_retention']['logs'] = str(target_owner)
            value['stage_log_path'] = str(target_stage)
            after = self.write(old,value)
            if owner == path:
                receipt['workspace_retention'] = value['workspace_retention']
                receipt['result_sha256'] = after['sha256']
                self.write(bind(release),receipt)
            return after
        return self.write(old,value) if value.get('error_pauses') else self.copy(old)

    def basis_record(self, path):
        if path.name == 'assessment.json' and path.parent.name == 'review':
            value = self.json(path)
            self.documents(path.parent/'inputs')
            stage = path.parent/'stage'
            for doc in self.json(stage/'execution-manifest.json')['frozen_task_files']:
                self.copy({'path':str(stage/doc['path']), 'sha256':doc['sha256']})
            self.stage_result(stage/'result.json')
            author = path.parents[1]/'stage/result.json'
            if author.is_file():
                self.stage_result(author)
            return self.bindings(value)
        if (path.name == 'report.json' and path.parent.name == 'review'
                or path.name == 'check.json' and path.parent.name == 'native'):
            return self.bindings(self.json(path))
        return None

    def basis(self, active):
        import basis

        old = bind(active/basis.CONTEXT)
        new = self.write(old,self.bindings(self.json(active/basis.CONTEXT)))
        contextual = (old,new)
        self.documents(active,contextual)
        local = self.destination(active/basis.CONTEXT).parent
        manifest(local)
        self.write(bind(self.source/'basis-selection.json'),
                   {'context':new,'inputs':bind(local/'inputs.json')})
        foundation = self.source/'handoffs/foundations.json'
        self.write(bind(foundation), self.bindings(self.json(foundation)))
        return contextual

    def working(self, reference, checked, record, contextual):
        spec, graph = checked['spec'], checked['graph']
        directory = Path(record['spec']['path']).parent
        self.working_sources(directory,graph,contextual)
        for row in spec['inputs']:
            row['sha256'] = self.document(directory/row['path'],row['sha256'],contextual)['sha256']
        spec_ref = self.write(record['spec'],spec)
        graph['spec_sha256'] = spec_ref['sha256']
        graph_ref = self.write(record['graph'],graph)
        if 'outline' in record:
            outline = self.json(Path(record['outline']['path']))
            outline.update(spec_sha256=spec_ref['sha256'],graph_sha256=graph_ref['sha256'])
            self.write(record['outline'],outline)
        return self.write(reference,self.bindings(record))

    def working_sources(self, directory, graph, contextual):
        from frozen_graph import evidence

        target = self.root/directory.relative_to(self.source)
        evidence(directory,graph,target)
        context = self.json(Path(contextual[1]['path']))
        for proposition in graph['propositions']:
            if proposition['kind'] != 'mathlib':
                continue
            for row in proposition['source']['evidence']:
                path = directory/row['path']
                if path.suffix != '.json':
                    continue
                probe = self.json(path)
                if isinstance(probe,dict) and probe.get('probe_version')==1 and 'inheritance' in probe:
                    probe['inheritance']['context'] = context
                    reference = {'path':str(path),'sha256':row['sha256']}
                    row['sha256'] = self.write(reference,probe)['sha256']

    def local_return(self, reference, record, job):
        from frozen_graph import ASSIGNED, read_working

        [submission] = record['evidence']
        old_stage = Path(submission['path']).parent
        accepted = self.json(Path(submission['path']))
        self.write(bind(old_stage.parent/'inputs'/ASSIGNED),read_working(self.reference(record['global'])))
        for finding in accepted.get('batch',{}).get('findings',[]):
            for span in finding.get('source_spans',[]):
                path = old_stage.parent/'inputs'/span['from_task']
                self.copy(bind(path))
        from graph_repair import FEEDBACK
        feedback = old_stage.parent/'inputs'/FEEDBACK
        if feedback.is_file():
            self.copy(bind(feedback))
        for name in ('execution-manifest.json','exposure-audit.json','tools.jsonl'):
            self.copy(bind(old_stage/name))
        self.stage_result(old_stage/'result.json')
        self.write(submission,self.bindings(accepted))
        self.write(reference,self.bindings({key:value for key,value in record.items() if key!='job'}) | {'job':job})
