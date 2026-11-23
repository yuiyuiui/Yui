"""One interruptible compile per request, with its shortest applicable limit."""
WHOLE_FILE_SECONDS = 1800
PROBE_SECONDS = 60


def allowance(configured, requested, stage_remaining=None):
    limits = [seconds for seconds in (configured,requested,stage_remaining) if seconds is not None]
    seconds = min(limits) if limits else None
    return seconds, stage_remaining is not None and seconds == stage_remaining
