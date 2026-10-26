#!/usr/bin/env python3
"""NL0 v2 accounting and audit receipts; explicit legacy v1 inspection. Not a prover."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import background


_CLOSURE_SPEC = importlib.util.spec_from_file_location("nl0_closure", Path(__file__).with_name("closure.py"))
closure = importlib.util.module_from_spec(_CLOSURE_SPEC)
_CLOSURE_SPEC.loader.exec_module(closure)


class Invalid(ValueError):
    pass


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Invalid(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def load(path):
    return json.loads(Path(path).read_text(), object_pairs_hook=unique_object)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, code, message):
    if not condition:
        raise Invalid(f"{code}: {message}")


def record(value, required, where, optional=()):
    require(isinstance(value, dict), "TYPE", f"{where} must be an object")
    require(set(required) <= value.keys(), "FIELDS", f"{where} missing {set(required)-value.keys()}")
    require(value.keys() <= set(required) | set(optional), "FIELDS", f"{where} unknown {value.keys()-set(required)-set(optional)}")


def string(value, where):
    require(isinstance(value, str) and value.strip(), "TYPE", f"{where} must be a nonempty string")


def strings(value, where, unique=True):
    require(isinstance(value, list), "TYPE", f"{where} must be a list")
    for item in value:
        string(item, where)
    if unique:
        require(len(value) == len(set(value)), "DUPLICATE", f"{where} repeats an item")


def indexed(items, prefix, where):
    require(isinstance(items, list), "TYPE", f"{where} must be a list")
    result = {}
    for item in items:
        require(isinstance(item, dict), "TYPE", f"{where} entry must be an object")
        key = item.get("id", "")
        require(isinstance(key, str) and re.fullmatch(prefix, key), "ID", f"invalid {where} ID {key!r}")
        require(key not in result, "DUPLICATE", f"duplicate {where} ID {key}")
        result[key] = item
    return result


def local_path(base, relative):
    string(relative, "evidence path")
    path = (base / relative).resolve()
    require(not Path(relative).is_absolute() and path.is_relative_to(base.resolve()),
            "PATH", f"evidence must stay inside the case: {relative}")
    return path


def evidence(base, entries, allow_empty=False):
    require(isinstance(entries, list) and (allow_empty or entries), "EVIDENCE", "missing evidence list")
    for entry in entries:
        record(entry, {"path", "sha256"}, "evidence")
        path = local_path(base, entry["path"])
        require(path.is_file(), "EVIDENCE", f"missing file {path}")
        require(sha(path) == entry["sha256"], "EVIDENCE-HASH", f"changed evidence {path}")


RULES = {
    "direct", "modus_ponens", "implication_introduction", "negation_introduction",
    "contradiction_classical", "case_elimination", "forall_introduction",
    "exists_elimination", "natural_induction",
}
CHECKS = closure.acceptance.current().check_ids('inference')
EXTERNAL_CHECKS = {"literature_identity", "result_location", "statement_fidelity",
                   "context_completeness", "version_and_eligibility"}
VERDICTS = {"PASS", "FAIL", "UNVERIFIED"}


def validate(graph_path, spec_path, audit_path=None, *, allow_unresolved=False, legacy=False):
    graph_path, spec_path = Path(graph_path), Path(spec_path)
    base = graph_path.parent
    graph, spec = load(graph_path), load(spec_path)
    record(spec, {"format_version", "case_id", "full_target", "conclusion", "parameters",
                  "hypotheses", "definitions", "logic", "pins", "inputs"}, "spec")
    require(type(spec["format_version"]) is int and spec["format_version"] in {1, 2}, "VERSION", "spec version")
    current = spec["format_version"] == 2
    require(current or legacy, "LEGACY-CONTRACT", "v1 is historical; use --legacy for inspection, not current acceptance")
    require(not current or not legacy, "VERSION", "--legacy is only for historical v1 artifacts")
    for key in ("case_id", "full_target", "conclusion"):
        string(spec[key], f"spec.{key}")
    record(graph, {"format_version", "case_id", "spec_sha256", "propositions", "inferences"}, "graph")
    require(type(graph["format_version"]) is int and graph["format_version"] == spec["format_version"], "VERSION", "graph/spec versions differ")
    require(graph["case_id"] == spec["case_id"], "SPEC", "case IDs differ")
    require(graph["spec_sha256"] == sha(spec_path), "SPEC-HASH", "graph is bound to a different specification")
    evidence(base, spec["inputs"])
    hypotheses = indexed(spec["hypotheses"], r"H\d{3,}", "hypotheses")
    for key, item in hypotheses.items():
        record(item, {"id", "statement", "origin"}, key)
        string(item["statement"], key)
        string(item["origin"], f"{key}.origin")
    definitions = indexed(spec["definitions"], r"D\d{3,}", "definitions")
    globals_ = set()
    require(isinstance(spec["parameters"], list), "TYPE", "parameters must be a list")
    for item in spec["parameters"]:
        record(item, {"symbol", "type"}, "parameter")
        string(item["type"], "parameter type")
        string(item["symbol"], "parameter symbol")
        require(item["symbol"] not in globals_, "GLOBAL-NAME", "duplicate parameter")
        globals_.add(item["symbol"])
    for key, item in definitions.items():
        record(item, {"id", "symbol", "definition", "type", "depends_on", "requires"}
               | ({"binders", "objects"} if current else set()), key)
        for field in ("symbol", "definition", "type"):
            string(item[field], f"{key}.{field}")
        require(item["symbol"] not in globals_, "GLOBAL-NAME", f"global symbol repeated: {item['symbol']}")
        globals_.add(item["symbol"])
        for field in ("depends_on", "requires"):
            strings(item[field], f"{key}.{field}")
        require(set(item["depends_on"]) <= definitions.keys(), "DEFINITION", f"unknown D dependency in {key}")

    def definition_closure(ids, active=None):
        active = set() if active is None else active
        result = set()
        for key in ids:
            require(key in definitions, "DEFINITION", f"unknown definition {key}")
            require(key not in active, "DEFINITION-CYCLE", f"circular definition {key}")
            result.add(key)
            result.update(definition_closure(definitions[key]["depends_on"], active | {key}))
        return result

    definition_closure(list(definitions))
    record(spec["logic"], {"classical", "rules", "calculations"} | ({"primitives"} if current else set()), "logic")
    require(type(spec["logic"]["classical"]) is bool, "TYPE", "logic.classical must be Boolean")
    strings(spec["logic"]["rules"], "logic.rules")
    strings(spec["logic"]["calculations"], "logic.calculations")
    require(set(spec["logic"]["rules"]) <= RULES, "LOGIC", "unknown logical rule")
    record(spec["pins"], {"lean_version", "mathlib_commit", "mathlib_root"}, "pins")
    for value in spec["pins"].values():
        string(value, "pin")

    propositions = indexed(graph["propositions"], r"(?:[HEMN]\d{3,}|P)", "propositions")
    inferences = indexed(graph["inferences"], r"R\d{3,}", "inferences")
    prefixes = {"hypothesis": "H", "external": "E", "mathlib": "M", "internal": "N", "target": "P"}
    sources = {}
    for key, item in propositions.items():
        kind = item.get("kind")
        require(kind in prefixes and key.startswith(prefixes[kind]), "KIND", f"invalid proposition kind/ID {key}")
        extra = {"source"} if kind in {"external", "mathlib"} else {"origin"} if kind == "internal" else set()
        record(item, {"id", "kind", "statement", "definitions"} | extra
               | ({"binders", "objects"} if current else set()), key)
        string(item["statement"], key)
        strings(item["definitions"], f"{key}.definitions")
        definition_closure(item["definitions"])
        if kind == "hypothesis":
            require(key in hypotheses and item["statement"] == hypotheses[key]["statement"],
                    "HYPOTHESIS", f"unfrozen or changed H {key}")
        elif kind == "target":
            require(key == "P" and item["statement"] == spec["conclusion"], "TARGET", "target differs from frozen conclusion")
        elif kind == "internal":
            string(item["origin"], f"{key}.origin")
        elif kind in {"external", "mathlib"}:
            source = item["source"]
            common = {"statement", "evidence", "hypotheses"}
            extra = {"declaration", "module", "mathlib_commit", "source_path", "source_sha256", "signature", "declaration_kind"} if kind == "mathlib" else {
                "author", "title", "version", "identifier", "locator", "notation_map", "errata",
                "source_kind", "origin", "retrieved_at", "source_statement", "context",
                "qualification", "version_check"}
            record(source, common | extra | ({"primary_evidence"} if kind == "external" else set()), f"{key}.source")
            require(source["statement"] == item["statement"], "SOURCE", f"source restatement mismatch {key}")
            strings(source["hypotheses"], f"{key}.hypotheses")
            evidence(base, source["evidence"])
            for field in extra:
                string(source[field], f"{key}.{field}")
            if kind == "external":
                evidence(base, source["primary_evidence"])
                require(all(entry in source["evidence"] for entry in source["primary_evidence"]),
                        "SOURCE-EVIDENCE", f"primary evidence not bound in source evidence {key}")
            if kind == "mathlib":
                require(source["mathlib_commit"] == spec["pins"]["mathlib_commit"], "SOURCE-PIN", f"wrong M commit {key}")
                require(source["declaration_kind"] in {"theorem", "proved_instance"}, "SOURCE-KIND", f"unproved source {key}")
                require(re.match(r"^@?" + re.escape(source["declaration"]) + r"(?:\.\{|\s|:)", source["signature"]),
                        "SOURCE-SIGNATURE", f"signature names a different declaration {key}")
                require(source["source_path"] == source["module"].replace(".", "/") + ".lean",
                        "SOURCE-MODULE", f"module/path mismatch {key}")
                probes = []
                for entry in source["evidence"]:
                    path = local_path(base, entry["path"])
                    if path.suffix == ".json":
                        payload = load(path)
                        if isinstance(payload, dict) and payload.get("probe_version") == 1:
                            probes.append(payload)
                require(any(probe.get("exit_code") == 0
                            and probe.get("mathlib_commit") == source["mathlib_commit"]
                            and re.search(r"\bversion " + re.escape(spec["pins"]["lean_version"]) + r"(?:,|\s)", probe.get("lean_version", ""))
                            and all(probe.get("sources", {}).get(key, {}).get(field) == source[field]
                                    for field in ("declaration", "signature", "source_path", "source_sha256", "declaration_kind"))
                            for probe in probes), "SOURCE-PROBE", f"missing matching successful pinned signature probe {key}")
                mroot = Path(spec["pins"]["mathlib_root"]).resolve()
                rel = Path(source["source_path"])
                mpath = (mroot / rel).resolve()
                require(not rel.is_absolute() and mpath.is_relative_to(mroot), "SOURCE-PATH", key)
                require(mpath.is_file() and sha(mpath) == source["source_sha256"], "SOURCE-HASH", f"source bytes differ {key}")
                actual = subprocess.run(["git", "-C", str(mroot), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
                require(actual == source["mathlib_commit"], "SOURCE-PIN", f"checkout changed {key}")
                tracked = subprocess.run(["git", "-C", str(mroot), "ls-files", "--error-unmatch", str(rel)], capture_output=True)
                clean = subprocess.run(["git", "-C", str(mroot), "diff", "--quiet", "HEAD", "--", str(rel)], capture_output=True)
                require(tracked.returncode == 0 and clean.returncode == 0, "SOURCE-DIRTY", f"not clean official source {key}")
            sources[key] = source
    require("P" in propositions and propositions["P"]["kind"] == "target", "TARGET", "missing unique target P")
    require({p for p, value in propositions.items() if value["kind"] == "hypothesis"} == set(hypotheses),
            "HYPOTHESIS", "every frozen original H must be present as an initial node")
    for key, definition in definitions.items():
        require(set(definition["requires"]) <= propositions.keys(), "DEFINITION-PREREQUISITE", f"unknown proof guard in {key}")
        require(all(propositions[p]["kind"] in {"hypothesis", "internal"} for p in definition["requires"]),
                "DEFINITION-PREREQUISITE", f"invalid proof guard in {key}")

    producer = {}
    for key, item in inferences.items():
        record(item, {"id", "inputs", "output", "definitions", "rules", "locals", "argument", "applications"}, key)
        for field in ("inputs", "definitions", "rules"):
            strings(item[field], f"{key}.{field}")
        require(set(item["inputs"]) <= propositions.keys(), "INPUT", f"unknown graph input {key}")
        out = item["output"]
        require(out in propositions and propositions[out]["kind"] in {"internal", "target"}, "OUTPUT", f"invalid output {key}")
        require(out not in producer, "PRODUCER", f"multiple producers of {out}")
        producer[out] = key
        definition_closure(item["definitions"])
        require(item["rules"] and set(item["rules"]) <= set(spec["logic"]["rules"]), "LOGIC", f"unpermitted rule {key}")
        require(spec["logic"]["classical"] or "contradiction_classical" not in item["rules"], "LOGIC", f"classical rule in constructive context {key}")
        require(isinstance(item["locals"], list), "TYPE", f"{key}.locals")
        bindings = set()
        for binder in item["locals"]:
            local_extra = {"start", "end", "kind", "declaration", "from_inputs", "from_local", "objects"} if current else set()
            record(binder, {"symbol", "type", "scope"} | local_extra, f"{key}.local")
            for field in {"symbol", "type", "scope"} | (local_extra - {"from_inputs", "from_local", "objects"}):
                string(binder[field], f"{key}.local.{field}")
            require(binder["symbol"] not in globals_, "SHADOW", f"local shadows global {binder['symbol']} in {key}")
            pair = (binder["scope"], binder["symbol"])
            require(pair not in bindings, "BINDER", f"duplicate binder {pair} in {key}")
            bindings.add(pair)
        require(isinstance(item["argument"], list) and item["argument"], "ARGUMENT", f"missing argument {key}")
        used, introduced, active = set(), set(), set()
        for step in item["argument"]:
            record(step, {"text", "uses", "introduces", "discharges"}
                   | ({"id", "objects", "uses_local", "produces"} if current else set()), f"{key}.step")
            string(step["text"], f"{key}.text")
            for field in ("uses", "introduces", "discharges"):
                strings(step[field], f"{key}.{field}")
            require(set(step["uses"]) <= set(item["inputs"]), "CITATION", f"undeclared graph citation in {key}/{step.get('id','step')}: {sorted(set(step['uses'])-set(item['inputs']))}")
            used.update(step["uses"])
            for assumption in step["introduces"]:
                require(re.fullmatch(r"L[1-9]\d*", assumption) and assumption not in introduced,
                        "LOCAL-ASSUMPTION", f"invalid/repeated introduction {assumption} in {key}")
                introduced.add(assumption)
                active.add(assumption)
            for assumption in step["discharges"]:
                require(assumption in active, "LOCAL-ASSUMPTION", f"invalid discharge {assumption} in {key}")
                active.remove(assumption)
        require(not active, "LOCAL-ASSUMPTION", f"unclosed local assumptions {active} in {key}")
        require(used == set(item["inputs"]), "CITATION", f"unused declared input in {key}: {set(item['inputs'])-used}")
        require(isinstance(item["applications"], list), "TYPE", f"{key}.applications")
        app_ids, applied_sources = set(), set()
        for app in item["applications"]:
            record(app, {"input", "bindings", "hypothesis_checks"} | ({"at"} if current else set()),
                   f"{key}.application", optional={"id"})
            aid = app["input"]
            require(aid in sources and aid in item["inputs"], "APPLICATION", f"invalid application {key}/{aid}")
            if propositions[aid]["kind"] == "external" or "id" in app:
                require(isinstance(app.get("id"), str) and re.fullmatch(r"A\d{3,}", app["id"]),
                        "APPLICATION-ID", f"missing/invalid actual-use ID {key}/{aid}")
            application_id = app.get("id", aid)
            require(application_id not in app_ids, "APPLICATION", f"duplicate actual-use ID {key}/{application_id}")
            app_ids.add(application_id)
            applied_sources.add(aid)
            string(app["bindings"], f"{key}/{aid}.bindings")
            strings(app["hypothesis_checks"], f"{key}/{aid}.hypothesis_checks", unique=False)
            require(len(app["hypothesis_checks"]) == len(sources[aid]["hypotheses"]), "APPLICATION", f"incomplete hypothesis mapping {key}/{aid}: expected {len(sources[aid]['hypotheses'])}, received {len(app['hypothesis_checks'])}; source obligations={sources[aid]['hypotheses']}")
        expected_sources=set(item['inputs']) & sources.keys()
        require(applied_sources == expected_sources, "APPLICATION", f"missing source application in {key}: missing={sorted(expected_sources-applied_sources)}, extra={sorted(applied_sources-expected_sources)}. Record actual at/bindings/hypothesis_checks; a source lookup alone is not an application.")

    require(set(producer) == {p for p, v in propositions.items() if v["kind"] in {"internal", "target"}}, "PRODUCER", "unproved internal/target proposition")
    ordered, closure_cache = [], {}

    def ancestors(key, active=None):
        active = set() if active is None else active
        require(key not in active, "CYCLE", f"circular proof at {key}")
        if key in closure_cache:
            return closure_cache[key]
        result = {key}
        if key in producer:
            for dep in inferences[producer[key]]["inputs"]:
                result.update(ancestors(dep, active | {key}))
        closure_cache[key] = result
        ordered.append(key)
        return result

    for key in propositions:
        ancestors(key)
    target_closure = ancestors("P")
    require(all(p in target_closure for p, v in propositions.items() if v["kind"] != "hypothesis"),
            "ORPHAN", "retained non-H IDs outside P's proof closure="+
            repr(sorted(p for p,v in propositions.items() if v['kind']!='hypothesis' and p not in target_closure))+
            ". Remove only genuinely unused inventory; a theorem still invoked in prose must instead be registered and actually used.")
    for key, item in inferences.items():
        available = set().union(*(ancestors(p) for p in item["inputs"])) if item["inputs"] else set()
        refs = set(item["definitions"]) | set(propositions[item["output"]]["definitions"])
        for p in item["inputs"]:
            refs.update(propositions[p]["definitions"])
        for did in definition_closure(refs):
            require(set(definitions[did]["requires"]) <= available, "DEFINITION-PREREQUISITE", f"{key} uses {did} before its proof guard")

    if current:
        closed_call(closure.validate, graph, spec, propositions, inferences, definitions, definition_closure)

    result = {"status": "STRUCTURE-PASSED" if current else "LEGACY-STRUCTURE-PASSED", "case_id": spec["case_id"],
              "contract_version": spec["format_version"], "current_standard_receipt_valid": False,
              "propositions": len(propositions), "inferences": len(inferences),
              "kinds": dict(Counter(p["kind"] for p in propositions.values())),
              "unused_original_hypotheses": sorted(hypotheses.keys() - target_closure),
              "topological_propositions": ordered,
              "graph_sha256": sha(graph_path), "spec_sha256": sha(spec_path),
              "audit_receipt_valid": False, "mathematics_automatically_verified": False}
    data = result, graph, spec, propositions, inferences, definitions, definition_closure, ancestors
    if audit_path:
        audit = load(audit_path)
        record(audit, {"format_version", "graph_sha256", "spec_sha256", "reviewer", "target_review",
                       "definition_reviews", "source_reviews", "inference_reviews"}, "audit", optional={"structure_review", "background_policy"})
        if 'background_policy' in audit:
            require(audit['background_policy'] == background.POLICY, 'BACKGROUND-POLICY', 'unsupported supplement policy')
        require(type(audit["format_version"]) is int and audit["format_version"] in ({3} if current else {1, 2}),
                "AUDIT-VERSION", "v2 graphs require audit v3; legacy receipts cannot establish current acceptance")
        has_external = any(p["kind"] == "external" for p in propositions.values())
        require(not has_external or audit["format_version"] >= 2, "AUDIT-VERSION", "external theorems require audit version >=2")
        require(audit["graph_sha256"] == sha(graph_path) and audit["spec_sha256"] == sha(spec_path), "STALE-AUDIT", "audit is bound to different bytes")
        record(audit["reviewer"], {"identity", "mode", "independent", "disclosure"}, "reviewer")
        for field in ("identity", "mode", "disclosure"):
            string(audit["reviewer"][field], f"reviewer.{field}")
        require(type(audit["reviewer"]["independent"]) is bool, "REVIEWER", "independent must be Boolean")
        require(audit["reviewer"]["mode"] != "same_context_self_audit" or not audit["reviewer"]["independent"], "REVIEWER", "self-audit cannot be independent")

        unresolved = []

        def verdict(value, where):
            require(isinstance(value, str) and value in VERDICTS, "AUDIT-VERDICT", f"invalid verdict {where}")
            if value != "PASS":
                unresolved.append({"review": where, "verdict": value})
                require(allow_unresolved, "AUDIT-FAIL", f"{where} is {value}")

        def review(entry, where, inference=False, external=False, located_packet=None):
            fields = {"verdict", "notes", "evidence"} | ({"checks"} if inference else set())
            if external:
                fields.add("citation_checks")
            if inference and audit["format_version"] >= 2:
                fields.add("external_applications")
            if inference and current:
                fields.add("replay")
            if located_packet is not None:
                fields.add("locations")
            record(entry, fields, where, optional=({'inheritance', 'background_notes'} if inference else {'inheritance'}) if current else ())
            inherited=None
            if 'inheritance' in entry:
                import audit_reuse
                scope=('packet:'+where if inference else where if where in {'target','structure'} else
                       'definition:'+where if where in definitions else 'source:'+where if where in sources else None)
                require(scope is not None,'AUDIT-INHERITANCE','Inheritance is allowed only on a complete top-level review item')
                inherited=closed_call(audit_reuse.validate,base,entry['inheritance'],data,scope,entry)
            verdict(entry["verdict"], where)
            string(entry["notes"], where)
            evidence(base, entry["evidence"])
            if located_packet is not None:
                strings(entry["locations"], where + ".locations")
                require(entry["verdict"] != "PASS" or entry["locations"], "AUDIT-LOCATION", where)
                for pointer in entry["locations"]:
                    closed_call(closure.resolve, located_packet, pointer)
            if inference:
                record(entry["checks"], CHECKS | (closure.CLOSURE_CHECKS if current else set()), where + ".checks")
                for name, value in entry["checks"].items():
                    if current:
                        review(value, f"{where}.checks.{name}", located_packet=packet(data, where))
                    else:
                        verdict(value, f"{where}.checks.{name}")
                if current:
                    notes = entry.get('background_notes', [])
                    require(not notes or audit.get('background_policy') == background.POLICY,
                            'BACKGROUND-POLICY', 'notes require their declared acceptance policy')
                    closed_call(background.validate, notes, packet(data, where), base)
                    replay = entry["replay"]
                    record(replay, {"packet_sha256", "mode", "carrier", "prior_exposure", "read_materials"}, where + ".replay", optional={'library_evidence'})
                    expected = inherited['previous_packet_sha256'] if inherited else packet(data, where)["packet_sha256"]
                    require(replay["packet_sha256"] == expected, "STALE-PACKET", where)
                    require(replay["mode"] in {"unperformed", "same_context_diagnostic", "fresh_packet_only", background.MODE}, "REPLAY-BOUNDARY", where)
                    string(replay["carrier"], where + ".carrier")
                    strings(replay["prior_exposure"], where + ".prior_exposure")
                    strings(replay["read_materials"], where + ".read_materials")
                    if entry["verdict"] == "PASS" or entry["checks"]["packet_replay"]["verdict"] == "PASS":
                        refs = replay.get('library_evidence', [])
                        if replay['mode'] == background.MODE:
                            require(audit.get('background_policy') == background.POLICY, 'BACKGROUND-POLICY', where)
                            if refs:evidence(base, refs)
                            materials = ['packet:'+expected] + ['mathlib-evidence:'+x['sha256'] for x in refs]
                            require(all(e in refs for note in notes if note['kind']=='mathlib' for e in note['source']['evidence']),
                                    'REPLAY-BOUNDARY', 'background source not in reviewed material list')
                        else:
                            require(not notes and not refs, 'REPLAY-BOUNDARY', 'old packet-only replay cannot import background notes')
                            materials = ['packet:'+expected]
                        require(replay["mode"] in {"fresh_packet_only", background.MODE} and not replay["prior_exposure"]
                                and replay["read_materials"] == materials
                                and replay["carrier"] != "UNASSIGNED", "REPLAY-BOUNDARY", where)
            if external:
                record(entry["citation_checks"], EXTERNAL_CHECKS, where + ".citation_checks")
                for name, value in entry["citation_checks"].items():
                    review(value, f"{where}.citation_checks.{name}")
            if inference and audit["format_version"] >= 2:
                actual = {a["id"]: a for a in inferences[where]["applications"]
                          if propositions[a["input"]]["kind"] == "external"}
                require(isinstance(entry["external_applications"], dict)
                        and set(entry["external_applications"]) == set(actual),
                        "AUDIT-APPLICATION-COVERAGE", f"missing/extra E actual-use review {where}")
                available = set(inferences[where]["inputs"]) if current else (
                    set().union(*(ancestors(p) for p in inferences[where]["inputs"])) if inferences[where]["inputs"] else set())
                for application_id, app_review in entry["external_applications"].items():
                    location = f"{where}.external_applications.{application_id}"
                    record(app_review, {"input", "verdict", "notes", "evidence", "bindings_review",
                                       "hypothesis_reviews", "conclusion_review", "bridges"}, location)
                    aid = actual[application_id]["input"]
                    require(app_review["input"] == aid, "AUDIT-APPLICATION-SOURCE", f"wrong E at {location}")
                    verdict(app_review["verdict"], location)
                    string(app_review["notes"], location)
                    evidence(base, app_review["evidence"])
                    review(app_review["bindings_review"], location + ".bindings_review")
                    review(app_review["conclusion_review"], location + ".conclusion_review")
                    hreviews = app_review["hypothesis_reviews"]
                    require(isinstance(hreviews, list) and len(hreviews) == len(sources[aid]["hypotheses"]),
                            "AUDIT-HYPOTHESIS-COVERAGE", f"incomplete source condition review {location}")
                    for number, hreview in enumerate(hreviews, 1):
                        review(hreview, f"{location}.hypothesis_reviews.{number}")
                    strings(app_review["bridges"], location + ".bridges")
                    require(all(p in available and propositions[p]["kind"] == "internal"
                                for p in app_review["bridges"]), "AUDIT-BRIDGE", f"unproved/unavailable bridge at {location}")

        review(audit["target_review"], "target")
        if 'structure_review' in audit:review(audit['structure_review'],'structure')
        for field, expected, is_inference in (("definition_reviews", set(definitions), False),
                                               ("source_reviews", set(sources), False),
                                               ("inference_reviews", set(inferences), True)):
            require(isinstance(audit[field], dict) and set(audit[field]) == expected, "AUDIT-COVERAGE", f"incomplete/extra {field}")
            for key, entry in audit[field].items():
                review(entry, key, is_inference, key in sources and propositions[key]["kind"] == "external")
        result.update({"audit_record_complete": True, "audit_receipt_valid": not unresolved,
                       "current_standard_receipt_valid": current and not unresolved,
                       "audit_status": "AUDIT-NOT-PASSED" if unresolved else (
                           "AUDIT-RECEIPT-VALID" if current else "LEGACY-AUDIT-RECEIPT-VALID"),
                       "unresolved_reviews": unresolved, "audit_format_version": audit["format_version"],
                       "reviewer": audit["reviewer"]})
        if current:
            notes = {rid: deepcopy_entry.get('background_notes', []) for rid, deepcopy_entry in audit['inference_reviews'].items()}
            result.update(background_policy=audit.get('background_policy'), background_notes=notes,
                          background_note_count=sum(len(x) for x in notes.values()),
                          audit_sha256=sha(audit_path),
                          background_supplement=background.supplement(data, notes))
            if not unresolved and any(notes.values()):result['audit_status']='AUDIT-RECEIPT-VALID-WITH-BACKGROUND-NOTES'
    return result, graph, spec, propositions, inferences, definitions, definition_closure, ancestors


def closed_call(function, *args):
    try:
        return function(*args)
    except ValueError as error:
        raise Invalid(str(error)) from error


def render(data, destination):
    result, graph, spec, props, steps, defs, _, _ = data
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    lines = [f"# NL0 — {spec['case_id']}", "", "> Generated from canonical nl0.json and spec.json. Do not edit this view.",
             "", "## Frozen original target", "", spec["full_target"], "", "## Original hypotheses", ""]
    for item in spec["hypotheses"]:
        lines.extend([f"- **{item['id']}**: {item['statement']}"])
    if graph["format_version"] == 2:
        lines.extend(["", "## Declared parameters and logical primitives", ""])
        for item in spec["parameters"]:
            lines.append(f"- `{item['symbol']}`: {item['type']}.")
        for item in spec["logic"]["primitives"]:
            lines.append(f"- `{item['symbol']}`: {item['type']}. {item['meaning']}")
    lines.extend(["", "## Global definitions and notation", ""])
    for item in defs.values():
        lines.extend([f"### {item['id']} — {item['symbol']}", "", item["definition"], "",
                      f"Type: `{item['type']}`. Definition dependencies: {', '.join(item['depends_on']) or 'none'}. Proof prerequisites: {', '.join(item['requires']) or 'none'}.", ""])
    mermaid = ["flowchart TD"]
    for key, item in props.items():
        mermaid.append(f'  {key}["{key}: {item["kind"]}"]')
    for key, item in steps.items():
        mermaid.append(f'  {key}{{{{"{key}"}}}}')
        for dep in item["inputs"]:
            mermaid.append(f"  {dep} --> {key}")
        mermaid.append(f"  {key} --> {item['output']}")
    lines.extend(["## Bipartite proof graph", "", "```mermaid", *mermaid, "```", "", "## Source propositions", ""])
    for key in result["topological_propositions"]:
        item = props[key]
        if item["kind"] not in {"external", "mathlib"}:
            continue
        source = item["source"]
        lines.extend([f"### {key}", "", item["statement"], ""])
        if item["kind"] == "mathlib":
            lines.extend([f"Declaration: `{source['declaration']}`; module `{source['module']}`.", "", "```lean", source["signature"], "```", ""])
        else:
            lines.extend([f"Source: {source['author']}, {source['title']}, {source['version']}.", "",
                          f"Identifier: {source['identifier']}. Locator: {source['locator']}.", "",
                          "Primary-source statement: " + source["source_statement"], "",
                          "Notation map: " + source["notation_map"], "",
                          "Context: " + source["context"], "",
                          "Version check: " + source["version_check"], ""])
        lines.extend(["Hypotheses: " + "; ".join(source["hypotheses"]), ""])
    lines.extend(["## Derived propositions and their arguments", ""])
    by_output = {step["output"]: step for step in steps.values()}
    for key in result["topological_propositions"]:
        if key not in by_output:
            continue
        item, step = props[key], by_output[key]
        lines.extend([f"### {key} — {step['id']}", "", item["statement"], "", f"Inputs: {', '.join(step['inputs']) or 'none'}. Rules: {', '.join(step['rules'])}.", ""])
        if graph["format_version"] == 2:
            lines.extend(["Statement binders: " + json.dumps(item["binders"], ensure_ascii=False), "",
                          "Local declarations: " + json.dumps(step["locals"], ensure_ascii=False), ""])
        for n, paragraph in enumerate(step["argument"], 1):
            lines.extend([f"{n}. {paragraph['text']}", "", f"   Inputs used: {', '.join(paragraph['uses']) or 'local calculation/logic'}. Introduces: {', '.join(paragraph['introduces']) or 'none'}. Discharges: {', '.join(paragraph['discharges']) or 'none'}.", ""])
            if graph["format_version"] == 2:
                lines.extend([f"   Step {paragraph['id']}; objects: {', '.join(paragraph['objects']) or 'none'}; prior local facts: {', '.join(paragraph['uses_local']) or 'none'}.", ""])
                for fact in paragraph["produces"]:
                    lines.extend([f"   {fact['id']}: {fact['statement']} Active assumptions: {', '.join(fact['assumptions']) or 'none'}.", ""])
        for app in step["applications"]:
            lines.extend([f"Source {app['input']} ({app.get('id', app['input'])}) — {app['bindings']}", "", *[f"- {check}" for check in app["hypothesis_checks"]], ""])
    (destination / "NL0.md").write_text("\n".join(lines) + "\n")
    (destination / "graph.mmd").write_text("\n".join(mermaid) + "\n")
    return {"rendered": [str(destination / "NL0.md"), str(destination / "graph.mmd")]}


def packet(data, inference):
    result, graph, spec, props, steps, defs, definition_closure, ancestors = data
    require(inference in steps, "INFERENCE", f"unknown inference {inference}")
    if graph["format_version"] == 2:
        value = closed_call(closure.packet, data, inference)
        notes = result.get('background_notes', {}).get(inference, [])
        if notes:
            value['reviewed_packet_sha256'] = value.pop('packet_sha256')
            value['accepted_background_notes'] = notes
            value['background_supplement_sha256'] = result['background_supplement']['sha256']
            value['packet_sha256'] = closure.digest(value)
        return value
    step = steps[inference]
    all_props = [props[p] for p in step["inputs"]] + [props[step["output"]]]
    ids = set(step["definitions"])
    for proposition in all_props:
        ids.update(proposition["definitions"])
    dclosure = definition_closure(ids)
    guards = set().union(*(set(defs[d]["requires"]) for d in dclosure)) if dclosure else set()
    hclosure = set().union(*(ancestors(p) for p in step["inputs"])) if step["inputs"] else set()
    return {"case_id": spec["case_id"], "full_target": spec["full_target"],
            "graph_sha256": result["graph_sha256"], "spec_sha256": result["spec_sha256"],
            "audit_receipt_valid": result["audit_receipt_valid"],
            "original_hypotheses": [h for h in spec["hypotheses"] if h["id"] in hclosure],
            "logic": spec["logic"], "pins": spec["pins"],
            "definitions": [d for d in defs.values() if d["id"] in dclosure],
            "definition_prerequisites": [props[p] for p in sorted(guards)],
            "inputs": [props[p] for p in step["inputs"]], "output": props[step["output"]],
            "inference": step, "warning": "This packet is a view, not an independent proof or audit certificate."}


def global_overview(data):
    """Exhaustive global records/edges; no proof or source verdict is produced."""
    result,graph,spec=data[:3];props=graph['propositions']
    producers={r['output']:r['inputs'] for r in graph['inferences']}
    reachable=set();pending=['P']
    while pending:
        node=pending.pop()
        if node in reachable:continue
        reachable.add(node);pending.extend(producers.get(node,[]))
    unused=sorted(h['id'] for h in spec['hypotheses'] if h['id'] not in reachable)
    return {'schema':'yui-global-overview-2',
        'scope':'Lossless global-context/statement projection of the bound canonical files. No proof judgment, extra premise or author/reviewer note. Proof bodies and full native source readbacks remain in the other task documents.',
        'canonical_hashes':{'spec.json':result['spec_sha256'],'nl0.json':result['graph_sha256']},
        'context':{key:spec[key] for key in ['full_target','conclusion','parameters','logic']},
        'spec_hypotheses':[{'pointer':f'spec.json#/hypotheses/{i}','record':row}
            for i,row in enumerate(spec['hypotheses'])],
        'graph_hypotheses':[{'pointer':f'nl0.json#/propositions/{i}','record':row}
            for i,row in enumerate(props) if row['kind']=='hypothesis'],
        'definitions':[{'pointer':f'spec.json#/definitions/{i}','record':row}
            for i,row in enumerate(spec['definitions'])],
        'other_propositions':[{'pointer':f'nl0.json#/propositions/{i}','record':row}
            for i,row in enumerate(props) if row['kind']!='hypothesis'],
        'inference_edges':[{'pointer':f'nl0.json#/inferences/{i}',
            **{key:row[key] for key in ['id','inputs','output','definitions','rules']}}
            for i,row in enumerate(graph['inferences'])],
        'inventory':{'spec_H_ids':[h['id'] for h in spec['hypotheses']],
            'graph_H_ids':[p['id'] for p in props if p['kind']=='hypothesis'],
            'unused_original_hypotheses':unused,
            'reachability_basis':'Declared R input/output edges only; actual prose uses still require audit.',
            'all_proposition_ids':[p['id'] for p in props],
            'all_definition_ids':[d['id'] for d in spec['definitions']],
            'all_inference_ids':[r['id'] for r in graph['inferences']]}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["check", "inspect-audit", "render", "packet", "overview", "audit-template"])
    parser.add_argument("graph", type=Path)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--inference")
    parser.add_argument("--legacy", action="store_true", help="Inspect historical v1; never grants current-standard acceptance")
    args = parser.parse_args()
    try:
        require(args.command != "inspect-audit" or args.audit is not None, "CLI", "inspect-audit requires --audit")
        data = validate(args.graph, args.spec, args.audit,
                        allow_unresolved=args.command == "inspect-audit", legacy=args.legacy)
        if args.command in {"check", "inspect-audit"}:
            result = data[0]
        elif args.command == "render":
            require(args.out is not None, "CLI", "render requires --out")
            result = render(data, args.out)
        elif args.command == 'overview':
            require(not args.legacy and args.audit is None,'CLI','Create a current source overview without importing an audit receipt')
            result=global_overview(data)
        elif args.command == "audit-template":
            require(args.audit is None and not args.legacy, "CLI", "Create a new pending audit without inheriting a receipt")
            result = closed_call(closure.audit_template, data, CHECKS, EXTERNAL_CHECKS,
                                 str(args.graph.resolve().relative_to(args.graph.parent.resolve())),
                                 str(args.spec.resolve().relative_to(args.graph.parent.resolve())))
        else:
            require(args.inference is not None, "CLI", "packet requires --inference")
            result = packet(data, args.inference)
        if args.out is not None and args.command in {"audit-template", "packet", "overview"}:
            require(args.out.parent.resolve() == args.graph.parent.resolve() or args.command in {"packet","overview"},
                    "PATH", "Store audit templates beside the canonical graph")
            with args.out.open("x") as handle:
                handle.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
            result = {"written": str(args.out), "status": "AUDIT-UNREVIEWED" if args.command == "audit-template" else "GLOBAL-OVERVIEW-WRITTEN" if args.command=='overview' else "PACKET-WRITTEN"}
    except (Invalid, OSError, ValueError, KeyError, TypeError, RecursionError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "INVALID", "error": str(error), "mathematics_automatically_verified": False}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
