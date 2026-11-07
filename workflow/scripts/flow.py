#!/usr/bin/env python3
"""Standalone generated-workflow entry. Run with --help for the protocol commands."""

import argparse
import json
import runpy
import shutil
import sys
from pathlib import Path

# Loading a pinned execution snapshot must leave its files untouched.
# ruff: noqa: E402
sys.dont_write_bytecode = True
from wfcore import storage
from wfcore.conformance import verify
from wfcore.engine import Run, replay, start
from wfcore.model import Model
from wfcore.protocol import Fault, load, need, parse

ROOT = Path(__file__).resolve().parent.parent


def argument(value):
    return load(value[1:]) if value.startswith("@") else parse(value)


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest="cmd", required=True)
    for name in ("check", "plan", "test", "diagram"):
        commands.add_parser(name)
    audit_cmd = commands.add_parser("audit")
    audit_cmd.add_argument("--baseline", type=Path)
    audit_cmd.add_argument("--baseline-ref")
    audit_cmd.add_argument("--require-baseline", action="store_true")
    audit_cmd.add_argument("--record", action="store_true")
    audit_cmd.add_argument("--history-run", action="append", default=[])
    for name in (
        "start",
        "status",
        "resume",
        "cancel",
        "clean",
        "message",
        "signal",
        "attach",
        "settle",
        "replay",
        "delivery",
        "history",
    ):
        p = commands.add_parser(name)
        p.add_argument("run", type=Path)
        if name == "start":
            p.add_argument("entry")
            p.add_argument("data", type=argument)
        if name == "message":
            p.add_argument("type")
            p.add_argument("data", type=argument)
            p.add_argument("--id", required=True)
        if name == "signal":
            p.add_argument("envelope", type=argument)
        if name == "attach":
            p.add_argument("file", type=Path)
        if name == "settle":
            p.add_argument("operation")
            p.add_argument("reply", type=argument)
        if name == "replay":
            p.add_argument("--against", type=Path)
    return cli


def call(args):
    cmd = args.cmd
    if cmd in ("check", "plan", "diagram"):
        m = Model(ROOT)
        impl = storage.adapters(ROOT)
        for name, b in m.blocks.items():
            for field in ("handler", "worker"):
                if field in b:
                    need(
                        callable(getattr(impl, b[field], None)),
                        f"{name}: missing {field} {b[field]}",
                    )
        if cmd == "diagram":
            index = {name: f"n{i}" for i, name in enumerate(m.nodes)}
            rows = ["flowchart TD"]
            for name, node in m.nodes.items():
                rows.append(f'  {index[name]}["{name} ({node["definition"]["kind"]})"]')
            for edge in m.plan():
                rows.append(
                    f"  {index[edge['node']]} -->|{edge['port']}| {index[edge['next']]}"
                )
            return "\n".join(rows)
        return (
            m.plan()
            if cmd == "plan"
            else {"valid": True, "version": m.version, "entries": m.entries}
        )
    if cmd == "test":
        return verify(ROOT)
    if cmd == "audit":
        from wfcore.maintenance import audit

        return audit(
            ROOT,
            ROOT,
            baseline=args.baseline,
            baseline_ref=args.baseline_ref,
            record=args.record,
            require_baseline=args.require_baseline,
            runs=args.history_run,
        )
    root = args.run.absolute()
    if cmd == "start":
        return start(ROOT, root, args.entry, args.data)
    if cmd == "delivery":
        return storage.verify_delivery(root)
    if cmd in ("status", "history") and (root / "work").exists():
        try:
            run = Run(root, read_only=True)
            return run.view() if cmd == "status" else run.s["trace"]
        except (FileNotFoundError, Fault):
            if (root / "work").exists():
                raise
    if cmd in ("cancel", "clean") and (root / "work").exists():
        try:
            storage.owner(root)
            (root / "work" / "cancel.request").touch(exist_ok=True)
        except (FileNotFoundError, Fault):
            if (root / "work").exists():
                raise
    with storage.lock(root):
        if not (root / "work").exists() and cmd in (
            "clean",
            "status",
            "cancel",
            "resume",
        ):
            receipt = storage.verify_delivery(root)
            return {
                "status": receipt["status"],
                "result": receipt["result"],
                "cleaned": True,
                "run": receipt["run"],
            }
        storage.owner(root)
        pinned = root / "work" / "snapshot" / "scripts" / "flow.py"
        if pinned.resolve() != Path(__file__).resolve():
            info = load(root / "work" / "state.json")
            need(
                info["snapshot"] == storage.snapshot_id(pinned.parent.parent),
                "runtime snapshot changed",
            )
            # The lock stays held across the handoff, including concurrent clean.
            sys.path.insert(0, str(pinned.parent))
            for name in list(sys.modules):
                if name == "wfcore" or name.startswith("wfcore."):
                    del sys.modules[name]
            return runpy.run_path(str(pinned))["operate"](args, root)
        return operate(args, root)


def operate(args, root):
    cmd = args.cmd
    r = Run(root)
    if cmd == "resume":
        storage.reap(root)
        return r.resume()
    if cmd == "message":
        return r.letter(args.type, args.data, args.id)
    if cmd == "signal":
        return r.signal(args.envelope)
    if cmd == "attach":
        return r.attach(args.file.read_bytes())
    if cmd == "settle":
        return r.settle(args.operation, args.reply)
    if cmd == "replay":
        return replay(r.s, Model(args.against) if args.against else r.model)
    if cmd in ("cancel", "clean"):
        storage.reap(root)
        result = r.cancel()
        if cmd == "clean":
            receipt = storage.verify_delivery(root)
            need(r.s["id"] == receipt["run"], "delivery ownership mismatch")
            shutil.rmtree(root / "work")
            return {"cleaned": True, "result": receipt["result"], "run": r.s["id"]}
        return result
    raise Fault(f"unknown command {cmd}")


def main():
    try:
        result = call(parser().parse_args())
        print(
            result
            if isinstance(result, str)
            else json.dumps(result, ensure_ascii=False, sort_keys=True)
        )
        return int(isinstance(result, dict) and result.get("passed") is False)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
