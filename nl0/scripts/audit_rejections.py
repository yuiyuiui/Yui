"""Remember diagnosed negative reviews within one case, before scheduling another review."""
import json
from pathlib import Path
import re

import audit_reuse
from controller_common import bind, verify_bindings, write
from execution_health import record_qualification
import nl0


def _content(value):
    if isinstance(value, list):
        return [_content(x) for x in value]
    if isinstance(value, dict):
        if set(value) == {'path', 'sha256'}:
            return {'sha256': value['sha256']}
        return {k:_content(v) for k,v in value.items() if k != 'retrieved_at'}
    return value


def review_key(source, scope, *, data=None, rules=None):
    if data is None:
        data = nl0.validate(source/'nl0.json', source/'spec.json')
    if scope == 'global':
        spec = dict(data[2])
        # Warm-repair instructions describe the earlier verdict. They add no
        # source evidence. Keep the original documents, mathematical inputs,
        # basis version and evidence bindings on which a new review can depend.
        spec['inputs'] = [(Path(r['path']).name, r['sha256']) for r in spec['inputs']
                          if Path(r['path']).name not in {'baseline.json','repair-obligations.json'}]
        graph = {k:v for k,v in data[1].items() if k != 'spec_sha256'}
        packet = {'spec':spec, 'graph':graph, 'rules':audit_reuse.rules() if rules is None else rules}
    else:
        packet = audit_reuse.context(data, 'packet:'+scope, semantic_rules=rules)
    return audit_reuse.hashed(_content(packet))


class RejectedReviews:
    def __init__(self, prior):
        self.history = {}
        for directory in prior:
            directory = Path(directory)
            path = directory/'rejected-review.json'
            if not path.is_file():
                continue
            saved = nl0.load(path)
            scope = saved['scope']
            review = self.review_path(directory, scope)
            if saved['review'] != bind(review):
                raise ValueError('Prior rejected review changed')
            plan = nl0.load(directory/'campaign.json')
            verify_bindings([plan['graph'],plan['spec']])
            source = Path(plan['case'])
            manifest = directory/scope/'stage/execution-manifest.json'
            rule_documents = nl0.load(manifest)['rule_documents']
            rules = {name:rule_documents[name] for name in audit_reuse.SEMANTIC_RULES}
            if self.record(directory, source, scope, persist=False, rules=rules) != saved:
                raise ValueError('Prior negative review context changed')

    @staticmethod
    def review_path(directory, scope):
        if scope == 'global':
            return directory/'global-acceptance.json'
        if not re.fullmatch(r'R\d+', scope):
            raise ValueError('Invalid rejected review scope')
        return directory/scope/'stage/accepted.json'

    def record(self, directory, source, scope, *, persist=True, data=None, rules=None):
        path = self.review_path(directory, scope)
        review = nl0.load(path)
        if scope == 'global':
            if review.get('accepted') is not False:
                raise ValueError('Only rejected global reviews enter failure history')
        else:
            result_path = path.parent/'result.json'
            if not record_qualification(nl0.load(result_path),allow_blocked=True)['submitted_record_qualified']:
                raise ValueError('Unqualified local execution cannot be a mathematical rejection')
            if review.get('verdict') == 'PASS' and audit_reuse.all_pass(review):
                raise ValueError('Passing packet cannot enter failure history')
        key = review_key(source, scope, data=data, rules=rules)
        saved = {'scope':scope, 'key':key, 'review':bind(path)}
        self.history.setdefault(scope,{})[key] = saved
        if persist:
            write(directory/'rejected-review.json', saved)
        return saved

    def match(self, source, scope, *, data=None):
        if scope not in self.history:
            return None
        key = review_key(source, scope, data=data)
        rejected = self.history[scope].get(key)
        if rejected:
            verify_bindings([rejected['review']])
        return rejected

    def check_submission(self, source, scopes=None, *, data=None):
        findings = []
        for scope in sorted(self.history) if scopes is None else scopes:
            if data is None and scope in self.history:
                data = nl0.validate(source/'nl0.json', source/'spec.json')
            if data is not None and scope!='global' and scope not in data[4]:
                continue
            rejected = self.match(source, scope, data=data)
            if rejected:
                review = nl0.load(rejected['review']['path'])
                findings.append({'scope':scope,'review':review['review'] if scope=='global' else review})
        if findings:
            return {'accepted':False,'error':'AUDIT_A_REPAIR_REQUIRED: address the original independent findings: '
                    +json.dumps(findings,ensure_ascii=False)}
        return {'accepted':True}
