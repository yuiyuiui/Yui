"""Each public handler runs in the selected Yui case and returns a typed transition."""
from .blocks import routing


def dispatch(ctx, data, name):
    import sys
    if 'workflow_execution' in sys.modules:
        from workflow_execution import active
        session = active.get()
        if session is not None:
            return session.dispatch(name, ctx, data, routing)
    from .blocks.prepared_case import invoke
    return invoke(ctx, data)


def request_audit(ctx, data): return dispatch(ctx, data, 'request_audit')
def request_conditional(ctx, data): return dispatch(ctx, data, 'request_conditional')
def request_unconditional(ctx, data): return dispatch(ctx, data, 'request_unconditional')
def reduce(ctx, data): return dispatch(ctx, data, 'reduce')
def direct_outline(ctx, data): return dispatch(ctx, data, 'direct_outline')
def basis_outline(ctx, data): return dispatch(ctx, data, 'basis_outline')
def freeze_global(ctx, data): return dispatch(ctx, data, 'freeze_global')
def detail(ctx, data): return dispatch(ctx, data, 'detail')
def audit(ctx, data): return dispatch(ctx, data, 'audit')
def translate(ctx, data): return dispatch(ctx, data, 'translate')
def close(ctx, data): return dispatch(ctx, data, 'close')
def publish(ctx, data): return dispatch(ctx, data, 'publish')
