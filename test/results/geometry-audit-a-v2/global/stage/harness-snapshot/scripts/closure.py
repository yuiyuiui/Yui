"""Explicit NL0 v2 closure accounting. This is not a natural-language prover."""
from __future__ import annotations

import copy
import hashlib
import json
import re


CLOSURE_CHECKS = {"statement_closure", "object_closure", "dependency_closure", "packet_replay"}
_IDS = re.compile(r"\b(?:[HEMN]\d{3,}|F\d{3,})\b")
_NUMBERED = re.compile(
    r"\b(?:formula|equation|identity|estimate|bound|theorem|lemma|proposition|corollary|section)"
    r"\s*\(?\d+(?:\.\d+)+[a-z]?\)?|"
    r"\b(?:by|from|using)\s+\(\d+(?:\.\d+)+[a-z]?\)|"
    r"\\(?:eqref|ref)\{(?!F\d{3,}\})[^}]+\}", re.I)
_OUTSIDE = re.compile(
    r"\b(?:as in|as defined in|as proved in|as shown in|notation from|defined in)"
    r"\s+(?:the\s+)?(?:original|paper|manuscript|source|previous section)\b", re.I)


def need(condition, code, message):
    if not condition:
        raise ValueError(f"{code}: {message}")


def fields(item, keys, where):
    need(isinstance(item, dict) and set(item) == set(keys), "CLOSURE-FIELDS", where)


def names(items, where):
    need(isinstance(items, list) and all(isinstance(x, str) and x.strip() for x in items),
         "CLOSURE-TYPE", where)
    need(len(items) == len(set(items)), "CLOSURE-DUPLICATE", where)


def opaque(text, where):
    need(not _NUMBERED.search(text) and not _OUTSIDE.search(text), "OPAQUE-REFERENCE",
         f"{where}: expand the mathematical content; use input IDs or previously proved local F IDs")


def binders(items, reserved, where):
    need(isinstance(items, list), "BINDER", where)
    result = set()
    for b in items:
        fields(b, {"symbol", "type"}, where)
        need(all(isinstance(x, str) and x.strip() for x in b.values()), "BINDER", where)
        need(b["symbol"] not in reserved | result, "SHADOW", where)
        result.add(b["symbol"])
    return result


def objects(item, available, where):
    names(item["objects"], where + ".objects")
    need(set(item["objects"]) <= available, "UNDECLARED-OBJECT",
         f"{where}: {set(item['objects']) - available}")


def validate(graph, spec, props, steps, defs, definition_closure):
    """Check declared accounting; auditors must compare it to the actual prose."""
    global_names = {p["symbol"] for p in spec["parameters"]} | {d["symbol"] for d in defs.values()}
    primitives = spec["logic"]["primitives"]
    need(isinstance(primitives, list), "FOUNDATION", "logic.primitives")
    for primitive in primitives:
        fields(primitive, {"symbol", "type", "meaning"}, "primitive")
        need(all(isinstance(v, str) and v.strip() for v in primitive.values()), "FOUNDATION", "primitive")
        need(primitive["symbol"] not in global_names, "SHADOW", "primitive shadows a global object")
        global_names.add(primitive["symbol"])

    def statement(item, where, body="statement", allowed=None):
        local = binders(item["binders"], global_names, where + ".binders")
        objects(item, (global_names if allowed is None else allowed) | local, where)
        opaque(item[body], where)
        need(not _IDS.search(item[body]), "OPAQUE-STATEMENT", f"{where}: a proposition ID cannot replace content")

    for key, d in defs.items():
        allowed = {p["symbol"] for p in spec["parameters"]} | {p["symbol"] for p in primitives}
        allowed |= {defs[x]["symbol"] for x in definition_closure(d["depends_on"])} | {d["symbol"]}
        statement(d, key, "definition", allowed)
    for key, p in props.items():
        allowed = {p["symbol"] for p in spec["parameters"]} | {p["symbol"] for p in primitives}
        allowed |= {defs[x]["symbol"] for x in definition_closure(p["definitions"])}
        statement(p, key, allowed=allowed)

    for rid, r in steps.items():
        ids = [s["id"] for s in r["argument"]]
        need(len(ids) == len(set(ids)) and all(re.fullmatch(r"S\d{3,}", x) for x in ids), "STEP-ID", rid)
        position = {key: i for i, key in enumerate(ids)}
        referenced = set(r["definitions"]) | set(props[r["output"]]["definitions"])
        for pid in r["inputs"]:
            referenced.update(props[pid]["definitions"])
        dclosure = definition_closure(referenced)
        for did in dclosure:
            need(set(defs[did]["requires"]) <= set(r["inputs"]), "DIRECT-GUARD",
                 f"{rid}/{did}: existence/property guards must be direct inputs")
        base = {p["symbol"] for p in spec["parameters"]} | {p["symbol"] for p in primitives}
        base |= {defs[x]["symbol"] for x in dclosure}
        locals_ = []
        for local in r["locals"]:
            need(local["start"] in position and local["end"] in position, "LOCAL-SCOPE", rid)
            lo, hi = position[local["start"]], position[local["end"]]
            need(lo <= hi, "LOCAL-SCOPE", rid)
            need(local["kind"] in {"arbitrary", "definition", "witness"}, "LOCAL-INTRODUCTION", rid)
            need(local["symbol"] not in global_names, "SHADOW", rid)
            for other, a, b in locals_:
                need(local["symbol"] != other["symbol"] or hi < a or lo > b, "SHADOW", rid)
            for key in ("from_inputs", "from_local", "objects"):
                names(local[key], rid + ".local." + key)
            need(set(local["from_inputs"]) <= set(r["inputs"]), "LOCAL-INTRODUCTION", rid)
            need(local["kind"] != "witness" or local["from_inputs"] or local["from_local"],
                 "WITNESS-EXISTENCE", rid)
            opaque(local["declaration"], rid + ".local.declaration")
            locals_.append((local, lo, hi))

        facts, active, visible_facts = {}, set(), {}
        for i, s in enumerate(r["argument"]):
            where = rid + "/" + s["id"]
            available = base | {local["symbol"] for local, lo, hi in locals_ if lo <= i <= hi}
            active.update(s["introduces"])
            for declaration_index, (local, lo, hi) in enumerate(locals_):
                if lo == i:
                    # Only earlier declarations, not a later simultaneous definition, justify this one.
                    earlier = base | {other["symbol"] for j, (other, a, b) in enumerate(locals_)
                                      if a <= i <= b and (a < i or j < declaration_index)}
                    objects(local, earlier, where + ".declaration")
                    need(set(local["from_local"]) <= facts.keys(), "LOCAL-INTRODUCTION", where)
                    need(all(facts[x]["assumptions"] <= active and facts[x]["objects"] <= earlier
                             for x in local["from_local"]), "LOCAL-FACT-SCOPE", where)
                    need(set(_IDS.findall(local["declaration"])) <= set(local["from_inputs"]) | set(local["from_local"]),
                         "UNDECLARED-FACT", where + ".declaration")
            objects(s, available, where)
            opaque(s["text"], where)
            names(s["uses_local"], where + ".uses_local")
            need(set(s["uses_local"]) <= facts.keys(), "LOCAL-FACT-ORDER", where)
            need(all(facts[x]["assumptions"] <= active and facts[x]["objects"] <= available
                     for x in s["uses_local"]), "LOCAL-FACT-SCOPE", where)
            visible_facts[s["id"]] = {fid for fid, fact in facts.items()
                                      if fact["assumptions"] <= active and fact["objects"] <= available}
            need(isinstance(s["produces"], list), "LOCAL-FACT", where)
            produced = set()
            remaining = active - set(s["discharges"])
            for f in s["produces"]:
                fields(f, {"id", "statement", "binders", "objects", "assumptions"}, where + ".produces")
                need(isinstance(f["id"], str) and re.fullmatch(r"F\d{3,}", f["id"])
                     and f["id"] not in facts, "LOCAL-FACT", where)
                need(isinstance(f["statement"], str) and f["statement"].strip(), "LOCAL-FACT", where)
                opaque(f["statement"], where)
                need(not _IDS.search(f["statement"]), "OPAQUE-STATEMENT", where)
                bound = binders(f["binders"], global_names | available, where + "/" + f["id"])
                objects(f, available | bound, where + "/" + f["id"])
                names(f["assumptions"], where + ".assumptions")
                need(set(f["assumptions"]) <= remaining, "LOCAL-FACT-SCOPE", where)
                facts[f["id"]] = {"assumptions": set(f["assumptions"]), "objects": set(f["objects"]) - bound}
                produced.add(f["id"])
            mentioned = set(_IDS.findall(s["text"]))
            need(mentioned <= set(s["uses"]) | set(s["uses_local"]) | produced,
                 "UNDECLARED-FACT", f"{where}: {mentioned - set(s['uses']) - set(s['uses_local']) - produced}")
            active = remaining
        for app in r["applications"]:
            need(isinstance(app["at"], str) and app["at"] in position, "APPLICATION-STEP", rid)
            step = r["argument"][position[app["at"]]]
            need(app["input"] in step["uses"], "APPLICATION-STEP", rid)
            for text in [app["bindings"], *app["hypothesis_checks"]]:
                opaque(text, rid + ".application")
                need(set(_IDS.findall(text)) <= set(r["inputs"]) | visible_facts[app["at"]],
                     "UNDECLARED-FACT", rid + ".application")


def digest(payload):
    data = {k: v for k, v in payload.items() if k != "packet_sha256"}
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def packet(data, inference):
    result, graph, spec, props, steps, defs, closure, _ = data
    step = steps[inference]
    proposition_ids = step["inputs"] + [step["output"]]
    refs = set(step["definitions"])
    for pid in proposition_ids:
        refs.update(props[pid]["definitions"])

    def port(pid):
        p = props[pid]
        answer = {key: copy.deepcopy(p[key]) for key in ("id", "kind", "statement", "definitions", "binders", "objects")}
        if p["kind"] in {"external", "mathlib"}:
            answer["source_contract"] = {"hypotheses": p["source"]["hypotheses"]}
            if p["kind"] == "mathlib":
                answer["source_contract"].update({key: p["source"][key] for key in ("declaration", "signature")})
        return answer

    payload = {"contract_version": 2, "case_id": spec["case_id"],
               "graph_sha256": result["graph_sha256"], "spec_sha256": result["spec_sha256"],
               "parameters": spec["parameters"], "logic": spec["logic"], "pins": spec["pins"],
               "definitions": [defs[x] for x in sorted(closure(refs))],
               "inputs": [port(x) for x in step["inputs"]], "output": port(step["output"]),
               "inference": step,
               "warning": "Only listed inputs are premises. No source proof, ancestor proof, or ambient H is supplied. A packet is not an audit certificate."}
    payload["packet_sha256"] = digest(payload)
    return payload


def resolve(payload, pointer):
    need(isinstance(pointer, str) and pointer.startswith("/"), "AUDIT-LOCATION", str(pointer))
    value = payload
    for part in pointer[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            need(part.isdigit() and int(part) < len(value), "AUDIT-LOCATION", pointer)
            value = value[int(part)]
        else:
            need(isinstance(value, dict) and part in value, "AUDIT-LOCATION", pointer)
            value = value[part]
    return value


def audit_template(data, checks, external_checks, graph_name, spec_name):
    result, graph, spec, props, steps, defs, _, _ = data
    need(graph["format_version"] == 2, "LEGACY-CONTRACT", "Author v2 before preparing a current audit")
    frozen = [{"path": graph_name, "sha256": result["graph_sha256"]},
              {"path": spec_name, "sha256": result["spec_sha256"]}]

    def pending():
        return {"verdict": "UNVERIFIED", "notes": "Not reviewed. Frozen artifacts are not review evidence.",
                "evidence": copy.deepcopy(frozen)}

    sources = {}
    for pid, p in props.items():
        if p["kind"] in {"mathlib", "external"}:
            entry = pending()
            if p["kind"] == "external":
                entry["citation_checks"] = {key: pending() for key in sorted(external_checks)}
            sources[pid] = entry
    inferences = {}
    for rid, r in steps.items():
        entry = pending()
        entry["checks"] = {key: dict(pending(), locations=[]) for key in sorted(checks | CLOSURE_CHECKS)}
        entry["replay"] = {"packet_sha256": packet(data, rid)["packet_sha256"], "mode": "unperformed",
                           "carrier": "UNASSIGNED", "prior_exposure": [], "read_materials": []}
        entry["external_applications"] = {}
        for app in r["applications"]:
            if props[app["input"]]["kind"] == "external":
                entry["external_applications"][app["id"]] = dict(pending(), input=app["input"],
                    bindings_review=pending(), hypothesis_reviews=[pending() for _ in app["hypothesis_checks"]],
                    conclusion_review=pending(), bridges=[])
        inferences[rid] = entry
    return {"format_version": 3, "graph_sha256": result["graph_sha256"], "spec_sha256": result["spec_sha256"],
            "reviewer": {"identity": "UNASSIGNED", "mode": "unperformed", "independent": False,
                         "disclosure": "Template only. No mathematical review or packet replay has occurred."},
            "target_review": pending(), "definition_reviews": {key: pending() for key in defs},
            "source_reviews": sources, "inference_reviews": inferences}
