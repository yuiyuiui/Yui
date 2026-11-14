"""Bounded fresh process-query retries; parsing stays inside the attempt."""
from copy import deepcopy
from datetime import datetime
import subprocess
import time

VERSION='yui-process-query-retry-2'
TIMEOUTS=(5,15,30)
ATTEMPTS=len(TIMEOUTS)
DECISION_VERSION='yui-process-diagnosis-1'


def started(value):
    if not isinstance(value,str):raise ValueError('Malformed OS process start identity')
    value=' '.join(value.split())
    datetime.strptime(value,'%a %b %d %H:%M:%S %Y')
    return value


def retry(query, *, observe=None):
    """Retry only an actual timeout, using a new complete query and parse."""
    attempts=[]
    for number,limit in enumerate(TIMEOUTS,1):
        begin=time.monotonic()
        try:
            value=query(limit)
        except subprocess.TimeoutExpired as error:
            attempts.append({'attempt':number,'timeout_seconds':limit,'elapsed_seconds':time.monotonic()-begin,'outcome':'TIMEOUT'})
            if number<ATTEMPTS:continue
            error.process_query_attempts=deepcopy(attempts)
            if observe:observe({'version':VERSION,'attempts':attempts,'query_completed':False})
            raise
        except BaseException as error:
            if attempts or isinstance(error,ValueError):
                attempts.append({'attempt':number,'timeout_seconds':limit,'elapsed_seconds':time.monotonic()-begin,'outcome':'FAILED','error_type':type(error).__name__})
                error.process_query_attempts=deepcopy(attempts)
                if observe:observe({'version':VERSION,'attempts':attempts,'query_completed':False})
            raise
        else:
            if attempts:
                attempts.append({'attempt':number,'timeout_seconds':limit,'elapsed_seconds':time.monotonic()-begin,'outcome':'COMPLETE'})
                if observe:observe({'version':VERSION,'attempts':attempts,'query_completed':True})
            return value


def decision(value):
    """AI advice requests an action; only a fresh native check confirms exit."""
    required={'version','incident','checkpoint_sha256','observation_sha256','assessment','observations','unknowns','options','action'}
    if not isinstance(value,dict) or not required<=value.keys() or value.keys()-required-{'delay_seconds'}:
        raise ValueError('Supply the complete process diagnosis and exact incident bindings')
    if value['version']!=DECISION_VERSION:raise ValueError('Unknown process diagnosis version')
    for key in ('incident','checkpoint_sha256','observation_sha256'):
        if not isinstance(value[key],str) or not value[key]:raise ValueError('Missing '+key)
    if value['assessment'] not in {'CONFIRMED','LIKELY','UNKNOWN'}:raise ValueError('Invalid assessment')
    for key in ('observations','unknowns','options'):
        if not isinstance(value[key],list) or any(not isinstance(s,str) or not s.strip() for s in value[key]):
            raise ValueError('Use located text for '+key)
    if not value['observations'] or not value['options'] or (value['assessment']=='UNKNOWN' and not value['unknowns']):
        raise ValueError('Record observations, options and evaluated uncertainty')
    if value['action'] not in {'recheck','wait','escalate'}:raise ValueError('A diagnosis cannot authorize pass, signals or cancellation')
    delay=value.get('delay_seconds',60 if value['action']=='wait' else 0)
    if type(delay) is not int or not 0<=delay<=300:raise ValueError('Wait must be between zero and 300 seconds')
    return {**deepcopy(value),'delay_seconds':delay}
