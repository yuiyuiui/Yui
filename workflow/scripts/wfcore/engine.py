"""Serialized state commits. The directory lock also orders independent CLI processes."""

import copy
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import storage
from .model import Model
from .protocol import (
    BLOB,
    ENVELOPE,
    REPLY,
    USAGE,
    Rejected,
    digest,
    encode,
    load,
    need,
    packet,
    receive,
    save,
    validate,
)


class Context:
    def __init__(self, root, run_id, node, activation, registry):
        self.root = root
        self.run_id = run_id
        self.node = node
        self.activation = activation
        self.registry = registry
        self.operation_id = f"{run_id}:{activation}:{node}"
        self.samples = []
        self._lock = threading.Lock()

    def transfer(self, source, target, event, contract, schema, data, suffix):
        msg = packet(
            self.run_id,
            self.operation_id + ":" + suffix,
            source,
            target,
            self.activation,
            event,
            contract,
            data,
        )
        return receive(msg, msg, schema, self.registry)

    def read_file(self, ref):
        ref = self.transfer(self.node, "storage", "read", "blob@1", BLOB, ref, "read")
        return storage.read_blob(self.root, ref)

    def put_file(self, data):
        ref = storage.store_blob(self.root, data)
        return self.transfer(
            "storage", self.node, "stored", "blob@1", BLOB, ref, "store"
        )

    def command(self, argv, *, timeout):
        return storage.command(self.root, argv, timeout, self.root / "work")

    def usage(self, *, input_tokens, output_tokens):
        info = {"input_tokens": input_tokens, "output_tokens": output_tokens}
        validate(USAGE, info, "adapter usage")
        with self._lock:
            self.samples.append(info)

    @property
    def cancelled(self):
        return (self.root / "work" / "cancel.request").exists()


def start(project, root, entry, data):
    project = Path(project).resolve()
    for source_dir in ("scripts", "blocks"):
        need(
            not root.resolve().is_relative_to(project / source_dir),
            "run directory overlaps application sources",
        )
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    with storage.lock(root):
        work = root / "work"
        work.mkdir()
        try:
            for n in ("blobs", "processes"):
                (work / n).mkdir()
            with storage.lock(project):
                storage.snapshot(project, work / "snapshot")
            model = Model(work / "snapshot")
            need(entry in model.entries, f"unknown entry {entry}")
            first = model.entries[entry]
            model.check(model.nodes[first]["definition"]["input"], data, "entry")
            run_id = uuid.uuid4().hex
            save(
                work / "owner.json",
                {"protocol": 1, "directory": storage.identity(root), "run": run_id},
            )
            ref = model.nodes[first]["definition"]["input"]
            inbound = packet(run_id, "entry", "entry", first, 1, entry, ref, data)
            receive(inbound, inbound, model.contracts[ref], model.registry)
            state = {
                "id": run_id,
                "workflow": model.version,
                "snapshot": storage.snapshot_id(work / "snapshot"),
                "entry_message": inbound,
                "controls": [],
                "started": time.time(),
                "entry": entry,
                "initial": data,
                "data": data,
                "node": first,
                "activation": 1,
                "visits": {first: 1},
                "status": "running",
                "error": None,
                "result": None,
                "events": {},
                "trace": [],
                "pending": None,
                "effect": None,
                "items": {},
                "timing": {},
                "usage": {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "unreported_model_calls": 0,
                },
            }
            save(work / "state.json", state)
        except BaseException:
            shutil.rmtree(work)
            root.rmdir()
            raise
        run = Run(root)
        return run.drive()


class Run:
    """Open and operate under storage.lock(root)."""

    def __init__(self, root, *, read_only=False):
        self.root = Path(root)
        self.work = self.root / "work"
        owned = storage.owner(self.root)
        self.path = self.work / "state.json"
        self.s = load(self.path)
        need(self.s["id"] == owned["run"], "foreign state")
        snap = self.work / "snapshot"
        need(
            storage.snapshot_id(snap) == self.s["snapshot"],
            "execution snapshot changed",
        )
        self.model = Model(snap)
        need(self.model.version == self.s["workflow"], "definition version changed")
        self.impl = None

    @property
    def block(self):
        return self.model.nodes[self.s["node"]]["definition"]

    def commit(self):
        save(self.path, self.s)

    def view(self):
        fields = (
            "status",
            "node",
            "activation",
            "result",
            "error",
            "data",
            "usage",
            "timing",
        )
        advice = {
            "uncertain": "reconcile",
            "paused": "inspect-and-resume",
            "waiting": "correct-input",
        }
        diag = (
            {
                "kind": self.s["status"],
                "node": self.s["node"],
                "activation": self.s["activation"],
                "message": self.s["error"],
                "next": advice.get(self.s["status"]),
            }
            if self.s["error"]
            else None
        )
        return {
            **{k: copy.deepcopy(self.s[k]) for k in fields},
            "diagnostic": diag,
            "run": self.s["id"],
            "operation": self.s["effect"],
            "deliveries": int(self.s["status"] == "completed"),
            "event_count": len(self.s["events"]),
            "events": self.block.get("events", {})
            if self.s["status"] == "waiting"
            else {},
        }

    def letter(self, typ, data, event_id):
        need(
            self.s["status"] == "waiting" and typ in self.block["events"],
            f"inactive event port {typ}",
        )
        port = self.block["events"][typ]
        return packet(
            self.s["id"],
            event_id,
            port["source"],
            self.s["node"],
            self.s["activation"],
            typ,
            port["contract"],
            data,
        )

    def signal(self, msg):
        validate(ENVELOPE, msg, "message")
        need(msg["run"] == self.s["id"], "message belongs to another run")
        previous = self.s["events"].get(msg["id"])
        if previous is not None:
            need(previous == digest(msg), "message ID reused for different content")
            prior = self.model.nodes[msg["target"]]["definition"]
            if prior.get("on_duplicate") == "reject":
                raise Rejected("duplicate message already processed")
            return self.view()
        pending = self.s["pending"]
        if pending and pending["id"] == msg["id"]:
            need(pending == msg, "message ID reused for different content")
            return self.resume() if self.s["status"] == "running" else self.view()
        need(self.s["status"] == "waiting", "run is not accepting events")
        expected = self.letter(msg["type"], msg["data"], msg["id"])
        receive(
            msg,
            expected,
            self.model.contracts[expected["contract"]],
            self.model.registry,
        )
        self.s.update(pending=msg, status="running", error=None)
        self.commit()
        return self.drive()

    def control(self, event, data, schema):
        msg = packet(
            self.s["id"],
            f"control-{len(self.s['controls']) + 1}",
            "operator",
            self.s["node"],
            self.s["activation"],
            event,
            event + "@1",
            data,
        )
        receive(msg, msg, schema)
        self.s["controls"].append(msg)

    def attach(self, data):
        need(self.s["status"] == "waiting", "attachments require an active wait")
        ctx = Context(
            self.root,
            self.s["id"],
            self.s["node"],
            self.s["activation"],
            self.model.registry,
        )
        return ctx.put_file(data)

    def _adapter(self, name):
        if self.impl is None:
            self.impl = storage.adapters(self.work / "snapshot")
        fn = getattr(self.impl, name, None)
        need(callable(fn), f"missing adapter {name}")
        return fn

    def _gather(self, jobs, workers):
        done = self.s["items"]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            queued = {
                pool.submit(fn, *args): key
                for key, (fn, args) in jobs.items()
                if key not in done
            }
            errors = []
            for job in as_completed(queued):
                key = queued[job]
                try:
                    value = job.result()
                    encode(value)
                    done[key] = value
                    self.commit()
                except Exception as exc:
                    errors.append(f"item {key}: {exc}")
            need(not errors, "; ".join(errors))
        return done

    def _fork(self, b, ctx):
        def execute(lane, child, handler):
            ref = child["input"]
            data = ctx.transfer(
                ctx.node,
                lane,
                "dispatch",
                ref,
                self.model.contracts[ref],
                copy.deepcopy(self.s["data"]),
                lane + ":dispatch",
            )
            reply = handler(ctx, data)
            validate(REPLY, reply, lane)
            need(reply["port"] in child["outputs"], f"{lane}: unknown output port")
            out = child["outputs"][reply["port"]]
            return ctx.transfer(
                lane,
                ctx.node,
                reply["port"],
                out,
                self.model.contracts[out],
                reply["data"],
                lane + ":return",
            )

        jobs = {
            lane: (
                execute,
                (
                    lane,
                    self.model.blocks[name],
                    self._adapter(self.model.blocks[name]["handler"]),
                ),
            )
            for lane, name in b["branches"].items()
        }
        done = self._gather(jobs, b["workers"])
        return self._adapter(b["handler"])(
            ctx, copy.deepcopy(self.s["data"]), {key: done[key] for key in jobs}
        )

    def _map(self, b, ctx):
        inputs = (
            self.s["data"].get(b["field"]) if isinstance(self.s["data"], dict) else None
        )
        need(isinstance(inputs, list), f"map requires an array at {b['field']}")
        for i, item in enumerate(inputs):
            ctx.transfer(
                ctx.node,
                f"{ctx.node}/item/{i}",
                "dispatch",
                b["item_input"],
                self.model.contracts[b["item_input"]],
                item,
                f"item:{i}:dispatch",
            )
        worker = self._adapter(b["worker"])

        def execute(idx, item):
            value = worker(ctx, copy.deepcopy(item))
            return ctx.transfer(
                f"{ctx.node}/item/{idx}",
                ctx.node,
                "return",
                b["item_output"],
                self.model.contracts[b["item_output"]],
                value,
                f"item:{idx}:return",
            )

        done = self._gather(
            {str(i): (execute, (i, item)) for i, item in enumerate(inputs)},
            b["workers"],
        )
        rows = [done[str(i)] for i in range(len(inputs))]
        return self._adapter(b["handler"])(ctx, copy.deepcopy(self.s["data"]), rows)

    def _advance(self, reply, msg=None):
        validate(REPLY, reply, "adapter outcome")
        encode(reply)
        n = self.s["node"]
        port = reply["port"]
        need(port in self.model.edges[n], f"{n}: unknown outcome {port}")
        dest = self.model.edges[n][port]
        ref = self.model.nodes[dest]["definition"]["input"]
        msg_out = packet(
            self.s["id"],
            f"transition-{self.s['activation']}",
            n,
            dest,
            self.s["activation"] + 1,
            port,
            ref,
            reply["data"],
        )
        receive(msg_out, msg_out, self.model.contracts[ref], self.model.registry)
        row = {
            "message": msg_out,
            "node": n,
            "activation": self.s["activation"],
            "port": port,
            "next": dest,
            "contract": ref,
            "input": self.s["data"],
            "data": reply["data"],
            "event": msg,
        }
        self.s["trace"].append(row)
        if msg:
            self.s["events"][msg["id"]] = digest(msg)
        self.s.update(
            node=dest,
            activation=self.s["activation"] + 1,
            data=reply["data"],
            pending=None,
            status="running",
            error=None,
            effect=None,
            items={},
        )
        self.s["visits"][dest] = self.s["visits"].get(dest, 0) + 1

    def _stop(self, status, error):
        self.s.update(status=status, error=str(error))
        self.commit()
        return self.view()

    def cancel(self):
        if self.s["status"] in ("cancelled", "completed"):
            return self.view()
        self.control("cancel", {}, {"type": "object", "maxProperties": 0})
        # A crash after the atomic delivery rename must retain the completed outcome.
        if (self.root / "delivery").exists():
            row = storage.verify_delivery(self.root)
            need(row["run"] == self.s["id"], "foreign delivery")
            self.s.update(status=row["status"], result=row["result"], error=None)
        else:
            storage.publish(
                self.root, self.s, self.model, "cancelled", {}, cancelled=True
            )
            self.s.update(status="cancelled", result="cancelled", error=None)
        self.commit()
        return self.view()

    def resume(self):
        if self.s["status"] in ("completed", "cancelled", "waiting", "uncertain"):
            return self.view()
        self.control("resume", {}, {"type": "object", "maxProperties": 0})
        return self.drive()

    def settle(self, operation, reply):
        need(
            self.s["status"] == "uncertain" and operation == self.s["effect"],
            "no matching uncertain operation",
        )
        self.control("settle", reply, REPLY)
        self._advance(reply)
        self.commit()
        return self.drive()

    def drive(self):
        self.s.update(status="running", error=None)
        self.commit()
        while True:
            if (self.work / "cancel.request").exists():
                return self.cancel()
            n = self.s["node"]
            b = self.block
            kind = b["kind"]
            limit = self.model.nodes[n].get("max_visits")
            if limit and self.s["visits"][n] > limit:
                return self._stop("paused", f"{n}: visit budget {limit} reached")
            if kind == "wait" and self.s["pending"] is None:
                self.s.update(status="waiting", error=None)
                self.commit()
                return self.view()
            operation = f"{self.s['id']}:{self.s['activation']}:{n}"
            if self.s["effect"] and b.get("effect") == "reconcile":
                return self._stop(
                    "uncertain",
                    "inspect the external operation before supplying a receipt",
                )
            if b.get("effect") in ("idempotent", "reconcile"):
                self.s["effect"] = operation
            if b.get("executor") == "model":
                self.s["usage"]["unreported_model_calls"] += 1
            if self.s["effect"] or b.get("executor") == "model":
                self.commit()
            ctx = Context(
                self.root, self.s["id"], n, self.s["activation"], self.model.registry
            )
            started = time.monotonic()
            terminal = False
            error = None
            rejected = False
            try:
                msg = self.s["pending"]
                if kind == "exit":
                    storage.publish(
                        self.root, self.s, self.model, b["result"], b.get("files", {})
                    )
                    self.s.update(status="completed", result=b["result"], error=None)
                    terminal = True
                else:
                    if kind == "wait":
                        reply = self._adapter(b["handler"])(
                            ctx, copy.deepcopy(self.s["data"]), copy.deepcopy(msg)
                        )
                    elif kind == "task":
                        reply = self._adapter(b["handler"])(
                            ctx, copy.deepcopy(self.s["data"])
                        )
                    elif kind == "map":
                        reply = self._map(b, ctx)
                    elif kind == "fork":
                        reply = self._fork(b, ctx)
                    else:
                        reply = {"port": "enter", "data": self.s["data"]}
                    if ctx.cancelled:
                        return self.cancel()
                    self._advance(reply, msg)
            except Rejected as exc:
                error = str(exc)
                rejected = kind == "wait"
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            finally:
                timing = self.s["timing"].setdefault(n, {"calls": 0, "seconds": 0.0})
                timing["calls"] += 1
                timing["seconds"] += time.monotonic() - started
                for sample in ctx.samples:
                    for key, val in sample.items():
                        self.s["usage"][key] += val
                if b.get("executor") == "model" and ctx.samples:
                    self.s["usage"]["unreported_model_calls"] -= 1
            if ctx.cancelled:
                return self.cancel()
            if error is not None:
                if rejected:
                    self.s.update(pending=None, status="waiting", error=error)
                    self.commit()
                    raise Rejected(error)
                status = "uncertain" if b.get("effect") == "reconcile" else "paused"
                return self._stop(status, error)
            self.commit()
            if terminal:
                return self.view()


def replay(state, model):
    node = model.entries.get(state["entry"])
    data = state["initial"]
    need(node is not None, "entry no longer exists")
    initial_ref = model.nodes[node]["definition"]["input"]
    initial = packet(
        state["id"], "entry", "entry", node, 1, state["entry"], initial_ref, data
    )
    receive(
        state["entry_message"], initial, model.contracts[initial_ref], model.registry
    )
    need(state["entry_message"] == initial, "entry payload or identity changed")
    for idx, row in enumerate(state["trace"], 1):
        need(
            node == row["node"] and row["activation"] == idx and row["input"] == data,
            f"replay {idx}: input mismatch",
        )
        b = model.nodes[node]["definition"]
        model.check(b["input"], data, node)
        msg = row["event"]
        if msg is not None:
            validate(ENVELOPE, msg, "replayed message")
            event = b.get("events", {}).get(msg["type"])
            need(
                msg["run"] == state["id"]
                and msg["target"] == node
                and msg["activation"] == idx
                and event == {"source": msg["source"], "contract": msg["contract"]},
                "event contract changed",
            )
            model.check(msg["contract"], msg["data"], node)
        dest = model.edges[node].get(row["port"])
        need(
            dest == row["next"], f"replay {idx}: route changed at {node}.{row['port']}"
        )
        ref = model.nodes[dest]["definition"]["input"]
        need(ref == row["contract"], "receiver contract version changed")
        data = row["data"]
        expected = packet(
            state["id"],
            f"transition-{idx}",
            node,
            dest,
            idx + 1,
            row["port"],
            ref,
            data,
        )
        receive(row["message"], expected, model.contracts[ref], model.registry)
        need(row["message"] == expected, "transition payload or identity changed")
        node = dest
    need(node == state["node"] and data == state["data"], "final checkpoint mismatch")
    end = model.nodes[node]["definition"]
    model.check(end["input"], data, "final checkpoint")
    if state["status"] == "completed":
        need(
            end["kind"] == "exit" and end["result"] == state["result"],
            "terminal result changed",
        )
    return {"transitions": len(state["trace"]), "node": node, "status": state["status"]}
