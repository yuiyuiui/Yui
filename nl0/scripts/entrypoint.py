"""Conversational-skill execution adapter; no extra intent-classification model."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys

from controller_common import CORE, write
from runtime_config import validate_profile, auth_home
import jobs


def parsers(commands):
    for name in ('prepare','run'):
        p=commands.add_parser(name,help='Organize arbitrary supplied proof(s); outputs stay beside each problem')
        p.add_argument('problems',nargs='+',type=Path)
        p.add_argument('--track',choices=sorted(jobs.TRACKS),required=True)
        p.add_argument('--formalization',choices=['conditional','unconditional'],default='conditional',
                       help='Lean goal; unconditional adds 2basis and final b2lean closure to track=full')
        p.add_argument('--material',action='append',type=Path,default=[])
        p.add_argument('--lean-library',action='append',type=Path,default=[],
                       help='Configured library name or explicit specification for this selected environment')
        p.add_argument('--lean-root',type=Path,help='Explicit local Lean installation for this run')
        p.add_argument('--mathlib-root',type=Path,help='Explicit compatible Mathlib checkout for this run')
        p.add_argument('--lean-version',help='Select one installed exact Lean release')
        p.add_argument('--mathlib-version',help='Select an installed Mathlib release tag or full commit')
        p.add_argument('--source',type=Path);p.add_argument('--audit',type=Path);p.add_argument('--output',type=Path)
        p.add_argument('--target',help='Complete requested statement or semicolon-separated theorem labels')
        p.add_argument('--target-file',type=Path,help='Source-bound, reviewed target-selection JSON')
        p.add_argument('--max-concurrency',metavar='auto|N',default='auto',
                       help='Per-case local review/proof limit; default auto uses the current R/T node count')
        p.add_argument('--case-concurrency',type=int)
        p.add_argument('--stop-after',choices=['2basis','nl0','nl02lean'],help='Hold a live case at the verified stage boundary')
        p.add_argument('--policy',choices=['normal','first-pass'],default='normal')
        p.add_argument('--time-budget-seconds',type=int)
        p.add_argument('--use-config-profiles',action='store_true',help='Explicitly select the installed defaults for missing profiles')
        for phase in ('nl0','lean'):
            p.add_argument('--'+phase+'-model');p.add_argument('--'+phase+'-effort');p.add_argument('--'+phase+'-speed')
        p.add_argument('--detach',action='store_true',help='Run independent owned case processes and return their locations')
    p=commands.add_parser('lean-environments',help='Discover checked local pairs or explicitly install selected versions')
    p.add_argument('--install',action='store_true',help='Download the exact requested versions to a new shared directory')
    p.add_argument('--lean-version');p.add_argument('--mathlib-version')
    p.add_argument('--directory',type=Path,help='New shared directory for explicit installation')
    p=commands.add_parser('execute',help='Execute already prepared, unchanged run jobs')
    p.add_argument('runs',nargs='+',type=Path);p.add_argument('--case-concurrency',type=int);p.add_argument('--detach',action='store_true')
    p=commands.add_parser('targets',help='Inspect theorem candidates without starting mathematical work')
    p.add_argument('problem',type=Path)
    p=commands.add_parser('resume',help='Continue a supported, explicitly verified operational checkpoint')
    p.add_argument('runs',nargs='+',type=Path);p.add_argument('--case-concurrency',type=int)
    p.add_argument('--detach',action='store_true');p.add_argument('--prepare-only',action='store_true')
    repairs=p.add_mutually_exclusive_group()
    repairs.add_argument('--repair-basis',action='store_true',
        help='Revise a verified downstream basis defect in a new run, under the original budget')
    repairs.add_argument('--repair-evidence',action='store_true',
        help='Resume a verified stopped evidence-index fault with complete retained reviews; no new review sampling')
    repairs.add_argument('--repair-local-tool',action='store_true',
        help='Continue a verified inherited probe-directory collision from its saved pre-draft author-repair boundary')
    repairs.add_argument('--repair-native-cleanup',action='store_true',
        help='Continue an exited frozen proof queue stopped only by native-process cleanup faults')
    repairs.add_argument('--repair-proof-io',action='store_true',
        help='Continue an exited frozen proof queue after recorded ENOSPC; retain own drafts and recheck bodies')
    repairs.add_argument('--repair-basis-closure',action='store_true',
        help='After cancellation and verified exit, repeat only failed final basis closure from accepted artifacts')
    for name in ('status','observe','cancel','cleanup'):
        p=commands.add_parser(name,help='Inspect, cancel or clean explicitly selected run(s) without a model')
        p.add_argument('runs',nargs='+',type=Path)
        if name=='cancel':p.add_argument('--task',help='One known proof task; requires a single run')
        if name=='cleanup':p.add_argument('--apply',action='store_true');p.add_argument('--grace-seconds',type=float,default=10)
    checkpoint=commands.add_parser('resume-checkpoint',help='Continue an explicitly stopped stage under its existing owner')
    checkpoint.add_argument('run',type=Path);checkpoint.add_argument('--id',required=True)
    material=commands.add_parser('supply-material',help='Bind a received source file to its exact waiting incident')
    material.add_argument('run',type=Path);material.add_argument('--incident',required=True);material.add_argument('--file',type=Path)
    for name in ('errors','resume-error'):
        p=commands.add_parser(name,help='Inspect or explicitly resume one retained live error checkpoint; no model call')
        p.add_argument('run',type=Path)
        if name=='resume-error':p.add_argument('--incident',required=True)
    p=commands.add_parser('final-decision',help='Apply an explicit user choice at a retained B-final nonpass')
    p.add_argument('run',type=Path);p.add_argument('--incident',required=True)
    p.add_argument('--action',choices=['deliver-actual','recheck','reset-translation'],required=True)
    p=commands.add_parser('basis-decision',help='Choose an exact retained class-4 basis action')
    p.add_argument('run',type=Path);p.add_argument('--incident',required=True)
    p.add_argument('--action',choices=['stop','continue','accept-conditional'],required=True)


def profiles(args):
    config=json.loads((CORE/'config.json').read_text());selected={}
    import local_config
    local=local_config.current()
    required={'nl0','lean'} if args.track=='full' else {'nl0'} if args.track=='nl0' else {'lean'}
    for phase in required:
        values=[getattr(args,phase+'_'+field) for field in ('model','effort','speed')]
        default=(local['profiles'][phase] if local is not None else
                 config['model'] if phase=='nl0' else config['phase_models']['nl0_to_lean'])
        if args.use_config_profiles or local is not None:
            values=[value if value is not None else default[key] for value,key in zip(values,('id','reasoning_effort','speed'))]
        if any(value is None for value in values):
            raise ValueError('Ask once for the missing '+phase+' model, reasoning effort and speed, or explicitly choose --use-config-profiles')
        selected[phase]=validate_profile(dict(zip(('id','reasoning_effort','speed'),values),automatic_fallback=False))
    for phase in {'nl0','lean'}-required:selected[phase]=dict(next(iter(selected.values())))
    return selected


def proof_workers(args):
    """Keep auto deferred until the current phase's R/T nodes are known."""
    requested='auto' if args.max_concurrency is None else args.max_concurrency
    import concurrency
    configuration=concurrency.resolve(requested)
    return 'auto' if requested=='auto' else configuration['effective']


def preflight_profiles(job):
    """Use the carrier's actual local model metadata; never guess availability."""
    path=auth_home()/'models_cache.json'
    if not path.is_file():raise ValueError('No local backend model metadata; refresh authenticated Codex models first')
    available={row['slug']:row for row in json.loads(path.read_text()).get('models',[])}
    phases={'nl0','lean'} if job['track']=='full' else {'nl0'} if job['track']=='nl0' else {'lean'}
    for phase in phases:
        p=job['profiles'][phase];model=available.get(p['id'])
        if model is None:raise ValueError('Selected model is unavailable in backend metadata: '+p['id'])
        supported={row['effort'] for row in model.get('supported_reasoning_levels',[])}
        if p['reasoning_effort'] not in supported:
            raise ValueError('Backend does not advertise '+p['id']+'/'+p['reasoning_effort']+'; supported: '+', '.join(sorted(supported)))


def launch(prepared, *, detached=False, case_concurrency=None):
    for job in prepared:jobs.validate(job);preflight_profiles(job)
    from runtime_config import verify, use_environment
    for job in prepared:
        selected = job['lean_environment']
        with use_environment(selected):verify()
    if detached:
        from owner_observation import handoff
        observation=handoff([job['root'] for job in prepared])
        root=Path(prepared[0]['root']);(root/'logs').mkdir(exist_ok=True)
        import runtime_snapshot
        command=[sys.executable,'-u','-B',str(runtime_snapshot.root_for(prepared[0])/'nl0/scripts/queue_controller.py')]
        for job in prepared:command.extend(['--job',str(Path(job['root'])/'job.json')])
        if case_concurrency is not None:command.extend(['--case-concurrency',str(case_concurrency)])
        with (root/'logs/batch-controller.log').open('w') as log:
            process=subprocess.Popen(command,stdout=log,stderr=log,start_new_session=True,
                env=runtime_snapshot.environment(prepared[0]))
        from execution_state import identity
        who=identity(process.pid)
        if who is None and process.poll() is None:raise RuntimeError('Cannot verify detached controller identity')
        for job in prepared:write(Path(job['root'])/'launch.json',{'controller':who,'runs':[p['root'] for p in prepared],
            'owner_observation':observation})
        return {'status':'DISPATCHED','controller':who,'runs':[p['root'] for p in prepared],
                'owner_observation':observation,
                'scope':'Actual mathematical acceptance is pending; use status/cancel on these run paths'}
    import queue_controller
    return {'status':'EXECUTORS_FINISHED','outcomes':queue_controller.serve(prepared,case_concurrency=case_concurrency)}


def dispatch(args):
    if args.command=='lean-environments':
        import lean_environment
        if args.install:
            if not args.mathlib_version:
                raise ValueError('Installation needs an exact --mathlib-version')
            selected=lean_environment.install(lean_version=args.lean_version,
                mathlib_ref=args.mathlib_version,directory=args.directory)
            return {'status':'LEAN_ENVIRONMENT_INSTALLED','environment':selected}
        if args.directory is not None:
            raise ValueError('--directory is only used for explicit installation')
        if args.lean_version or args.mathlib_version:
            return {'status':'LEAN_ENVIRONMENT_SELECTED','environment':lean_environment.resolve(
                lean_version=args.lean_version,mathlib_ref=args.mathlib_version)}
        choices,failures=lean_environment.discover()
        return {'status':'LEAN_ENVIRONMENTS_DISCOVERED','candidates':choices,'discovery_errors':failures,
                'selection_required':len(choices)!=1}
    if args.command in {'final-decision','basis-decision'}:
        import fault_control
        return fault_control.final_decision(args.run,args.incident,args.action)
    if args.command in {'errors','resume-error'}:
        import fault_control
        if args.command=='errors':return {'status':'ERROR_CHECKPOINTS','errors':fault_control.pending(args.run)}
        return fault_control.resume(args.run,args.incident)
    if args.command=='observe':
        from owner_observation import snapshot
        return snapshot(args.runs)
    if args.command=='resume-checkpoint':
        import workflow_checkpoint
        return workflow_checkpoint.resume(args.run,args.id)
    if args.command=='supply-material':
        from material_exchange import supply
        return supply(args.run,args.incident,args.file)
    if args.command=='targets':
        import target_selection
        return target_selection.inspect(args.problem)
    if args.command=='resume':
        import interrupted
        import basis_defect
        import native_cleanup_recovery
        import proof_io_recovery
        import basis_closure_recovery
        prepared=[basis_defect.prepare(path) if getattr(args,'repair_basis',False) else
              basis_closure_recovery.prepare(path) if getattr(args,'repair_basis_closure',False) else
              native_cleanup_recovery.prepare(path) if getattr(args,'repair_native_cleanup',False) else
              proof_io_recovery.prepare(path) if getattr(args,'repair_proof_io',False) else
              interrupted.prepare(path,repair_evidence=True) if args.repair_evidence else
              interrupted.prepare(path,repair_local_tool=True) if args.repair_local_tool else
              interrupted.prepare(path) for path in args.runs]
        if args.prepare_only:return {'status':'PREPARED_NOT_STARTED','runs':[job['root'] for job in prepared]}
        return launch(prepared,detached=args.detach,case_concurrency=args.case_concurrency)
    if args.command in {'prepare','run'}:
        from basis import validate_mode
        selected_mode=getattr(args,'formalization','conditional')
        validate_mode(selected_mode,args.track)
        if len(args.problems)>1 and any((args.material,args.source,args.audit,args.output,getattr(args,'lean_library',[]))):
            raise ValueError('For per-case materials/source/output, prepare separate explicit jobs and execute them together')
        import target_selection
        chosen=profiles(args);workers=proof_workers(args);prepared=[]
        import lean_environment
        explicit = any(getattr(args,key,None) is not None for key in (
            'lean_root','mathlib_root','lean_version','mathlib_version'))
        selections={}
        if args.track in {'nl0','full'}:
            for problem in args.problems:
                selection=target_selection.resolve(problem,requested=getattr(args,'target',None),selection_file=getattr(args,'target_file',None))
                if selection['status']!='SELECTED':return selection
                selections[str(problem)]=selection
        selected_environment = (lean_environment.resolve(lean_root=getattr(args,'lean_root',None),
            mathlib_root=getattr(args,'mathlib_root',None),lean_version=getattr(args,'lean_version',None),
            mathlib_ref=getattr(args,'mathlib_version',None)) if explicit else
            __import__('runtime_config').require_environment() if args.track!='nl0' else None)
        import local_config
        local=local_config.current()
        libraries=[]
        for specification in getattr(args,'lean_library',[]):
            configured=[row for row in local['libraries'] if row['name']==str(specification)] if local and 'libraries' in local else []
            libraries.append(Path(configured[0]['specification']['path']) if configured else specification)
        for problem in args.problems:
            prepared.append(jobs.prepare(problem,track=args.track,profiles=chosen,max_concurrency=workers,
                materials=args.material,source=args.source,audit=args.audit,output=args.output,
                policy=args.policy,time_budget_seconds=args.time_budget_seconds,
                target=selections.get(str(problem)),formalization=selected_mode,stop_after=getattr(args,'stop_after',None),
                lean_environment=selected_environment,lean_libraries=libraries))
        summary={'status':'PREPARED_NOT_STARTED','runs':[p['root'] for p in prepared],
                 'profiles':chosen,'proof_concurrency':(__import__('concurrency').resolve(workers)
                    if args.track in {'full','translate'} else None),
                 'concurrent_cases':args.case_concurrency or len(prepared)}
        summary['formalization']=selected_mode
        summary['lean_environment']=selected_environment
        summary['source_policy_notice']='Unavailable primary sources can produce only an explicitly conditional result with warn.json/warn.md, never an unqualified PASS.'
        summary['audit_r_concurrency']=__import__('concurrency').resolve(workers) if args.track in {'nl0','full'} else None
        if args.command=='prepare':return summary
        launched=launch(prepared,detached=args.detach,case_concurrency=args.case_concurrency)
        launched['source_policy_notice']=summary['source_policy_notice']
        return launched
    if args.command=='execute':
        prepared=[jobs.validate(json.loads((p/'job.json').read_text())) for p in args.runs]
        return launch(prepared,detached=args.detach,case_concurrency=args.case_concurrency)
    if args.command=='status':
        from execution_state import inspect, same_process
        result={}
        for p in args.runs:
            if not (p/'job.json').exists() and (p/'delivery/run.json').is_file():
                import delivery
                result[str(p)]={'phase':'CLEANED','delivery':delivery.verify(p/'delivery')}
                continue
            job=json.loads((p/'job.json').read_text())
            if (p/'execution-status.json').exists():value=inspect(p)
            elif (p/'case-result.json').exists():value=json.loads((p/'case-result.json').read_text())
            else:
                launch_file=p/'batch.json' if (p/'batch.json').exists() else p/'launch.json'
                launch_record=json.loads(launch_file.read_text()) if launch_file.exists() else {}
                who=launch_record.get('controller')
                live=bool(who and same_process(who))
                value={'phase':'CANCEL_REQUESTED_NOT_STARTED' if (p/'cancel-request.json').exists() else
                       'QUEUED' if live else 'CONTROLLER_EXITED_BEFORE_CASE_START' if who else 'PREPARED_NOT_STARTED',
                       'controller':who,'controller_identity_matches':live,
                       'track':job['track'],'profiles':job['profiles']}
            result[str(p)]=value
            import fault_control
            value['paused_errors']=fault_control.pending(p)
        return result
    if args.command=='cancel':
        if len(args.runs)==1 and not (args.runs[0]/jobs.MARKER).is_file() and not args.task:
            import fault_control
            return fault_control.cancel_paused(args.runs[0])
        if args.task:
            if len(args.runs)!=1:raise ValueError('Task cancellation requires exactly one run')
            from execution_state import request_cancel
            return request_cancel(args.runs[0],args.task)
        from queue_controller import cancel_batch
        cancel_batch(args.runs);return {'status':'CANCEL_REQUESTED','runs':[str(p) for p in args.runs]}
    if args.command=='cleanup':
        import cleanup
        return cleanup.clean(apply=args.apply,grace=args.grace_seconds,outputs=args.runs)
    raise ValueError('Unknown workflow entry command')
