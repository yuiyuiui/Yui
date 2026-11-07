"""Exercise the real state machine using declared seeds, branch inputs and independent expectations."""

import copy
import shutil
import tempfile
import time
from collections import deque
from pathlib import Path

from . import storage
from .engine import Run, replay, start
from .model import Model
from .protocol import Fault, digest, fields, load, need, validate


def expand(value, data, root):
    if isinstance(value, list):
        return [expand(v, data, root) for v in value]
    if isinstance(value, dict):
        if set(value) == {"$file"}:
            return storage.store_blob(root, value["$file"].encode("utf-8"))
        if set(value) == {"$input"}:
            return data[value["$input"]]
        return {k: expand(v, data, root) for k, v in value.items()}
    return value


def expect(run, target):
    view = run.view()
    need(bool(target), "empty expectation")
    for key, wanted in target.items():
        if key == "files":
            delivered = storage.verify_delivery(run.root)["files"]
            need(
                isinstance(wanted, dict) and set(delivered) == set(wanted),
                "unexpected delivery file set",
            )
            for name, content in wanted.items():
                need(
                    (run.root / "delivery" / name).read_bytes() == content.encode(),
                    f"wrong content: {name}",
                )
        elif key == "data" and isinstance(wanted, dict):
            actual = view["data"]
            need(isinstance(actual, dict), "expected object payload")
            if not wanted:
                need(not actual, "expected empty payload")
            for field, value in wanted.items():
                need(field in actual, f"missing expected field data.{field}")
                validate({"const": value}, actual[field], "expected data." + field)
        else:
            need(key in view, f"missing status field {key}")
            validate({"const": wanted}, view[key], "expected " + key)


def require_reject(action, why):
    try:
        action()
    except (Fault, ValueError):
        return
    raise Fault(f"{why}: invalid operation was accepted")


def collect(run, observed, witnesses, label):
    local = {k: set() for k in observed}
    for row in run.s["trace"]:
        local["edges"].add((row["node"], row["port"], row["next"]))
        if row["event"]:
            local["events"].add((row["node"], row["event"]["type"]))
    local["entries"].add(run.s["entry"])
    if run.s["status"] == "completed":
        storage.verify_delivery(run.root)
        local["exits"].add(run.s["node"])
    replay(run.s, run.model)
    for kind, values in local.items():
        observed[kind].update(values)
        for item in values:
            witnesses[kind].setdefault(item, []).append(label)


def exercise(project, root, entry, inputs, steps, observed, probes, witnesses, label):
    start(project, root, entry, copy.deepcopy(inputs))
    with storage.lock(root):
        run = Run(root)
        for i, step in enumerate(steps):
            if "signal" in step:
                fields(step, {"signal", "data"}, {"reject"}, "scenario signal")
                msg = run.letter(
                    step["signal"],
                    expand(step["data"], run.s["data"], root),
                    f"message-{i}",
                )
                if step.get("reject"):
                    before = (
                        run.s["activation"],
                        digest(run.s["data"]),
                        len(run.s["trace"]),
                    )
                    require_reject(lambda: run.signal(msg), "rejected business input")
                    need(
                        before
                        == (
                            run.s["activation"],
                            digest(run.s["data"]),
                            len(run.s["trace"]),
                        )
                        and run.s["status"] == "waiting",
                        "business rejection advanced the workflow",
                    )
                    continue
                for key, value in (
                    ("run", "foreign"),
                    ("source", "undeclared-source"),
                    ("activation", 0),
                    ("contract", "Unknown@999"),
                ):
                    before = copy.deepcopy(run.s)
                    require_reject(
                        lambda: run.signal({**msg, key: value}), f"wrong {key}"
                    )
                    need(run.s == before, "rejected envelope changed state")
                    probes.add("wrong-" + key)
                reject_duplicates = run.block.get("on_duplicate") == "reject"
                run.signal(msg)
                accepted = copy.deepcopy(run.s)
                if reject_duplicates:
                    require_reject(
                        lambda: run.signal(msg), "duplicate under reject policy"
                    )
                else:
                    run.signal(msg)
                need(run.s == accepted, "duplicate changed state")
                require_reject(
                    lambda: run.signal({**msg, "source": "other"}), "collision"
                )
                require_reject(
                    lambda: run.signal({**msg, "id": f"late-{i}"}), "late message"
                )
                probes.update(("duplicate", "id-collision", "late"))
            elif set(step) == {"expect"}:
                expect(run, step["expect"])
            elif step == {"cancel": True}:
                run.cancel()
            elif step == {"resume": True}:
                run = Run(root)
                run.resume()
            else:
                raise Fault(f"invalid scenario step {step}")
        collect(run, observed, witnesses, label)
        return run.view()


def verify(project, *, inherited_cases=()):
    started = time.monotonic()
    project = Path(project)
    model = Model(project)
    fixtures = load(project / "fixtures.json")
    fields(fixtures, {"seeds", "events", "max_depth", "max_paths"}, set(), "fixtures")
    cases = load(project / "acceptance.json")
    need(isinstance(cases, list) and cases, "supply independent acceptance cases")
    cases = [*cases, *inherited_cases]
    for limit in ("max_depth", "max_paths"):
        need(type(fixtures[limit]) is int and fixtures[limit] > 0, f"invalid {limit}")
    for b, opts in fixtures["events"].items():
        need(
            b in model.blocks
            and model.blocks[b]["kind"] == "wait"
            and isinstance(opts, list),
            f"unknown fixture block {b}",
        )
        for opt in opts:
            fields(opt, {"type", "data"}, set(), "event fixture")
            need(opt["type"] in model.blocks[b]["events"], "unknown fixture event")
    req = {
        "edges": {(r["node"], r["port"], r["next"]) for r in model.plan()},
        "entries": set(model.entries),
        "events": {
            (n, e)
            for n, node in model.nodes.items()
            for e in node["definition"].get("events", {})
        },
        "exits": {
            n for n, node in model.nodes.items() if node["definition"]["kind"] == "exit"
        },
    }
    observed = {k: set() for k in req}
    witnesses = {k: {} for k in req}
    probes = set()
    failures = []
    paths = []
    remaining = 0
    case_results = []
    independently_checked_entries = set()
    independently_checked_results = set()
    with tempfile.TemporaryDirectory(prefix="workflow-conformance-") as temp:
        base = Path(temp)
        src = base / "project"
        storage.snapshot(project, src)
        twin = project / "test_adapters.py"
        external = any(
            b.get("executor") in ("model", "tool") or b.get("effect", "pure") != "pure"
            for b in model.blocks.values()
        )
        need(
            not external or twin.is_file(),
            "provide a complete offline test_adapters.py for external/effectful tasks",
        )
        if twin.is_file():
            shutil.copyfile(twin, src / "adapters.py")
        queue = deque()
        for seed in fixtures["seeds"]:
            fields(seed, {"entry", "data"}, set(), "seed")
            queue.append((seed["entry"], seed["data"], []))
        expanded = set()
        while queue and len(paths) < fixtures["max_paths"]:
            entry, data, steps = queue.popleft()
            index = len(paths)
            root = base / f"generated-{index}"
            row = {
                "id": f"path-{index}",
                "entry": entry,
                "input": data,
                "steps": steps,
                "signals": [s["signal"] for s in steps],
            }
            paths.append(row)
            try:
                view = exercise(
                    src,
                    root,
                    entry,
                    data,
                    steps,
                    observed,
                    probes,
                    witnesses,
                    row["id"],
                )
                row["status"] = view["status"]
                row["node"] = view["node"]
                need(
                    view["status"] in ("waiting", "completed"),
                    f"unexpected runtime status {view}",
                )
                if view["status"] == "waiting":
                    key = (entry, view["node"], digest(view["data"]))
                    options = fixtures["events"].get(
                        model.nodes[view["node"]]["block"], []
                    )
                    if key not in expanded:
                        if len(steps) < fixtures["max_depth"]:
                            expanded.add(key)
                            for opt in options:
                                queue.append(
                                    (
                                        entry,
                                        data,
                                        [
                                            *steps,
                                            {
                                                "signal": opt["type"],
                                                "data": opt["data"],
                                            },
                                        ],
                                    )
                                )
                        else:
                            remaining += len(options)
            except Exception as exc:
                failures.append(f"generated path {index} {row}: {exc}")
        remaining += len(queue)
        generated = {k: len(v) for k, v in observed.items()}
        for i, case in enumerate(cases):
            try:
                fields(
                    case, {"name", "entry", "input", "steps"}, set(), "acceptance case"
                )
                need(
                    any(
                        "expect" in s
                        and set(s["expect"])
                        & {"data", "files", "result", "deliveries", "status", "node"}
                        for s in case["steps"]
                    ),
                    "case has no independent expected behavior",
                )
                final = exercise(
                    src,
                    base / f"oracle-{i}",
                    case["entry"],
                    case["input"],
                    case["steps"],
                    observed,
                    probes,
                    witnesses,
                    f"acceptance-{i}",
                )
                independently_checked_entries.add(case["entry"])
                if final["status"] == "completed" and any(
                    s.get("expect", {}).get("result") == final["result"]
                    for s in case["steps"]
                ):
                    independently_checked_results.add(final["result"])
                case_results.append({"name": case["name"], "passed": True})
            except Exception as exc:
                failures.append(f"acceptance {case.get('name', i)}: {exc}")
                case_results.append({"name": case.get("name", i), "passed": False})
    missing = {k: sorted(req[k] - observed[k]) for k in req}
    public_results = {
        model.nodes[node]["definition"]["result"] for node in req["exits"]
    }
    missing_acceptance = {
        "entries": sorted(req["entries"] - independently_checked_entries),
        "results": sorted(public_results - independently_checked_results),
    }
    obligations = [
        {"kind": kind, "requirement": item, "tests": witnesses[kind].get(item, [])}
        for kind, items in req.items()
        for item in sorted(items)
    ]
    return {
        "passed": not failures
        and not any(missing.values())
        and not any(missing_acceptance.values()),
        "missing_acceptance": missing_acceptance,
        "workflow": model.version,
        "obligations": obligations,
        "required": {k: len(v) for k, v in req.items()},
        "generated_coverage": generated,
        "missing": missing,
        "paths": paths,
        "unexpanded_prefixes": remaining,
        "probes": sorted(probes),
        "acceptance": case_results,
        "failures": failures,
        "seconds": time.monotonic() - started,
        "adapter_mode": "offline-double" if twin.is_file() else "local",
    }
