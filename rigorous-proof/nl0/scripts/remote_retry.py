"""Positive classification and backoff for temporary remote service failures."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import math
import random
import re


POLICY = {'version':'remote-service-retry-1','initial_delay_seconds':15,
          'maximum_backoff_seconds':300,'jitter_fraction':0.2,
          'maximum_attempts':None,'preserve_thread_and_tools':True,
          'model_fallback':False,'cancellable_wait':True}

TRANSIENT = {'serveroverloaded','serverisoverloaded','servererror','internalerror',
             'serviceunavailable','serviceunavailableerror','requesttimeout','timeout',
             'responsestreamdisconnected','responsestreamconnectionfailed',
             'httpconnectionfailed','connectionerror','networkerror',
             'ratelimitexceeded','slowdown'}
PERMANENT = {'invalidrequest','invalidrequesterror','authenticationerror','invalidapikey',
             'unauthorized','permissiondenied','modelnotfound','invalidmodel',
             'contextlengthexceeded','maxoutputtokens','outputtokenlimit',
             'insufficientquota','quotaexceeded','usagelimitexceeded','usagelimitreached',
             'creditbalanceexhausted','projectspendlimitexceeded',
             'organizationspendlimitexceeded','organizationusagelimitexceeded',
             'sessionbudgetexceeded','billinghardlimitreached','cancelled','interrupted',
             'localprotocolrejected','localprovenancerejection'}


def normalized(value):return re.sub('[^a-z0-9]','',value.lower())


def retry_after(value, *, at=None):
    """Parse a real Retry-After header; malformed values grant no delay."""
    if isinstance(value,bool) or value is None:return None
    try:
        seconds=float(value)
    except (ValueError,TypeError):
        try:
            date=parsedate_to_datetime(str(value))
            if date.tzinfo is None:date=date.replace(tzinfo=timezone.utc)
            seconds=(date-(at or datetime.now(timezone.utc))).total_seconds()
        except (ValueError,TypeError,OverflowError):return None
    return max(0,seconds) if math.isfinite(seconds) else None


def classify(error):
    """Use structured codes, never a free-text guess about mathematical work."""
    if not isinstance(error,dict):return None
    codes=set();statuses=[]
    def visit(value):
        if isinstance(value,dict):
            for key,item in value.items():
                token=normalized(key)
                if token in TRANSIENT|PERMANENT:codes.add(token)
                if key in {'code','type','codexErrorInfo','reason'} and isinstance(item,str):
                    codes.add(normalized(item))
                if key in {'httpStatusCode','http_status','status_code'} and type(item) is int:
                    statuses.append(item)
                if isinstance(item,(dict,list)):visit(item)
        elif isinstance(value,list):
            for item in value:visit(item)
    visit(error)
    if codes & PERMANENT or any(status in {400,401,403,404,413,422} for status in statuses):return None
    if not codes & TRANSIENT and not any(status in {408,429} or 500<=status<600 for status in statuses):return None
    return {'kind':'REMOTE_SERVICE_TRANSIENT','codes':sorted(codes & TRANSIENT),
            'http_statuses':sorted(set(statuses))}


def delay(attempt, *, retry_after_seconds=None):
    if type(attempt) is not int or attempt<1:raise ValueError('Retry attempt must be positive')
    cap=POLICY['maximum_backoff_seconds']
    base=min(cap,POLICY['initial_delay_seconds']*2**min(attempt-1,10))
    seconds=min(cap,base*random.uniform(1-POLICY['jitter_fraction'],1+POLICY['jitter_fraction']))
    return max(seconds,retry_after_seconds or 0)
