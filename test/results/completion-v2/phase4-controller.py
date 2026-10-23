"""Fresh development batch: one actual two-slot budget across all cases."""
from concurrent.futures import ThreadPoolExecutor,as_completed
import datetime
import json
from pathlib import Path
import sys
import threading
import traceback
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'test/support'))
import audit_a_campaign as a
import full_workflow as f
from clean_stage import ArtifactStage
RESULTS=ROOT/'test/results';OUT=RESULTS/'completion-v2'
BUDGET=a.concurrency.Budget(a.concurrency.resolve());LOCK=threading.Lock();STATES={}
def update(case,stage,**extra):
 with LOCK:
  STATES[case]={'stage':stage,'updated_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),**extra}
  temp=OUT/'phase4-progress.pending';a.write(temp,STATES);temp.replace(OUT/'phase4-progress.json')
  print(case,stage,extra,flush=True)
def geometry():
 out=RESULTS/'geometry-nl0-v10';update('geometry-product-dimension','BOUNDED_SOURCE_REPAIR',directory=str(out))
 stage=ArtifactStage(out/'stage',(out/'prompt.txt').read_text(),phase='nl0-authoring',kind='nl0',case_id='geometry-product-dimension',inputs=out/'inputs.json',timeout=1800,budget=BUDGET)
 stage.execute();f.accepted(out);source=out/'stage/case'
 f.audit_source('geometry-product-dimension',source,'geometry-audit-a-v4',BUDGET,update)
 return f.translate('geometry-product-dimension',source,'geometry-interface-v1','geometry-workflow-v1',BUDGET,update)
def wave():
 source=RESULTS/'wave-recovered-v11-candidate-0047/case'
 f.audit_source('wave-map-energy',source,'wave-audit-a-v5',BUDGET,update)
 return f.translate('wave-map-energy',source,'wave-interface-v1','wave-workflow-v1',BUDGET,update)
with ThreadPoolExecutor(max_workers=3) as pool:
 jobs={pool.submit(f.translate,'lie-module-irreducibility',RESULTS/'lie-nl0-v17/stage/case','lie-interface-v3','lie-workflow-v2',BUDGET,update):'lie-module-irreducibility',pool.submit(wave):'wave-map-energy',pool.submit(geometry):'geometry-product-dimension'}
 for future in as_completed(jobs):
  case=jobs[future]
  try:future.result()
  except Exception as error:
   (OUT/(case+'-phase4-error.txt')).write_text(traceback.format_exc());update(case,'REPAIR_REQUIRED',error=type(error).__name__+': '+str(error))
a.write(OUT/'phase4-concurrency.json',BUDGET.report())
