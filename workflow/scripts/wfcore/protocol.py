"""The messages accepted by the runner and returned by adapters."""

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

IDENT = re.compile(r"[a-z][a-z0-9_-]*\Z")
CONTRACT = re.compile(r"[A-Za-z][A-Za-z0-9_-]*@[1-9][0-9]*\Z")
DIGEST = re.compile(r"[a-f0-9]{64}\Z")


class Fault(ValueError):
    """Located protocol, wiring or ownership error."""


class Rejected(Fault):
    """A recoverable user input rejection. Leave the active port available."""


def need(condition, message):
    if not condition:
        raise Fault(message)


def object_shape(properties, required=None):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties) if required is None else required,
        "additionalProperties": False,
    }


TEXT = {"type": "string", "minLength": 1}
COUNT = {"type": "integer", "minimum": 0}
BLOB = object_shape(
    {"sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"}, "size": COUNT}
)
PORT = object_shape({"source": TEXT, "contract": TEXT})
ENVELOPE = object_shape(
    {
        "protocol": {"const": 1},
        "id": TEXT,
        "run": TEXT,
        "source": TEXT,
        "target": TEXT,
        "activation": {"type": "integer", "minimum": 1},
        "type": TEXT,
        "contract": TEXT,
        "data": {},
    }
)
REPLY = object_shape({"port": TEXT, "data": {}})
USAGE = object_shape({"input_tokens": COUNT, "output_tokens": COUNT})


def schema_registry(contracts):
    return Registry().with_resources(
        (
            "urn:workflow:" + key,
            Resource.from_contents(schema, default_specification=DRAFT202012),
        )
        for key, schema in contracts.items()
    )


def validate(schema, value, where, registry=None):
    validator = Draft202012Validator(
        schema, registry=registry if registry is not None else Registry()
    )
    try:
        error = next(validator.iter_errors(value), None)
    except RecursionError as exc:
        raise Fault(f"{where}: schema recursion does not consume input") from exc
    if error is not None:
        path = "/".join(str(x) for x in error.absolute_path)
        raise Fault(f"{where}/{path}: {error.message}")


def packet(run, ident, source, target, activation, event, contract, data):
    return {
        "protocol": 1,
        "run": run,
        "id": ident,
        "source": source,
        "target": target,
        "activation": activation,
        "type": event,
        "contract": contract,
        "data": data,
    }


def receive(message, expected, schema, registry=None):
    """One validator for external events, graph edges, map items and storage/control ports."""
    validate(ENVELOPE, message, "message")
    for key in (
        "protocol",
        "run",
        "source",
        "target",
        "activation",
        "type",
        "contract",
    ):
        need(
            message[key] == expected[key],
            f"unexpected {key} at {expected['target']}: {message[key]}",
        )
    validate(
        schema,
        message["data"],
        f"{expected['target']} ({expected['contract']})",
        registry,
    )
    return message["data"]


def checked_schema(schema, where, registered=()):
    need(isinstance(schema, dict), f"{where}: expected JSON Schema object")
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise Fault(f"{where}: {exc.message}") from exc
    dependencies = set()

    def visit(item):
        if not isinstance(item, dict):
            return
        for k in ("$ref", "$dynamicRef"):
            if k in item:
                ref = item[k]
                if isinstance(ref, str) and ref.startswith("urn:workflow:"):
                    key = ref.removeprefix("urn:workflow:")
                    need(
                        key in registered,
                        f"{where}: unregistered contract reference {key}",
                    )
                    dependencies.add(key)
                    continue
                need(
                    isinstance(ref, str) and ref.startswith("#/"),
                    f"{where}: use local JSON pointers or registered contract URNs",
                )
                obj = schema
                try:
                    for part in ref[2:].split("/"):
                        part = part.replace("~1", "/").replace("~0", "~")
                        obj = obj[int(part)] if isinstance(obj, list) else obj[part]
                except (KeyError, IndexError, ValueError, TypeError) as exc:
                    raise Fault(f"{where}: unresolved reference {ref}") from exc
        need("$id" not in item, f"{where}: contract IDs belong in the registry")
        for k in (
            "$defs",
            "definitions",
            "properties",
            "patternProperties",
            "dependentSchemas",
        ):
            for sub in item.get(k, {}).values():
                visit(sub)
        for k in ("allOf", "anyOf", "oneOf", "prefixItems"):
            for sub in item.get(k, []):
                visit(sub)
        for k in (
            "additionalProperties",
            "unevaluatedProperties",
            "propertyNames",
            "items",
            "unevaluatedItems",
            "contains",
            "if",
            "then",
            "else",
            "not",
            "contentSchema",
        ):
            visit(item.get(k))

    visit(schema)
    return dependencies


def unique(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, f"duplicate JSON key {key}")
        result[key] = value
    return result


def parse(data):
    def bad(text):
        raise Fault(f"invalid JSON number {text}")

    return json.loads(data, object_pairs_hook=unique, parse_constant=bad)


def load(path):
    return parse(Path(path).read_text(encoding="utf-8"))


def encode(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def durable(path, data):
    path = Path(path)
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(name).unlink(missing_ok=True)


def save(path, obj):
    durable(path, (encode(obj) + "\n").encode())


def fields(obj, required, optional, where):
    need(isinstance(obj, dict), f"{where}: object required")
    missing = set(required) - obj.keys()
    extra = obj.keys() - set(required) - set(optional)
    need(
        not missing and not extra,
        f"{where}: missing {sorted(missing)}, unexpected {sorted(extra)}",
    )


def symbol(name, where):
    need(
        isinstance(name, str) and IDENT.fullmatch(name),
        f"{where}: invalid identifier {name!r}",
    )


def filename(name):
    need(
        isinstance(name, str)
        and re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", name)
        and name not in {"receipt.json", "result.json"},
        f"invalid/reserved delivery filename {name!r}",
    )
