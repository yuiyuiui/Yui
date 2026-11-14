"""Read-only breakdown of recorded wall time and usage; no model introspection."""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from usage import json_rows


def rows(path):
    if path.is_file():yield from json_rows(path)


def summarize(directory):
    root=Path(directory).resolve();stages=[]
    for file in sorted(root.rglob('result.json')):
        stage=file.parent
        if not (stage/'execution-manifest.json').is_file():continue
        result=json.loads(file.read_text());manifest=json.loads((stage/'execution-manifest.json').read_text())
        canonical=result.get('stage_log_path')
        if canonical and Path(canonical).resolve()!=stage.resolve():continue
        if not canonical and any(name in {'review-evidence','runtime','harness-snapshot'} for name in stage.relative_to(root).parts):continue
        totals={};tool_count=0
        for row in rows(stage/'tools.jsonl'):
            tool_count+=1
            key=row['tool'];duration=row.get('wall_seconds')
            totals[key]=(totals.get(key,0)+duration if isinstance(duration,(int,float)) and totals.get(key,0) is not None else None)
        stages.append({'stage':str(stage.relative_to(root)),'phase':manifest.get('phase',result.get('mode')),
            'status':result.get('status'),'task_outcome':result.get('task_outcome'),
            'wall_seconds':result.get('wall_seconds'),'slot_queue_seconds':result.get('queue_seconds'),
            'tool_calls':tool_count,'tool_wall_seconds_by_name':totals,'requests':None,
            'request_observations':[],'usage':result.get('usage'),
            'execution_health':result.get('execution_health'),
            'measurement_valid':result.get('measurement_valid',False)})
    return {'schema':'yui-phase-metrics-1','stages':stages,
            'pure_internal_model_reasoning_seconds':None,
            'scope':'Recorded stage wall time includes nested tools. Do not sum overlapping/nested durations. Missing usage remains unknown; acquisition, warm reuse and owner work need their own disclosed records.'}
