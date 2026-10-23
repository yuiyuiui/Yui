"""Clean text author/review stages sharing the same audited carrier as Lean workers."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
import shutil
import sys
import time

from runtime_config import CORE
sys.path.insert(0, str(CORE / 'translation/scripts'))
import model_pilot as pilot


class ArtifactStage(pilot.Stage):
    def __init__(self, logs, prompt, *, phase, arm='yui', timeout=600, validator=None, budget=None, library=True, inputs=None,
                 kind='json', case_id=None):
        super().__init__(logs, Path(logs) / 'unused-contract.json', phase, timeout, budget=budget)
        if arm not in {'yui', 'direct'}:
            raise ValueError('Unknown instruction arm')
        self.phase, self.arm, self.input_prompt, self.validator = phase, arm, prompt, validator
        self.instruction_arm = arm
        self.mode = phase
        self.rule_texts = {}
        for path in [CORE/'SKILL.md', *(CORE/'references').glob('*.md'), *(CORE/'templates').glob('*.md'),
                     *(CORE/'translation/references').glob('*.md'), *(CORE/'translation/templates').glob('*.md')]:
            self.rule_texts[str(path.resolve())] = path.read_text()
        self.task_inputs = {}
        if inputs:
            manifest = Path(inputs).resolve()
            for row in json.loads(manifest.read_text())['inputs']:
                path = (manifest.parent/row['path']).resolve()
                if not path.is_relative_to(manifest.parent) or row['id'] in self.task_inputs:
                    raise ValueError('Task input escapes its directory or repeats an ID')
                data = path.read_bytes()
                if hashlib.sha256(data).hexdigest() != row['sha256']:
                    raise ValueError('Task input hash differs from the frozen manifest')
                self.task_inputs[row['id']] = data.decode('utf-8')
        self.artifact_kind = kind
        if kind not in {'json', 'nl0'}:
            raise ValueError('Unknown artifact contract')
        if kind == 'nl0':
            if validator is not None or not self.task_inputs:
                raise ValueError('NL0 authoring requires explicit frozen inputs and its built-in validator')
            from artifact_validation import NL0Contract
            self.validator = NL0Contract(self.logs/'case', self.task_inputs, case_id=case_id)
        self.system = ('Complete the supplied mathematical task using only its explicit inputs and tools. '
                       'Submit the requested JSON artifact through submit_artifact. '
                       'Tool feedback is real task feedback; do not invent a successful check.')
        if arm == 'yui':
            self.system += (' This is a Yui workflow stage. Read the relevant declared Yui rules, '
                            'preserve the supplied proof route and exact allowed assumptions, '
                            'and distinguish mathematical review from structural checks.')
        self.tools = [dict(t) for t in pilot.carrier.TOOLS[:2]] if library else []
        if self.task_inputs:
            self.tools.append(pilot.carrier.tool('read_task_input', 'Read an explicitly frozen task document by ID; no other local files are accessible.',
                {'id': {'type':'string'}, 'start':{'type':'integer'}, 'end':{'type':'integer'}}, ['id','start','end']))
        if arm == 'yui':
            self.tools.append(pilot.carrier.tool('read_yui', 'Read declared Yui rules/templates; no tests, historical runs or personal files.',
                {'path': {'type': 'string'}, 'start': {'type': 'integer'}, 'end': {'type': 'integer'}}, ['path', 'start', 'end']))
        self.tools += [pilot.json_tool('check_artifact', 'Check a JSON artifact against the explicit stage contract; this is not automatic mathematical certification.', 'artifact_json'),
                       pilot.json_tool('submit_artifact', 'Submit a JSON artifact after its stage checks.', 'artifact_json'),
                       pilot.json_tool('report_obstacle', 'Stop this stage honestly on a substantive or suspected proof gap, unavailable source, or input conflict. JSON fields: status, location, explanation, basis, partial_progress. Status must be SUBSTANTIVE_GAP, SUSPECTED_GAP, SOURCE_UNAVAILABLE or INPUT_CONFLICT. Difficulty alone is not a mathematical error.', 'obstacle_json')]
        if kind == 'nl0' and library:
            self.tools.append(pilot.carrier.tool('probe_library',
                'Query a proved Mathlib theorem and its exact signature/axioms in the offline sandbox. '
                'Returns located evidence for an M source; the mathematical statement and applicability still require review.',
                {'id':{'type':'string'},'declaration':{'type':'string'},'module':{'type':'string'}},
                ['id','declaration','module']))
        self.tool_names = {t['name'] for t in self.tools}
        snapshot = self.logs/'harness-snapshot'
        snapshot.mkdir()
        source_files = [*CORE.glob('scripts/*.py'), *CORE.glob('translation/scripts/*.py'),
                        CORE/'toolchain/lock.json', CORE/'config.json']
        files = []
        for path in source_files:
            destination = snapshot/path.relative_to(CORE)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
            files.append({'path':str(path.relative_to(CORE)), 'sha256':hashlib.sha256(destination.read_bytes()).hexdigest()})
        for raw, text in self.rule_texts.items():
            destination = snapshot/Path(raw).relative_to(CORE)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(text)
        task_bindings=[]
        for index,(identifier,text) in enumerate(self.task_inputs.items(),1):
            destination=self.logs/'task-inputs'/f'{index:04d}.txt'
            destination.parent.mkdir(exist_ok=True)
            destination.write_text(text)
            task_bindings.append({'id':identifier,'path':str(destination.relative_to(self.logs)),
                                  'sha256':hashlib.sha256(destination.read_bytes()).hexdigest()})
        (self.logs/'execution-manifest.json').write_text(json.dumps({'model':'gpt-6-luna','effort':'high','speed':'standard',
            'arm':arm,'phase':phase,'artifact_contract':kind,'runtime_files':files,'resolved_environment':pilot.load_lock(),'task_documents':
            {k:hashlib.sha256(v.encode()).hexdigest() for k,v in self.task_inputs.items()},
            'frozen_task_files':task_bindings,
            'rule_documents':{str(Path(k).relative_to(CORE)):hashlib.sha256(v.encode()).hexdigest() for k,v in self.rule_texts.items()},
            'scope':'Only declared task documents and, in the Yui arm, frozen Yui rules are model-visible.'},indent=2)+'\n')
        if kind == 'nl0':
            import nl0
            self.input_prompt += ('\nSubmission has exactly {"spec": <NL0 v2 specification>, "graph": <NL0 v2 graph>}. '
                'The controller binds spec.inputs to all frozen task documents, pins to the verified runtime, '
                'and graph.spec_sha256 to the resulting spec. Supply these fields as placeholders if needed. '
                'All mathematical fields remain your responsibility. probe_library returns checked M-source evidence '
                'inside this stage case directory; source.statement and hypotheses still need complete mathematical text. '
                'A successful check_artifact is structural validation, not Audit A acceptance.')
            self.input_prompt += ('\nFrozen structural contract: spec.format_version=2; graph.format_version=2; '
                'spec.case_id=graph.case_id='+json.dumps(case_id)+'. '
                'The controller-bound pins are '+json.dumps({'lean_version':'4.32.2',
                    'mathlib_commit':pilot.load_lock()['mathlib']['rev'],
                    'mathlib_root':pilot.load_lock()['mathlib']['local_path']})+'. '
                'These are provided configuration facts, not guessed mathematical premises. '
                'Spec.inputs, spec.pins and graph.spec_sha256 are rebound deterministically, so their placeholder values '
                'are not an input conflict. All other required schema fields must be supplied normally.')
            self.input_prompt += ('\nExact permitted machine rule names for spec.logic.rules and inference.rules: '+
                json.dumps(sorted(nl0.RULES))+'. Use these identifiers; put mathematical derivations in argument text, '
                'not invented rule enum values. Parameters are a list of {symbol,type}; logic is an object '
                '{classical,rules,calculations,primitives}. Inferences use R001-style IDs; argument paragraphs '
                'use S001-style IDs; propositions use H001/E001/M001/N001 or P. An unknown field/rule is '
                'a format repair, not a mathematical gap. Read references/nl0-format.md for every remaining field.')
        if arm == 'yui':
            self.input_prompt += ('\nYui entry: read_yui(path="SKILL.md", start=1, end=200). '
                'Available frozen rule paths (relative to rigorous-proof): '+
                ', '.join(sorted(str(Path(k).relative_to(CORE)) for k in self.rule_texts))+'. '
                'Every read supports at most 250 lines. Start with the entry and follow its relevant links; do not guess filenames.')
        if self.task_inputs:
            self.input_prompt += '\nFrozen task document IDs: '+', '.join(sorted(self.task_inputs))+'. Use read_task_input to read them.'

    def prompt(self):
        return self.input_prompt

    def dispatch(self, name, args):
        if name in {'search_mathlib', 'read_mathlib'}:
            return super().dispatch(name, args)
        started = time.monotonic()
        try:
            if name not in self.tool_names:
                raise PermissionError('Tool is not allowed')
            if self.accepted is not None:
                raise ValueError('Stage is already complete')
            if name == 'report_obstacle':
                value = json.loads(args['obstacle_json'], object_pairs_hook=pilot.ir.unique)
                if not isinstance(value,dict) or set(value) != {'status','location','explanation','basis','partial_progress'}:
                    raise ValueError('Expected all five obstacle fields')
                if value['status'] not in {'SUBSTANTIVE_GAP','SUSPECTED_GAP','SOURCE_UNAVAILABLE','INPUT_CONFLICT'}:
                    raise ValueError('Unknown obstacle status')
                if any(not isinstance(value[k],str) or not value[k].strip() for k in ['location','explanation','basis','partial_progress']):
                    raise ValueError('Every obstacle field needs a substantive explanation')
                self.accepted = value
                result = {'accepted':True,'stage_complete':True,'mathematical_acceptance':False,'outcome':value['status']}
            elif name == 'probe_library':
                from artifact_validation import signature_probe
                self.lean_calls += 1
                result = signature_probe(self.validator.directory, args['id'], args['declaration'], args['module'], self.lean_calls)
            elif name == 'read_task_input':
                text = self.task_inputs[args['id']]
                start, end = args['start'], args['end']
                if type(start) is not int or type(end) is not int or not 1 <= start <= end or end-start > 249:
                    raise ValueError('Read at most 250 lines using positive line numbers')
                lines = text.splitlines()
                result = {'id':args['id'],'total_lines':len(lines),'text':'\n'.join(f'{i}: {lines[i-1]}' for i in range(start,min(end,len(lines))+1))}
            elif name == 'read_yui':
                relative = Path(args['path'])
                path = (CORE / relative).resolve()
                permitted = [CORE / 'references', CORE / 'templates', CORE / 'translation/references', CORE / 'translation/templates']
                if path != CORE / 'SKILL.md' and not any(path.is_relative_to(p) for p in permitted):
                    raise PermissionError('Only declared instruction/template roots may be read')
                if str(path) not in self.rule_texts:
                    raise PermissionError('Expected an existing Markdown rule')
                start, end = args['start'], args['end']
                if type(start) is not int or type(end) is not int or not 1 <= start <= end or end - start > 249:
                    raise ValueError('Read at most 250 lines using positive line numbers')
                lines = self.rule_texts[str(path)].splitlines()
                result = {'path': str(relative), 'total_lines': len(lines),
                          'text': '\n'.join(f'{i}: {lines[i-1]}' for i in range(start, min(end, len(lines)) + 1))}
            else:
                value = json.loads(args['artifact_json'], object_pairs_hook=pilot.ir.unique)
                if not isinstance(value, dict):
                    raise ValueError('Artifact must be a JSON object')
                checked = self.validator(value) if self.validator else {'structural_acceptance_only': True}
                result = {'accepted': True, 'validation': checked, 'stage_complete': name == 'submit_artifact'}
                if name == 'submit_artifact':
                    self.accepted = value
        except (ValueError, KeyError, TypeError, PermissionError) as e:
            result = {'accepted': False, 'error': str(e), 'feedback_kind': 'candidate_rejected'}
        pilot.carrier.append(self.logs / 'tools.jsonl', {'tool': name, 'arguments': args, 'result': result,
                                                       'wall_seconds': time.monotonic() - started})
        return result
