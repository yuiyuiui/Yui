"""Business decisions shared by the native adapters and the finite protocol fixtures."""
def outcome(port, data):
    return {'port': port, 'data': data}

def final_data(data, binding):
    return {'job': data['job'], 'goal': data['goal'], 'outcome': binding}

def after_audit(data, authority, result):
    if data['goal'] == 'audit':
        return outcome('finish', final_data(data, result))
    return outcome('formalize', {k:data[k] for k in ('job','goal','global')} | {'authority':authority})

def after_translation(data, result, *, different=False):
    if data['goal'] == 'unconditional' and not different:
        return outcome('discharge', {**data, 'intermediate':result})
    return outcome('finish', final_data(data, result))

def classify(goal, status, *, closed, qualified):
    if status == 'STOPPED_BY_USER': return 'stopped', 'STOPPED'
    if status == 'DIFFERENT_RESULT_DELIVERED': return 'different', 'DIFFERENT_RESULT'
    if goal == 'audit':
        if status == 'DRAFT-AUDIT-PASSED': return 'audited', 'NL0'
        if status == 'DRAFT-AUDIT-CONDITIONAL': return 'qualified-audit', 'NL0_SOURCE_QUALIFIED'
    elif status in ('WORKFLOW-PASSED', 'WORKFLOW-CONDITIONAL'):
        if goal == 'unconditional':
            if closed and not qualified and status == 'WORKFLOW-PASSED': return 'unconditional','UNCONDITIONAL_LEAN'
            if closed and qualified: return 'qualified', 'CLOSED_LEAN_SOURCE_QUALIFIED'
            if status == 'WORKFLOW-PASSED':
                raise ValueError('An unconditional pass requires verified kernel closure')
        return 'conditional', 'CONDITIONAL_LEAN'
    raise ValueError(f'No delivery for {goal} with unfinished outcome {status}')
