"""Wall-clock policy inside nl02lean. A review can authorize a retry, never a proof."""
INITIAL_SECONDS = 360
MAX_SECONDS = 1800
WHOLE_FILE_INITIAL_SECONDS = 1800
WHOLE_FILE_INCREMENT_SECONDS = 900
WHOLE_FILE_MAX_SECONDS = 3600
CATEGORIES = ('code_issue', 'workload_only', 'uncertain')


def limits(kind='local'):
    if kind == 'local':
        return INITIAL_SECONDS, INITIAL_SECONDS, MAX_SECONDS
    if kind == 'whole_file':
        return WHOLE_FILE_INITIAL_SECONDS, WHOLE_FILE_INCREMENT_SECONDS, WHOLE_FILE_MAX_SECONDS
    raise ValueError('Unknown native Lean check kind')


def decision(current, diagnosis, *, ceiling=None, kind='local'):
    _, increment, maximum = limits(kind)
    if not 0 < current <= maximum or diagnosis not in CATEGORIES:
        raise ValueError('Invalid native Lean allowance or diagnosis')
    if diagnosis == 'code_issue':
        return 'repair', current
    if diagnosis == 'uncertain':
        return 'inspect', current
    following = current + increment
    if following <= min(maximum, maximum if ceiling is None else ceiling):
        return 'retry', following
    return 'limit', current
