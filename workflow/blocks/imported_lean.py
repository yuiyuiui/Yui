"""Native compatibility decisions; no source-fidelity or mathematical verdict."""
VERSION='yui-imported-lean-1'


def complete(check):
    native=(check or {}).get('native',{})
    return (type(native.get('exit_code')) is int and native['exit_code'] in (0,1)
            and not native.get('timed_out') and not native.get('cancelled') and not native.get('error_kind'))


def passed(check):
    return complete(check) and check['native']['exit_code']==0 and check.get('source_policy_passed') is True


def decide(current, *, upstream_available=False, context=None, original=None, candidate=None):
    base={'version':VERSION,'accepted_for_native_reuse':False,'semantic_acceptance':False,
          'decision_scope':'Native compatibility under the declared environments; ordinary source/type/dependency review remains required.'}
    if passed(current):return {**base,'status':'LOCAL_REUSED','accepted_for_native_reuse':True}
    if not complete(current):return {**base,'status':'LOCAL_CHECK_INCOMPLETE'}
    if not upstream_available:return {**base,'status':'UPSTREAM_ENVIRONMENT_REQUIRED'}
    if context is None or not passed(context):return {**base,'status':'UPSTREAM_CONTEXT_REQUIRED'}
    if not complete(original):return {**base,'status':'UPSTREAM_CHECK_INCOMPLETE'}
    route='COMPATIBILITY_PORT_REQUIRED' if passed(original) else 'CORRECTION_AND_PORT_REQUIRED'
    if candidate is None:return {**base,'status':route}
    status='PORTED_CHECKED' if passed(candidate) else 'PORT_CHECK_FAILED' if complete(candidate) else 'PORT_CHECK_INCOMPLETE'
    return {**base,'status':status,'original_route':route,'accepted_for_native_reuse':passed(candidate)}
