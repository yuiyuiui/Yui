"""Run ownership, private snapshots, immutable blobs and verifiable deliveries."""

import contextlib
import fcntl
import hashlib
import importlib.util
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

from .protocol import (
    BLOB,
    TEXT,
    checked_schema,
    digest,
    durable,
    filename,
    load,
    need,
    object_shape,
    packet,
    receive,
    save,
    schema_registry,
    validate,
)

DELIVERY = object_shape(
    {
        "result": TEXT,
        "result_digest": {
            "type": "string",
            "pattern": BLOB["properties"]["sha256"]["pattern"],
        },
    }
)


def owned_dir(path):
    return path.is_dir() and not path.is_symlink()


@contextlib.contextmanager
def lock(root):
    need(owned_dir(root), f"run directory unavailable: {root}")
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def identity(root):
    st = root.stat()
    return [st.st_dev, st.st_ino]


def owner(root):
    need(owned_dir(root), "unsafe run directory")
    work = root / "work"
    need(
        owned_dir(work)
        and (work / "owner.json").is_file()
        and not (work / "owner.json").is_symlink(),
        "no owned live workspace",
    )
    row = load(work / "owner.json")
    need(
        row.get("protocol") == 1 and row.get("directory") == identity(root),
        "workspace ownership mismatch",
    )
    for d in ("blobs", "processes", "snapshot"):
        need(owned_dir(work / d), f"unsafe workspace directory {d}")
    return row


def snapshot(src, dest):
    dest.mkdir()
    for name in ("workflow.json", "adapters.py", "scripts", "blocks"):
        p = src / name
        if not p.exists() and name in ("blocks", "adapters.py"):
            continue
        need(not p.is_symlink(), f"snapshot cannot follow symlink: {name}")
        if p.is_dir():
            for child in p.rglob("*"):
                need(not child.is_symlink(), f"snapshot cannot follow symlink: {child}")
            shutil.copytree(
                p, dest / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
            )
        else:
            shutil.copyfile(p, dest / name)


def snapshot_id(root):
    hashes = {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts
    }
    return digest(hashes)


def adapters(root):
    path = root / "adapters.py"
    if not path.exists():
        return None
    # Relative imports from .blocks are resolved against this specific snapshot.
    key = "_workflow_" + uuid.uuid4().hex
    spec = importlib.util.spec_from_file_location(
        key, path, submodule_search_locations=[str(root)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(key, None)
        raise
    return module


def store_blob(root, data):
    h = hashlib.sha256(data).hexdigest()
    p = root / "work" / "blobs" / h
    if not p.exists():
        durable(p, data)
    ref = {"sha256": h, "size": len(data)}
    read_blob(root, ref)
    return ref


def read_blob(root, ref):
    validate(BLOB, ref, "file")
    p = root / "work" / "blobs" / ref["sha256"]
    need(p.is_file() and not p.is_symlink(), "referenced attachment has not arrived")
    data = p.read_bytes()
    need(
        len(data) == ref["size"] and hashlib.sha256(data).hexdigest() == ref["sha256"],
        "blob verification failed",
    )
    return data


def verify_delivery(root):
    folder = root / "delivery"
    receipt = folder / "receipt.json"
    need(
        owned_dir(folder) and receipt.is_file() and not receipt.is_symlink(),
        "missing delivery receipt",
    )
    row = load(receipt)
    need(row.get("format") == "workflow-delivery/1", "unrecognized delivery")
    need(row.get("status") in ("completed", "cancelled"), "invalid delivery status")
    handoff = row["handoff"]
    expected = packet(
        row["run"],
        "delivery",
        row["node"],
        "delivery",
        row["activation"],
        row["status"],
        "delivery@1",
        {"result": row["result"], "result_digest": row["result_digest"]},
    )
    receive(handoff, expected, DELIVERY)
    need(handoff == expected, "delivery envelope differs from receipt")
    expected = {"receipt.json", "result.json"}
    for name in row["files"]:
        filename(name)
        expected.add(name)
    need(
        {p.name for p in folder.iterdir()} == expected,
        "delivery file set differs from receipt",
    )
    for name in expected - {"receipt.json"}:
        p = folder / name
        need(p.is_file() and not p.is_symlink(), f"unsafe delivery member {name}")
    data = load(folder / "result.json")
    need(digest(data) == row["result_digest"], "result digest mismatch")
    contracts = row["schema_dependencies"]
    for name, member in contracts.items():
        checked_schema(member, name, contracts)
    checked_schema(row["schema"], "delivered schema", contracts)
    validate(row["schema"], data, "delivered result", schema_registry(contracts))
    for name, ref in row["files"].items():
        validate(BLOB, ref, name)
        raw = (folder / name).read_bytes()
        need(
            len(raw) == ref["size"]
            and hashlib.sha256(raw).hexdigest() == ref["sha256"],
            f"changed delivery {name}",
        )
    return row


def publish(root, state, model, result, files, *, cancelled=False):
    started = time.monotonic()
    folder = root / "delivery"
    data = None if cancelled else state["data"]
    schema = (
        {"type": "null"}
        if cancelled
        else model.contracts[model.nodes[state["node"]]["definition"]["input"]]
    )
    refs = {name: data[field] for name, field in files.items()}
    if folder.exists():
        row = verify_delivery(root)
        need(
            row["run"] == state["id"]
            and row["result"] == result
            and row["result_digest"] == digest(data)
            and row["files"] == refs
            and row["workflow"] == state["workflow"],
            "another delivery already exists",
        )
        return row
    stage = Path(tempfile.mkdtemp(prefix="delivery-", dir=root / "work"))
    try:
        for name, ref in refs.items():
            durable(stage / name, read_blob(root, ref))
        save(stage / "result.json", data)
        usage = state["usage"]
        timing = {k: dict(v) for k, v in state["timing"].items()}
        if not cancelled:
            last = timing.setdefault(state["node"], {"calls": 0, "seconds": 0.0})
            last["calls"] += 1
            last["seconds"] += time.monotonic() - started
        row = {
            "format": "workflow-delivery/1",
            "run": state["id"],
            "workflow": state["workflow"],
            "snapshot": state["snapshot"],
            "status": "cancelled" if cancelled else "completed",
            "result": result,
            "result_digest": digest(data),
            "schema": schema,
            "files": refs,
            "elapsed_seconds": time.time() - state["started"],
            "usage": usage,
            "timing": timing,
            "unresolved_operation": state["effect"] if cancelled else None,
        }
        row["schema_dependencies"] = (
            {}
            if cancelled
            else model.schema_dependencies(
                model.nodes[state["node"]]["definition"]["input"]
            )
        )
        row["node"] = state["node"]
        row["activation"] = state["activation"]
        row["handoff"] = packet(
            state["id"],
            "delivery",
            state["node"],
            "delivery",
            state["activation"],
            row["status"],
            "delivery@1",
            {"result": result, "result_digest": row["result_digest"]},
        )
        receive(row["handoff"], row["handoff"], DELIVERY)
        save(stage / "receipt.json", row)
        os.rename(stage, folder)
        return verify_delivery(root)
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def proc_identity(pid):
    p = subprocess.run(
        ["ps", "-p", str(pid), "-o", "lstart="], capture_output=True, text=True
    )
    return p.stdout.strip() if p.returncode == 0 else ""


def reap(root):
    for p in (root / "work" / "processes").glob("*.json"):
        need(not p.is_symlink(), "unsafe process record")
        rec = load(p)
        pid = rec["pid"]
        need(type(pid) is int and pid > 1 and rec["start"], "invalid process record")
        if proc_identity(pid) == rec["start"]:
            try:
                need(os.getpgid(pid) == pid, "registered process group changed")
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        p.unlink(missing_ok=True)


def command(root, argv, timeout, cwd):
    """The child cannot start the requested tool before its identity is registered."""
    need(
        isinstance(argv, list) and argv and all(isinstance(s, str) for s in argv),
        "argv required",
    )
    need(timeout > 0, "positive tool timeout required")
    gate = "import os,sys; permit=sys.stdin.buffer.read(1); permit==b'G' and os.execvp(sys.argv[1],sys.argv[1:])"
    with subprocess.Popen(
        [sys.executable, "-c", gate, *argv],
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    ) as proc:
        record = root / "work" / "processes" / (uuid.uuid4().hex + ".json")
        try:
            start = proc_identity(proc.pid)
            need(start, "could not identify new tool process")
            save(record, {"pid": proc.pid, "start": start})
            proc.stdin.write(b"G")
            proc.stdin.close()
            proc.stdin = None
            end = time.monotonic() + timeout
            while True:
                need(not (root / "work" / "cancel.request").exists(), "cancelled")
                remaining = end - time.monotonic()
                need(remaining > 0, "tool timed out")
                try:
                    stdout, stderr = proc.communicate(timeout=min(0.2, remaining))
                    need(
                        proc.returncode == 0,
                        f"tool exited {proc.returncode}: {stderr.decode(errors='replace')[:800]}",
                    )
                    return stdout
                except subprocess.TimeoutExpired:
                    continue
        finally:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
            record.unlink(missing_ok=True)
