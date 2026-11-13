"""Bounded fresh process-query retries; parsing stays inside the attempt."""
from copy import deepcopy
from datetime import datetime
import subprocess

VERSION='yui-process-query-retry-1'
ATTEMPTS=3


def started(value):
    if not isinstance(value,str):raise ValueError('Malformed OS process start identity')
    value=' '.join(value.split())
    datetime.strptime(value,'%a %b %d %H:%M:%S %Y')
    return value


def retry(query, *, observe=None):
    """Retry only an actual timeout, using a new complete query and parse."""
    attempts=[]
    for number in range(1,ATTEMPTS+1):
        try:
            value=query()
        except subprocess.TimeoutExpired as error:
            attempts.append({'attempt':number,'outcome':'TIMEOUT'})
            if number<ATTEMPTS:continue
            error.process_query_attempts=deepcopy(attempts)
            if observe:observe({'version':VERSION,'attempts':attempts,'query_completed':False})
            raise
        except BaseException as error:
            if attempts:
                attempts.append({'attempt':number,'outcome':'FAILED','error_type':type(error).__name__})
                error.process_query_attempts=deepcopy(attempts)
                if observe:observe({'version':VERSION,'attempts':attempts,'query_completed':False})
            raise
        else:
            if attempts:
                attempts.append({'attempt':number,'outcome':'COMPLETE'})
                if observe:observe({'version':VERSION,'attempts':attempts,'query_completed':True})
            return value
