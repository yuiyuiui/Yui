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
def reduce(ctx, data):
    """Finish the NL route, prepare proofs and machine-check complete native source types.

    The existing independent basis review covers classification, sources, uses
    and exact handoff references. Findings return to the editable author before
    the accepted package is frozen. An author may consult the optional catalog.
    """
    return dispatch(ctx, data, 'reduce')
def direct_outline(ctx, data):
    """Select a working graph with each proposition's direct consumers and document locations."""
    return dispatch(ctx, data, 'direct_outline')

def basis_outline(ctx, data):
    """Assign M/E labels and retain reviewed statements and document locations in the same working graph format."""
    return dispatch(ctx, data, 'basis_outline')

def freeze_basis(ctx, data):
    """Pin the exact reviewed classification, source, type, proof and handoff; honor the optional checkpoint."""
    return dispatch(ctx, data, 'freeze_basis')

def await_revision(ctx, data, event):
    """Forward the bound repair when the owning case dispatches its next revision."""
    return routing.outcome('ready',data)


def revise_graph(ctx, data):
    """Give the located finding to the global author. Validate revised labels and every consumer against the same frozen foundations."""
    return dispatch(ctx, data, 'revise_graph')

def seal_audit(ctx, data):
    """Verify the exact graph, specification and Audit A evidence at the selected revision."""
    return dispatch(ctx, data, 'seal_audit')

def audit_exit(ctx, data):
    """Deliver the audited NL0 or pass its sealed authority to Lean."""
    return dispatch(ctx, data, 'audit_exit')

def detail(ctx, data):
    """Fill the inference bodies or report a located defect in the assigned graph."""
    return dispatch(ctx, data, 'detail')

def audit(ctx, data):
    """Independently review the complete current NL0 and route located graph findings."""
    return dispatch(ctx, data, 'audit')

def translate(ctx, data):
    """Authors may consult strategy cards. Check helper declarations incrementally, compile the combined proof and audit the export.

    Every native wall timeout receives a source-located diagnosis. Local checks
    start at six minutes and rise by six to thirty only for workload findings.
    Complete-file assembly/export/inspection and final basis closure start at
    thirty minutes and rise by fifteen to sixty. Code repair retains its current
    allowance; partial output from a timed-out check cannot pass acceptance.
    A complete local round may retain GRAPH_ASSEMBLY_REPAIR_REQUIRED while
    selection, reading and assembly preparation pass its exact bound files to
    connection repair. Incomplete rounds remain available to diagnosis/reuse
    under their own gates. Final acceptance requires actual compiled evidence.
    OS snapshots use fresh 5/15/30-second attempts. Exhausted native cleanup
    suspends in place for the owning AI's bound diagnosis and recheck/wait or
    escalation, with one delayed recheck. Advice cannot grant process exit or
    proof acceptance; untouched proof work and the pending native call survive.
    Diagnostic dispatch requests owner wake; only a fresh bound observation
    acknowledges takeover. Missing acknowledgement requests attention once.
    """
    return dispatch(ctx, data, 'translate')
def close(ctx, data): return dispatch(ctx, data, 'close')
def publish(ctx, data): return dispatch(ctx, data, 'publish')
