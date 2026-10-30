"""Positive classification and backoff for temporary remote service failures."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import math
import re
import errno
import http.client
import socket
import ssl


POLICY = {'version':'remote-service-retry-3','initial_delay_seconds':60,
          'maximum_backoff_seconds':60,'jitter_fraction':0,
          'maximum_attempts':30,'preserve_thread_and_tools':True,
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


def transport_error(error):
    """Only recognized network exceptions are transient; disk/tool I/O is local."""
    if isinstance(error,TimeoutError):code='request_timeout'
    elif isinstance(error,(http.client.IncompleteRead,http.client.RemoteDisconnected)):
        code='response_stream_disconnected'
    elif (isinstance(error,(ConnectionError,socket.gaierror,socket.herror,ssl.SSLError))
            or isinstance(error,OSError) and error.errno in {
                errno.ECONNRESET,errno.ECONNREFUSED,errno.ECONNABORTED,errno.ENETDOWN,
                errno.ENETUNREACH,errno.EHOSTUNREACH,errno.ETIMEDOUT}):code='network_error'
    else:code='harness_bug'
    return {'code':code,'message':str(error),'exception_type':type(error).__name__}


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


def diagnose(error):
    """Classify a fault without deciding task completion or authorizing cleanup."""
    if isinstance(error,BaseException):
        error=transport_error(error)
    if not isinstance(error,dict):error={'code':'unknown','message':str(error)}
    codes=set();statuses=[]
    def visit(value):
        if isinstance(value,dict):
            for key,item in value.items():
                token=normalized(key)
                if token in TRANSIENT|PERMANENT:codes.add(token)
                if key in {'code','type','codexErrorInfo','reason'} and isinstance(item,str):
                    codes.add(normalized(item))
                if key in {'httpStatusCode','http_status','status_code','status'} and type(item) is int:
                    statuses.append(item)
                if isinstance(item,(dict,list)):visit(item)
        elif isinstance(value,list):
            for item in value:visit(item)
    visit(error)
    quota={c for c in PERMANENT if any(w in c for w in ('quota','usagelimit','spendlimit','budget','billinghard'))}
    auth={'authenticationerror','invalidapikey','unauthorized','permissiondenied','modelnotfound','invalidmodel'}
    if codes & quota:category='model_quota'
    elif 'creditbalanceexhausted' in codes or 402 in statuses:category='model_balance'
    elif codes & auth or set(statuses)&{401,403}:category='model_auth'
    elif codes & {'harnessbug','localtoolerror','localerror','localprotocolrejected','localprovenancerejection'}:category='harness_bug'
    elif codes & (PERMANENT-quota-auth) or set(statuses)&{400,404,413,422}:category='model_request_rejected'
    elif 'workflowblocked' in codes:category='workflow_blocked'
    elif 'unknown' in codes:category='harness_bug'
    elif codes & {'responsestreamdisconnected','responsestreamconnectionfailed'}:category='model_stream_interrupted'
    elif codes & {'requesttimeout','timeout'} or 408 in statuses:category='model_timeout'
    elif codes & {'connectionerror','networkerror'}:category='model_transport'
    elif codes & {'serveroverloaded','serverisoverloaded','servererror','internalerror','serviceunavailable','serviceunavailableerror','ratelimitexceeded','slowdown'} or 429 in statuses or any(500<=s<600 for s in statuses):category='model_capacity'
    elif codes & {'httpconnectionfailed','connectionerror','networkerror'}:category='model_transport'
    else:category='harness_bug'
    retryable=category in {'model_capacity','model_transport','model_timeout','model_stream_interrupted'}
    return {'category':category,'retryable':retryable,
            'kind':'REMOTE_SERVICE_TRANSIENT' if retryable else 'ERROR_REQUIRES_ACTION',
            'codes':sorted(codes),'http_statuses':sorted(set(statuses))}


def classify(error):
    """Compatibility predicate for historical remote-only recovery guards."""
    result=diagnose(error)
    return result if result['retryable'] else None


def delay(attempt, *, retry_after_seconds=None):
    if type(attempt) is not int or attempt<1:raise ValueError('Retry attempt must be positive')
    return POLICY['initial_delay_seconds']
