"""Offline doubles for the external proof backend. Distinct fixture names select outcomes."""
from .blocks.routing import outcome, after_audit, after_translation, classify

def ref(label):
    return {'path': label, 'sha256': 'a' * 64}

def request_audit(ctx, data): return outcome('selected', {**data, 'goal': 'audit'})
def request_conditional(ctx, data): return outcome('selected', {**data, 'goal': 'conditional'})
def request_unconditional(ctx, data): return outcome('selected', {**data, 'goal': 'unconditional'})

def reduce(ctx, data):
    if data['job']['path'] == 'stop':
        return outcome('stopped', {**data, 'outcome': ref('stop')})
    return outcome('prepared', {**data, 'basis': ref('basis')})

def direct_outline(ctx, data):
    return outcome('selected', {**data, 'global': ref('outline')})

def basis_outline(ctx, data):
    return direct_outline(ctx, {k:data[k] for k in ('job','goal')})

def freeze_basis(ctx, data):
    if data['job']['path']=='tampered-foundation':
        data={**data,'basis':{**data['basis'],'sha256':'b'*64}}
    return outcome('frozen',data)

def detail(ctx, data):
    if data['job']['path']=='recurring-edge' or (data['job']['path']=='local-edge' and data['global']['path']=='outline'):
        return outcome('repair',{**data,'repair':ref('missing input')})
    return outcome('detailed',{**data,'local':ref('local')})

def revise_graph(ctx, data):
    return outcome('selected',{k:data[k] for k in ('job','goal')} | {'global':ref('revised-'+str(ctx.activation))})

def audit(ctx, data):
    common={k:data[k] for k in ('job','goal','global')}
    if data['job']['path']=='audit-edge' and data['global']['path']=='outline':
        return outcome('repair',{**common,'repair':ref('audit finding')})
    return outcome('reviewed',{**common,'authority':ref('reviewed source')})

def seal_audit(ctx, data):
    if data['job']['path']=='modified-after-review':
        data={**data,'authority':{**data['authority'],'sha256':'b'*64}}
    return outcome('sealed',data)

def audit_exit(ctx, data):
    return after_audit(data,data['authority'],ref(data['job']['path']))

def translate(ctx, data):
    different = data['job']['path'] == 'different'
    return after_translation(data, ref(data['job']['path']), different=different)

def close(ctx, data):
    return outcome('finish', {k:data[k] for k in ('job','goal')} | {'outcome': data['intermediate']})

def publish(ctx, data):
    case = data['job']['path']
    status = {'stop':'STOPPED_BY_USER','different':'DIFFERENT_RESULT_DELIVERED'}.get(case)
    if not status:
        status = ('DRAFT-AUDIT-CONDITIONAL' if case=='qualified' else 'DRAFT-AUDIT-PASSED') if data['goal']=='audit' else 'WORKFLOW-CONDITIONAL' if case in ('qualified','residual') else 'WORKFLOW-PASSED'
    closed = case in ('closed','qualified','local-edge')
    extra = {'residual':['E004'],'external':['E001']}.get(case,[])
    port, scope = classify(data['goal'], status, closed=closed, qualified=case=='qualified')
    return outcome(port, {'scope':scope,'extra_premises':extra,'inventory':ctx.put_file(scope.encode())})
