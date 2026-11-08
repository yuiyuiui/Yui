"""Validate a workflow and resolve nested flows into typed, executable links."""

import re
from pathlib import Path

from . import content
from .protocol import (
    BLOB,
    CONTRACT,
    PORT,
    checked_schema,
    digest,
    fields,
    filename,
    load,
    need,
    schema_registry,
    symbol,
    validate,
)


class Model:
    def __init__(self, root):
        self.root = Path(root)
        spec = load(self.root / "workflow.json")
        fields(
            spec,
            {"protocol", "name", "description", "contracts", "blocks", "flows"},
            set(),
            "workflow",
        )
        need(
            type(spec["protocol"]) is int and spec["protocol"] == 1,
            "unsupported protocol",
        )
        need(
            isinstance(spec["name"], str)
            and re.fullmatch(r"[a-z][a-z0-9-]{0,63}", spec["name"]),
            "workflow skill name must contain 1-64 lowercase letters, digits or hyphens",
        )
        need(
            isinstance(spec["description"], str) and spec["description"].strip(),
            "missing description",
        )
        self.spec = spec
        self.version = digest(spec)
        self.contracts = spec["contracts"]
        self.blocks = spec["blocks"]
        flows = spec["flows"]
        for group in (self.contracts, self.blocks, flows):
            need(
                isinstance(group, dict) and group,
                "contracts, blocks and flows must be nonempty maps",
            )
        need(
            "blob@1" not in self.contracts,
            "blob@1 is the built-in file reference contract",
        )
        self.contracts = {**self.contracts, "blob@1": BLOB}
        self.dependencies = {}
        for key, schema in self.contracts.items():
            need(CONTRACT.fullmatch(key), f"contract {key}: expected name@version")
            self.dependencies[key] = checked_schema(schema, key, self.contracts)
        self.registry = schema_registry(self.contracts)
        for key, block in self.blocks.items():
            symbol(key, "block")
            self._block(key, block)
        need("main" in flows, "main flow missing")
        for name, flow in flows.items():
            symbol(name, "flow")
            fields(flow, {"entries", "nodes"}, set(), name)
            for group in (flow["entries"], flow["nodes"]):
                need(
                    isinstance(group, dict) and group,
                    f"{name}: empty/invalid entries or nodes",
                )
            for entry, node in flow["entries"].items():
                symbol(entry, name)
                need(
                    isinstance(node, str) and node in flow["nodes"],
                    f"{name}.{entry}: unknown entry {node}",
                )
            for node, value in flow["nodes"].items():
                symbol(node, name)
                fields(value, {"block", "on"}, {"max_visits"}, f"{name}.{node}")
                block = self.blocks.get(value["block"])
                need(block is not None, f"{name}.{node}: unknown block")
                need(
                    isinstance(value["on"], dict)
                    and value["on"].keys() == block.get("outputs", {}).keys(),
                    f"{name}.{node}: every declared outcome needs exactly one route",
                )
                if "max_visits" in value:
                    need(
                        type(value["max_visits"]) is int and value["max_visits"] > 0,
                        f"{node}: invalid visit budget",
                    )
        self.nodes = {}
        self.edges = {}
        self.used_flows = set()

        def expand(flow_id, prefix, parents, returns):
            need(
                flow_id in flows and flow_id not in parents,
                f"missing or recursive subflow {flow_id}",
            )
            self.used_flows.add(flow_id)
            flow = flows[flow_id]

            def entrance(local):
                node = flow["nodes"][local]
                block = self.blocks[node["block"]]
                return (
                    prefix + local
                    if block["kind"] != "subflow"
                    else prefix + local + "/@enter"
                )

            for local, node in flow["nodes"].items():
                block = self.blocks[node["block"]]
                name = entrance(local)
                routes = {}
                for port, dest in node["on"].items():
                    need(
                        isinstance(dest, str),
                        f"{name}.{port}: string destination required",
                    )
                    schema = block["outputs"][port]
                    if dest.startswith("^"):
                        ret = dest[1:]
                        need(
                            ret in returns and returns[ret][0] == schema,
                            f"{name}.{port}: invalid return {dest}",
                        )
                        routes[port] = returns[ret][1]
                    else:
                        need(
                            dest in flow["nodes"],
                            f"{name}.{port}: unknown destination {dest}",
                        )
                        consumer = self.blocks[flow["nodes"][dest]["block"]]
                        need(
                            consumer["input"] == schema,
                            f"{name}.{port} -> {dest}: {schema} != {consumer['input']}",
                        )
                        routes[port] = entrance(dest)
                self.nodes[name] = {**node, "definition": block}
                if block["kind"] == "subflow":
                    sub = block["flow"]
                    need(
                        sub in flows and set(flows[sub]["entries"]) == {"start"},
                        f"{name}: subflow needs start entry",
                    )
                    start = flows[sub]["entries"]["start"]
                    boundary = self.blocks[flows[sub]["nodes"][start]["block"]]
                    need(
                        block["input"] == boundary["input"],
                        f"{name}: subflow input mismatch",
                    )
                    child_returns = {
                        p: (block["outputs"][p], d) for p, d in routes.items()
                    }
                    child_entries = expand(
                        sub, prefix + local + "/", parents + (flow_id,), child_returns
                    )
                    used = {
                        d[1:]
                        for n in flows[sub]["nodes"].values()
                        for d in n["on"].values()
                        if d.startswith("^")
                    }
                    need(
                        used == set(child_returns),
                        f"{name}: undelivered subflow return",
                    )
                    self.edges[name] = {"enter": child_entries["start"]}
                else:
                    need(
                        not (parents and block["kind"] == "exit"),
                        f"{name}: exit bypasses subflow returns",
                    )
                    self.edges[name] = routes
            return {e: entrance(n) for e, n in flow["entries"].items()}

        self.entries = expand("main", "", (), {})
        need(self.used_flows == flows.keys(), "unreferenced flow definitions")
        self._topology()
        content.check_routes(self)

    def _block(self, name, b):
        need(isinstance(b, dict), f"{name}: block object required")
        kind = b.get("kind")
        specific = {
            "task": {"handler", "executor"},
            "wait": {"handler", "events"},
            "map": {
                "field",
                "worker",
                "item_input",
                "item_output",
                "handler",
                "workers",
            },
            "fork": {"branches", "handler", "workers"},
            "exit": {"result"},
            "subflow": {"flow"},
        }
        need(kind in specific, f"{name}: invalid block kind {kind!r}")
        required = {"kind", "input"} | specific[kind]
        if kind != "exit":
            required.add("outputs")
        optional = {
            "exit": {"files"},
            "task": {"effect"},
            "wait": {"on_duplicate"},
        }.get(kind, set())
        if kind in {"task", "wait", "map", "fork"}:
            optional = optional | {"content"}
        fields(b, required, optional, name)

        def contract(ref):
            need(
                isinstance(ref, str) and ref in self.contracts,
                f"{name}: unknown contract {ref!r}",
            )

        contract(b["input"])
        if kind != "exit":
            need(
                isinstance(b["outputs"], dict) and b["outputs"],
                f"{name}: outputs required",
            )
            for port, ref in b["outputs"].items():
                symbol(port, name)
                contract(ref)
        if "content" in b:
            content.declarations(b, name)
        if kind in {"task", "wait", "map", "fork"}:
            for field in ("handler", "worker"):
                if field in b:
                    need(
                        isinstance(b[field], str)
                        and b[field].isidentifier()
                        and not b[field].startswith("_"),
                        f"{name}: invalid adapter {field}",
                    )
        if kind == "wait":
            need(
                b.get("on_duplicate", "acknowledge") in ("acknowledge", "reject"),
                f"{name}: invalid duplicate policy",
            )
            need(
                isinstance(b["events"], dict) and b["events"],
                f"{name}: no accepted events",
            )
            for event, port in b["events"].items():
                symbol(event, name)
                validate(PORT, port, f"{name}.{event}")
                contract(port["contract"])
        if kind == "map":
            contract(b["item_input"])
            contract(b["item_output"])
            need(
                isinstance(b["field"], str) and b["field"],
                f"{name}: expected array field",
            )
        if kind == "fork":
            need(
                isinstance(b["branches"], dict) and b["branches"],
                f"{name}: fork needs named branches",
            )
            for lane, child_id in b["branches"].items():
                symbol(lane, name)
                child = self.blocks.get(child_id)
                need(
                    isinstance(child, dict)
                    and child.get("kind") == "task"
                    and child.get("executor") == "python"
                    and child.get("effect", "pure") == "pure"
                    and "content" not in child
                    and child.get("input") == b["input"]
                    and isinstance(child.get("outputs"), dict)
                    and len(child["outputs"]) == 1,
                    f"{name}.{lane}: use a pure single-outcome task with the same input contract",
                )
        if kind in ("fork", "map"):
            need(
                type(b["workers"]) is int and b["workers"] > 0,
                f"{name}: workers must be positive",
            )
        if kind == "task":
            need(b["executor"] in ("python", "model", "tool"), f"{name}: bad executor")
            need(
                b.get("effect", "pure") in ("pure", "idempotent", "reconcile"),
                f"{name}: bad effect policy",
            )
        if kind == "exit":
            symbol(b["result"], name)
            need(isinstance(b.get("files", {}), dict), f"{name}: invalid files")
            for key, field in b.get("files", {}).items():
                filename(key)
                need(
                    isinstance(field, str) and field, f"{name}: invalid file reference"
                )

    def _topology(self):
        def reach(starts, graph):
            seen = set()
            stack = list(starts)
            while stack:
                node = stack.pop()
                if node not in seen:
                    seen.add(node)
                    stack.extend(graph[node])
            return seen

        graph = {n: set(r.values()) for n, r in self.edges.items()}
        need(
            reach(self.entries.values(), graph) == graph.keys(),
            "unreachable node(s): "
            + ", ".join(sorted(graph.keys() - reach(self.entries.values(), graph))),
        )
        reverse = {n: [] for n in graph}
        for n, dests in graph.items():
            for d in dests:
                reverse[d].append(n)
        exits = [n for n, v in self.nodes.items() if v["definition"]["kind"] == "exit"]
        need(
            reach(exits, reverse) == graph.keys(), "some nodes have no path to an exit"
        )
        done, visiting = set(), set()

        def check(n):
            if (
                n in done
                or self.nodes[n]["definition"]["kind"] == "wait"
                or "max_visits" in self.nodes[n]
            ):
                return
            need(n not in visiting, f"{n}: automatic cycle needs a visit bound or wait")
            visiting.add(n)
            for d in graph[n]:
                check(d)
            visiting.remove(n)
            done.add(n)

        for n in graph:
            check(n)

    def check(self, ref, data, where):
        validate(self.contracts[ref], data, f"{where} ({ref})", self.registry)

    def schema_dependencies(self, ref):
        seen = set()
        pending = list(self.dependencies[ref])
        while pending:
            name = pending.pop()
            if name not in seen:
                seen.add(name)
                pending.extend(self.dependencies[name])
        return {name: self.contracts[name] for name in sorted(seen)}

    def plan(self):
        return [
            {
                "node": n,
                "block": self.nodes[n]["block"],
                "port": p,
                "next": d,
                "contract": self.nodes[d]["definition"]["input"],
            }
            for n, routes in sorted(self.edges.items())
            for p, d in sorted(routes.items())
        ]
