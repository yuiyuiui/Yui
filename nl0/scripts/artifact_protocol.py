"""Shared JSON contracts for model tools, draft feedback and artifact readers.

This intentionally supports only the JSON Schema vocabulary emitted below.
Semantic checks (proofs, provenance, resolving locations) remain with the owner.
No validator repairs a value, drops fields or supplies a reviewer judgment.
"""
from copy import deepcopy
import json
import re


TEXT = {'type': 'string', 'minLength': 1, 'pattern': r'\S'}
STRING = {'type': 'string'}
VERDICT = {'type': 'string', 'enum': ['PASS', 'FAIL', 'UNVERIFIED']}


def obj(properties, required=None, *, extra=False):
    return {'type': 'object', 'properties': deepcopy(properties),
            'required': sorted(properties if required is None else required),
            'additionalProperties': deepcopy(extra)}


def array(items, **limits):
    return {'type': 'array', 'items': deepcopy(items), **limits}


def choice(*schemas):
    return {'anyOf': deepcopy(list(schemas))}


def nullable(schema):
    return choice(schema, {'type': 'null'})


def literal(value):
    return {'const': value}


def pointer(path, key):
    return path + '/' + str(key).replace('~', '~0').replace('/', '~1')


def _errors(value, schema, path):
    if 'allOf' in schema:
        errors=[error for branch in schema['allOf'] for error in _errors(value,branch,path)]
        if errors:return errors
    if 'not' in schema and not _errors(value,schema['not'],path):
        return [f'{path or "/"}: value matches an excluded schema variant']
    if 'anyOf' in schema:
        errors = [_errors(value, branch, path) for branch in schema['anyOf']]
        if any(not rows for rows in errors):
            return []
        # Prefer the object alternative whose declared fields match the input.
        def score(index):
            branch=schema['anyOf'][index]
            properties = branch.get('properties', {})
            overlap = len(set(value) & properties.keys()) if isinstance(value, dict) else 0
            tags = [(value[key],child) for key,child in properties.items()
                    if isinstance(value,dict) and key in value and ('const' in child or 'enum' in child)]
            wrong = sum(bool(_errors(item,child,path)) for item,child in tags)
            excluded='not' in branch and not _errors(value,branch['not'],path)
            return (excluded, wrong, -(len(tags)-wrong), -overlap, len(errors[index]), index)
        return errors[min(range(len(errors)), key=score)]
    where = path or '/'
    if 'const' in schema and (value != schema['const'] or type(value) is not type(schema['const'])):
        return [f'{where}: expected {json.dumps(schema["const"])}']
    kinds = schema.get('type')
    kinds = [kinds] if isinstance(kinds, str) else kinds
    matches = {'object': isinstance(value, dict), 'array': isinstance(value, list),
               'string': isinstance(value, str), 'integer': type(value) is int,
               'number': type(value) in (int, float), 'boolean': type(value) is bool,
               'null': value is None}
    if kinds and not any(matches[kind] for kind in kinds):
        return [f'{where}: expected {" or ".join(kinds)}, got {type(value).__name__}']
    if 'enum' in schema and not any(value == item and type(value) is type(item) for item in schema['enum']):
        return [f'{where}: expected one of {json.dumps(schema["enum"])}']
    errors = []
    if isinstance(value, dict):
        properties = schema.get('properties', {})
        extra = schema.get('additionalProperties', True)
        missing = sorted(set(schema.get('required', ())) - value.keys())
        unexpected = sorted(value.keys() - properties.keys()) if extra is False else []
        if missing or unexpected:
            identity=f' ({value["id"]})' if 'id' in properties and isinstance(value.get('id'),str) else ''
            errors.append(f'{where}{identity}: missing={missing}, unexpected={unexpected}')
        for key, item in value.items():
            child = properties.get(key, extra)
            if isinstance(child, dict):
                errors.extend(_errors(item, child, pointer(path, key)))
    elif isinstance(value, list):
        for bound, compare in [('minItems', len(value) < schema.get('minItems', 0)),
                               ('maxItems', len(value) > schema.get('maxItems', len(value)))]:
            if compare: errors.append(f'{where}: {bound}={schema[bound]}')
        if schema.get('uniqueItems') and len({json.dumps(x, sort_keys=True) for x in value}) != len(value):
            errors.append(f'{where}: items must be unique')
        if 'items' in schema:
            for index, item in enumerate(value):
                errors.extend(_errors(item, schema['items'], pointer(path, index)))
    elif isinstance(value, str):
        if len(value) < schema.get('minLength', 0): errors.append(f'{where}: text is too short')
        if len(value) > schema.get('maxLength', len(value)): errors.append(f'{where}: text is too long')
        if 'pattern' in schema and not re.search(schema['pattern'], value):
            errors.append(f'{where}: text must match {schema["pattern"]}')
    elif type(value) in (int, float):
        if value < schema.get('minimum', value): errors.append(f'{where}: minimum={schema["minimum"]}')
        if value > schema.get('maximum', value): errors.append(f'{where}: maximum={schema["maximum"]}')
    return errors


def validate(value, schema, path='', *, error_type=ValueError):
    errors = _errors(value, schema, path)
    if errors:
        raise error_type('; '.join(errors[:12]))


def instructions(schema):
    return ('\nThe submission JSON Schema below is generated from the same contract used by '
            'the validator. Match its fields exactly; additionalProperties:false forbids extra '
            'fields at that level. Format validity does not establish mathematical correctness.\n'
            + json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n')


class Contract:
    """Expose one structural definition to both the tool and its semantic owner."""
    def __init__(self, schema, check):
        self.schema = deepcopy(schema)
        self.check = check

    def __call__(self, value):
        validate(value, self.schema)
        return self.check(value)


def judgment(location=STRING, *, extra=None):
    return obj({'verdict': VERDICT, 'notes': TEXT,
                'locations': array(location, minItems=1), **(extra or {})})


def finding_schema(blocking_fields):
    """Keep extensible notes, but advertise required evidence for a blocker."""
    severity='^(?:'+'|'.join(''.join('['+c.lower()+c+']' for c in word)
                            for word in ['BLOCKING','FAIL','ERROR','FATAL'])+')$'
    trigger=choice(obj({'verdict':literal('FAIL')},extra=True),
                   obj({'severity':{'type':'string','pattern':severity}},extra=True))
    fields={'verdict':STRING,'severity':STRING,**blocking_fields}
    ordinary=obj(fields,required=[],extra=True);ordinary['not']=trigger
    return choice(obj(fields,required=blocking_fields,extra=True),ordinary)


class ReviewShape:
    """Define judgments once; derive whole, partial, saved and row-tool contracts."""
    def __init__(self, *, groups=None, rows=None, summary=None, optional=None, identities=None):
        groups, rows = groups or {}, rows or {}
        summary, optional = summary or {}, optional or {}
        self.base = {name: {} for name in groups}
        self.base.update(identities or {})
        self.rows = {pointer('/' + name, key): deepcopy(schema)
                     for name, children in groups.items() for key, schema in children.items()}
        self.rows.update({'/' + name: deepcopy(schema) for name, schema in rows.items()})
        self.required = sorted(self.rows)
        properties = {name: obj(children) for name, children in groups.items()}
        properties.update(rows); properties.update(summary); properties.update(optional)
        properties.update({key:literal(value) for key,value in (identities or {}).items()})
        self.output_schema = obj(properties, required=set(properties) - set(optional))
        self.summary_schema = obj({**summary, **optional}, required=summary)
        partial = deepcopy(properties)
        for name, children in groups.items():
            partial[name] = obj({key: nullable(schema) for key, schema in children.items()}, required=[])
        for name, schema in rows.items(): partial[name] = nullable(schema)
        partial['coverage'] = obj({p: {'enum': ['unread', 'read', 'assessed']} for p in self.required})
        complete=deepcopy(properties)
        complete['coverage']=obj({p:literal('assessed') for p in self.required})
        unfinished=obj(partial, required=['coverage'])
        unfinished['not']=obj({'coverage':complete['coverage']},required=['coverage'],extra=True)
        self.schema = choice(obj(complete,required=[*self.output_schema['required'],'coverage']),unfinished,
                             obj({'from_saved_review': literal(True), 'summary': self.summary_schema}))

    def validate(self, value):
        validate(value, self.output_schema)

    def record_schema(self):
        alternatives = []
        for key, schema in self.rows.items():
            alternatives.extend([
                obj({'pointer': literal(key), 'coverage': literal('assessed'), 'judgment': schema}),
                obj({'pointer': literal(key), 'coverage': {'enum': ['unread', 'read']},
                     'judgment': {'type': 'null'}})])
        return {'type':'object',**choice(*alternatives)} if alternatives else obj({}, extra=False)
