#!/usr/bin/env python3
"""One frozen cold NL0/Audit A round; never repair authors from audit feedback."""
from __future__ import annotations

import argparse
import collections
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import audit_a_campaign as a
import behavioral_controls
import queue_controller
import execution_state
import acceptance

ROOT = a.ROOT
CASES = {'geometry': 'geometry-product-dimension',
         'lie': 'lie-module-irreducibility', 'wave': 'wave-map-energy'}
PROFILE = {'model': json.loads((a.CORE/'config.json').read_text())['model']['id'], 'effort': 'high', 'speed': 'standard', 'fallback': False,
           'author_output_verbosity':'high','review_output_verbosity':'low'}
NO_OWNER_HELP = {'dispatch_and_observe_only':True,'mathematical_help':False,
    'source_locators':False,'proof_patches':False,'mid_run_input_edits':False,
    'audit_feedback_to_author':False,'automatic_repair_or_resampling':False}
STOP_POLICY = 'One frozen author and first Audit A pipeline per case; report every actual result after the finite campaign. No owner repair.'
AUTHOR = '''Use the frozen Yui rigorous-proof skill to turn the existing proof in
problem.md into a complete canonical NL0. Preserve its target, original
hypotheses and core proof route; supply ordinary rigorous local completion.
Retain every calculation and actual derivation needed for the frozen target
and supplied core proof route. An independent optional comment or corollary
outside that dependency may be omitted; note a material omission in the
existing context note. Never omit a needed proof step as optional. You
may copy its exact proof passages through the declared task-line text binding,
then normalize references and close every declaration and factual dependency.
Register important tools; routine basic library uses may receive verified
Audit A background notes. Use ordinary rigorous elementary compression rather
than rebuilding standard theory or expanding every arithmetic chain.
Read the declared Yui authoring, schema, self-containment and source rules.
Inspect actual library evidence for every source you select. Build the proof
and its exact input/object/application accounting together; perform the author
reverse checks before definitive submission. Source lookups, own drafts and
structural checks are available within this single author attempt. Submit the
actual result only after the same-author closing packet inspection and its
located notes. These notes are not an independent review and do not receive
Audit A feedback. Submit the
actual complete artifact, not a plan or a report that routine drafting is hard.
You receive no old NL0, prior audit or case-specific repair hints. A separate
fresh Audit A follows your definitive submission; its feedback will not be
returned to you in this round. Stop before any target Lean translation.
'''


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def runtime_hashes():
    paths = {a.CORE/'SKILL.md', a.CORE/'config.json', a.CORE/'toolchain/lock.json'}
    for base, pattern in [(a.CORE/'scripts', '*.py'),
                          (a.CORE/'translation/scripts', '*.py'),
                          (a.CORE/'references', '*.md'), (a.CORE/'templates', '*.md'),
                          (a.CORE/'translation/references', '*.md'),
                          (a.CORE/'translation/templates', '*.md'),
                          (a.CORE/'library', '*.json'), (ROOT/'test/support', '*.py')]:
        paths.update(base.rglob(pattern))
    fixture = a.CORE/'tests/fixtures/closed-addition'
    paths.update(p for p in fixture.iterdir() if p.is_file())
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths)}


def verify_frozen(manifest):
    if manifest.get('profile')!=PROFILE or manifest.get('owner_intervention_policy')!=NO_OWNER_HELP or manifest.get('stop_policy')!=STOP_POLICY:
        raise ValueError('Frozen model/profile or owner intervention/stop policy differs')
    if manifest.get('acceptance_contract')!=acceptance.current().metadata():
        raise ValueError('Shared Audit A acceptance authority changed after freeze')
    if set(runtime_hashes())!=set(manifest['runtime_source_hashes']):
        raise ValueError('Round runtime file inventory changed after freeze')
    for relative, digest in manifest['runtime_source_hashes'].items():
        if sha(ROOT/relative) != digest:
            raise ValueError('Round runtime changed after freeze: '+relative)
        if manifest.get('runtime_snapshot') and sha(Path(manifest['runtime_snapshot'])/relative)!=digest:
            raise ValueError('Round runtime snapshot changed: '+relative)
    for case in manifest['cases']:
        if sha(case['original_input']) != case['sha256']:
            raise ValueError('Original problem changed after freeze: '+case['case'])
        rows = read(Path(case['author'])/'inputs.json')['inputs']
        if len(rows) != 1 or rows[0]['id'] != 'problem.md':
            raise ValueError('A cold author must have only its own problem.md')
        if sha(Path(case['author'])/rows[0]['path']) != case['sha256']:
            raise ValueError('Staged author problem differs from frozen original')
        if sha(Path(case['author'])/'prompt.txt')!=manifest['author_prompt_sha256']:
            raise ValueError('Frozen author prompt changed; no owner hints or patches are permitted')


def prepare(out, index):
    out = Path(out).resolve()
    if out.parent != (ROOT/'test/results').resolve() or out.exists():
        raise ValueError('Use a new immediate child of test/results')
    if type(index) is not int or index < 1:
        raise ValueError('Positive round index required')
    out.mkdir(parents=True); (out/'pending').mkdir()
    stamp = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y%m%d-%H%M%S')
    cases = []
    controls = ROOT/'test/results'/f'first-pass-controls-r{index}-{stamp}'
    for identity, case_id in CASES.items():
        problem = ROOT/'test'/case_id/'problem.md'
        author = ROOT/'test/results'/f'first-pass-r{index}-{identity}-nl0-{stamp}'
        audit = ROOT/'test/results'/f'first-pass-r{index}-{identity}-audit-a-{stamp}'
        author.mkdir()
        shutil.copyfile(problem, author/'problem.md')
        a.write(author/'inputs.json', {'inputs': [
            {'id': 'problem.md', 'path': 'problem.md', 'sha256': sha(problem)}]})
        (author/'prompt.txt').write_text(AUTHOR)
        job = {'id': identity, 'case': case_id, 'kind': 'nl0', 'run': author.name,
               'audit': audit.name, 'audit_controls': controls.name,
               'stop_after': 'audit_a', 'max_concurrency': 'auto'}
        queue_controller.validate_job(job)
        a.write(out/'pending'/f'{identity}.json', job)
        cases.append({'id': identity, 'case': case_id, 'original_input': str(problem),
                      'sha256': sha(problem), 'author': str(author), 'audit': str(audit)})
    git = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True,
                         capture_output=True, check=True).stdout.strip()
    hashes=runtime_hashes();snapshot=out/'runtime-snapshot'
    for relative in hashes:
        destination=snapshot/relative;destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/relative,destination)
    manifest = {'schema': 'yui-cold-first-pass-round-1', 'round': index,
                'created_at_utc': execution_state.now(), 'profile': PROFILE,
                'case_concurrency': 3, 'within_case_model_cap': 1,
                'budgets': {'author_seconds': 1800, 'each_audit_stage_seconds': 1200,
                            'each_control_seconds': 600},
                'budget_scope': 'Per-stage limits, not an end-to-end campaign deadline.',
                'shared_calibration': str(controls), 'cases': cases,
                'author_prompt': AUTHOR, 'author_prompt_sha256': hashlib.sha256(AUTHOR.encode()).hexdigest(),
                'git_commit': git, 'runtime_source_hashes': hashes,'runtime_snapshot':str(snapshot),
                'acceptance_contract':acceptance.current().metadata(),
                'owner_intervention_policy':NO_OWNER_HELP,'stop_policy':STOP_POLICY,
                'previous_candidate_or_audit_reuse': False,
                'scope': 'Cold author inputs; one definitive source and first actual Audit A per case. No audit-driven repair, Lean translation or proof workers.',
                'interpretation': 'Development/regression cases, not held-out generalization or speed evidence.'}
    a.write(out/'round-manifest.json', manifest)
    verify_frozen(manifest)
    return manifest


def collect(out, status):
    manifest = read(out/'round-manifest.json')
    verify_frozen(manifest)
    cases, stages = {}, {}
    for row in manifest['cases']:
        source = Path(row['author'])/'stage/case'
        result = out/'results'/f'{row["id"]}.json'
        outcome = read(result)['result'] if result.is_file() else {'status': 'NOT_STARTED'}
        files = [Path(row['author'])/'stage/result.json',
                 *Path(row['audit']).glob('*/stage/result.json')]
        actual = {}
        authority_checks=[]
        for file in files:
            if file.is_file():
                stages[file.resolve()] = read(file)
                stage_manifest=file.parent/'execution-manifest.json'
                authority_checks.append(stage_manifest.is_file() and
                    read(stage_manifest).get('acceptance_contract')==manifest['acceptance_contract'])
        for file in Path(row['audit']).glob('*/stage/accepted.json'):
            review = read(file)
            actual[file.parent.parent.name] = {'artifact': str(file),
                                                'background_notes':review.get('background_notes', []),
                                                'findings': review.get('findings', [])}
        accepted = outcome.get('status') == 'DRAFT-AUDIT-PASSED'
        gate_error = None
        if accepted and (not authority_checks or not all(authority_checks)):
            accepted=False;gate_error='Author and actual Audit A do not bind the same frozen acceptance authority'
        if accepted:
            try:
                inspection = a.nl0.validate(source/'nl0.json', source/'spec.json', source/'audit-a.json')[0]
                accepted = bool(inspection['current_standard_receipt_valid'] and inspection['audit_record_complete'])
            except (ValueError, OSError) as error:
                accepted = False; gate_error = str(error)
        view = {'status':'SOURCE_NOT_AVAILABLE',
                'scope':'A readable view is not definitive author submission or mathematical acceptance.'}
        if (source/'nl0.json').is_file() and (source/'spec.json').is_file():
            try:
                rendered = subprocess.run([sys.executable, '-B', str(a.CORE/'scripts/nl0.py'), 'render',
                            str(source/'nl0.json'), '--spec', str(source/'spec.json'),
                            '--out', str(Path(row['author'])/'readable')],
                           text=True, capture_output=True, check=False)
                view.update(status='RENDERED' if rendered.returncode==0 else 'RENDER_FAILED',
                            exit_code=rendered.returncode, stdout=rendered.stdout, stderr=rendered.stderr)
            except OSError as error:
                view.update(status='RENDER_EXECUTION_ERROR',error=type(error).__name__+': '+str(error))
            a.write(Path(row['author'])/'readable-render.json',view)
        cases[row['id']] = {'status': outcome, 'first_audit_passed': accepted,
                            'recorded_background_note_count':sum(len(x['background_notes']) for x in actual.values()),
                            'author_artifact':outcome.get('author_artifact'),
                            'gate_error': gate_error,
                            'readable_view':view,
                            'acceptance_authority_verified':all(authority_checks) if authority_checks else None,
                            'author': row['author'], 'source': str(source),
                            'audit': row['audit'], 'actual_reviews': actual}
    for file in Path(manifest['shared_calibration']).rglob('stage/result.json'):
        stages[file.resolve()] = read(file)
    totals = collections.Counter(); incomplete = []
    for file, stage in stages.items():
        usage = stage.get('usage') or {}
        totals.update(usage.get('observed_usage') or {})
        if not usage.get('complete'): incomplete.append(str(file))
    controls_file = Path(manifest['shared_calibration'])/'behavioral-summary.json'
    controls = read(controls_file)['status'] if controls_file.is_file() else 'NOT_COMPLETED'
    achieved = bool(controls == 'BEHAVIORAL-CONTROLS-PASSED' and
                    len(cases) == 3 and all(row['first_audit_passed'] for row in cases.values()))
    timing_qualified=bool(stages) and all(stage.get('measurement_valid') is True for stage in stages.values())
    report = {'updated_at_utc': execution_state.now(), 'round': manifest['round'],
              'status': 'GOAL_ROUND_PASSED' if achieved else status,
              'goal_achieved': achieved, 'controls': controls, 'cases': cases,
              'acceptance_target_satisfied':achieved,
              'experiment_state':'FINISHED' if len(cases)==3 and all(x['status'].get('status')!='NOT_STARTED' for x in cases.values()) else 'INCOMPLETE',
              'owner_intervention_policy':manifest.get('owner_intervention_policy'),
              'next_action':'Report this frozen attempt; no automatic author repair or repeated review.',
              'benchmark_timing_qualified':timing_qualified,
              'qualification_scope':'First-A mathematical acceptance and execution/timing eligibility are separate; faults and incomplete usage are never erased.',
              'runtime_unchanged': True, 'cold_author_inputs': True,
              'accounting': {'finished_stage_records': len(stages),
                             'observed_tokens': dict(totals), 'usage_complete': not incomplete,
                             'incomplete_stage_results': incomplete,
                             'definition': 'Cached input/reasoning output are subsets. Missing usage is unknown; developer-chat usage is outside this carrier.'},
              'stage_results': [str(path) for path in sorted(stages)],
              'interpretation': manifest['interpretation']}
    a.write(out/'round-result.json', report)
    return report


def run(out):
    out = Path(out).resolve(); manifest = read(out/'round-manifest.json')
    verify_frozen(manifest)
    prepare_module = importlib.util.spec_from_file_location('neutral_controls', a.CORE/'scripts/prepare-review-cases.py')
    module = importlib.util.module_from_spec(prepare_module); prepare_module.loader.exec_module(module)
    controls = Path(manifest['shared_calibration']); module.prepare(controls)
    recorder = execution_state.Recorder(out/'calibration-execution', 'neutral-audit-calibration',
                                       a.concurrency.resolve(1), phase='review-calibration')
    budgets = a.concurrency.CaseBudgets(1, execution=recorder)
    status = 'ROUND_INCOMPLETE'
    try:
        with execution_state.activate(recorder), recorder.signals():
            actual = behavioral_controls.run(controls, 600, budget=budgets.serial)
        recorder.close(actual['status'])
        if actual['status'] != 'BEHAVIORAL-CONTROLS-PASSED':
            status = 'CALIBRATION_FAILED'; return collect(out, status)
        verify_frozen(manifest)
        print('Neutral controls passed; launching three cold author/Audit A cases.', flush=True)
        queue_controller.serve(out, case_concurrency=3)
        status = 'ROUND_DID_NOT_PASS'
        return collect(out, status)
    except BaseException as error:
        if not recorder.done.is_set(): recorder.close('CONTROLLER_STOPPED', error=str(error))
        a.write(out/'controller-error.json', {'at_utc': execution_state.now(),
                                             'error': type(error).__name__+': '+str(error)})
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare_ = commands.add_parser('prepare'); prepare_.add_argument('--out', required=True); prepare_.add_argument('--index', required=True, type=int)
    run_ = commands.add_parser('run'); run_.add_argument('--out', required=True)
    args = parser.parse_args()
    result = prepare(args.out, args.index) if args.command == 'prepare' else run(args.out)
    print(json.dumps(result, indent=2))
