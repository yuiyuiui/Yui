"""Wall-clock policy inside nl02lean. A review can authorize a retry, never a proof."""
INITIAL_SECONDS = 360
MAX_SECONDS = 1800
CATEGORIES = ('code_issue', 'workload_only', 'uncertain')


def decision(current, diagnosis, *, ceiling=MAX_SECONDS):
    if not 0 < current <= MAX_SECONDS or diagnosis not in CATEGORIES:
        raise ValueError('Invalid native Lean allowance or diagnosis')
    if diagnosis == 'code_issue':
        return 'repair', current
    if diagnosis == 'uncertain':
        return 'inspect', current
    following = current + INITIAL_SECONDS
    if following <= min(MAX_SECONDS, ceiling):
        return 'retry', following
    return 'limit', current
