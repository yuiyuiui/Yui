"""Repository standard, compatibility baseline and evidence-backed maintenance audit."""

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

from . import storage
from .conformance import verify
from .engine import replay
from .model import Model
from .protocol import Fault, digest, durable, fields, load, need, parse

STANDARD = "workflow-repository/1"
BASELINE = ".workflow-acceptance.json"
MANAGED = ".workflow-runtime.json"
RULES = {
    "package": "Skill entry, named public contracts and local links resolve",
    "runtime": "Managed runtime matches its manifest and the trusted builder",
    "composition": "Every named interface, route, control and adapter is present",
    "compatibility": "Changes respect versioned contracts and prior accepted behavior",
    "behavior": "Declared paths, independent business oracles and historical obligations pass",
    "entry": "A fresh process executes the portable public CLI and independently validates delivery",
    "extensions": "Registered project-specific test suites pass",
    "replay": "Supplied historical runs remain compatible",
}


def runtime_hashes(project):
    package = project / "scripts" / "wfcore"
    paths = [
        project / "requirements.txt",
        project / "scripts" / "flow.py",
        *package.rglob("*.py"),
    ]
    hashes = {}
    for p in paths:
        rel = p.relative_to(project)
        need(
            not p.is_symlink() and p.resolve() == project.resolve() / rel,
            f"unsafe runtime path {rel}",
        )
        hashes[rel.as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return hashes


def skill_info(root):
    file = root / "SKILL.md"
    need(file.is_file() and not file.is_symlink(), "missing SKILL.md")
    text = file.read_text()
    front = re.match(r"\A---\s*\n(.*?)\n---[ \t]*\n", text, re.S)
    need(front, "missing YAML skill metadata")
    meta = yaml.safe_load(front.group(1))
    need(
        isinstance(meta, dict)
        and isinstance(meta.get("description"), str)
        and meta["description"].strip(),
        "skill needs a description",
    )
    need(
        isinstance(meta.get("name"), str)
        and re.fullmatch(r"[a-z][a-z0-9-]{0,63}", meta["name"]),
        "invalid skill name",
    )
    for raw in re.findall(r"\[[^\]\n]*\]\(([^)\s]+)\)", text[front.end() :]):
        if ":" in raw or raw.startswith("#"):
            continue
        path = (root / raw.split("#", 1)[0]).resolve()
        need(
            path.is_relative_to(root.resolve()) and path.exists(),
            f"unresolved local skill link {raw}",
        )
    return meta


def suites(root):
    path = root / "checks.json"
    value = load(path) if path.is_file() else {"suites": []}
    fields(value, {"suites"}, set(), "checks")
    need(isinstance(value["suites"], list), "checks.suites needs a list")
    out = {}
    covered = set()
    for row in value["suites"]:
        fields(row, {"id", "file", "timeout"}, {"covers", "origin_cases"}, "suite")
        key, file = row["id"], row["file"]
        need(
            isinstance(key, str)
            and re.fullmatch("[a-z][a-z0-9-]*", key)
            and key not in out,
            "duplicate/invalid suite ID",
        )
        other = row.get("covers", [])
        need(
            isinstance(other, list) and all(isinstance(f, str) for f in other),
            f"{key}: covers must be a list of paths",
        )
        members = {}
        for name in [file, *other]:
            rel = Path(name)
            need(
                not rel.is_absolute()
                and rel.parts
                and rel.parts[0] in ("blocks", "tests")
                and ".." not in rel.parts,
                f"{key}: suite paths must be project-relative files under blocks/ or tests/",
            )
            p = root / rel
            need(
                p.is_file()
                and p.suffix == ".py"
                and p.resolve() == root.resolve() / rel,
                f"{key}: missing or unowned suite member {name}",
            )
            members[rel.as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
        covered.update(members)
        need(
            type(row["timeout"]) is int and row["timeout"] > 0,
            f"{key}: positive timeout required",
        )
        if "origin_cases" in row:
            cases = row["origin_cases"]
            need(isinstance(cases, dict) and len(cases) >= 2,
                 f"{key}: origin_cases needs at least two named input origins")
            seen = {}
            for origin, case in cases.items():
                need(isinstance(origin, str) and origin.strip() and isinstance(case, str)
                     and re.fullmatch(r"[A-Za-z_]\w*\.test_[A-Za-z0-9_]+", case),
                     f"{key}/{origin}: expected Class.test_method")
                need(case not in seen, f"{key}: {origin} and {seen.get(case)} share {case}; use distinct witnesses")
                seen[case] = origin
        out[key] = {**row, "members": members}
    discovered = {
        p.relative_to(root).as_posix()
        for p in (root / "tests").rglob("*.py")
        if p.name.startswith("test_") or p.stem.endswith("_test")
    }
    need(
        not discovered - covered,
        f"unregistered test modules: {sorted(discovered - covered)}",
    )
    return out


def source_info(root, model):
    cases = load(root / "acceptance.json")
    need(isinstance(cases, list) and cases, "independent acceptance cases required")
    names = [c["name"] for c in cases]
    need(
        all(isinstance(n, str) and n.strip() for n in names)
        and len(set(names)) == len(names),
        "acceptance case names must be unique",
    )
    surface = {}
    for e, n in model.entries.items():
        surface["entry:" + e] = {
            "node": n,
            "contract": model.nodes[n]["definition"]["input"],
        }
    for n, node in model.nodes.items():
        b = node["definition"]
        if b["kind"] == "exit":
            surface["exit:" + n] = {k: b.get(k) for k in ("input", "result", "files")}
        for event, port in b.get("events", {}).items():
            surface[f"event:{n}.{event}"] = {
                **port,
                "on_duplicate": b.get("on_duplicate", "acknowledge"),
            }
        for port, d in model.edges[n].items():
            surface[f"edge:{n}.{port}"] = {
                "next": d,
                "contract": model.nodes[d]["definition"]["input"],
            }
    files = [
        root / "workflow.json",
        root / "fixtures.json",
        root / "acceptance.json",
        root / "SKILL.md",
    ]
    for name in ("adapters.py", "test_adapters.py", "checks.json"):
        if (root / name).is_file():
            files.append(root / name)
    for folder in ("blocks", "tests", "references", "assets", "agents"):
        files.extend(
            p
            for p in sorted((root / folder).rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts
        )
    hashes = {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in files
    }
    return {
        "standard": STANDARD,
        "skill": model.spec["name"],
        "contracts": {k: digest(v) for k, v in model.contracts.items()},
        "surface": surface,
        "cases": dict(zip(names, cases)),
        "suites": suites(root),
        "sources": hashes,
        "blocks": {k: digest(v) for k, v in model.blocks.items()},
        "nodes": {
            n: digest({k: v for k, v in x.items() if k != "definition"})
            for n, x in model.nodes.items()
        },
    }


def checkpoint(info):
    return {"format": "workflow-acceptance/1", "id": digest(info), "accepted": info}


def save_baseline(path, value):
    durable(
        path,
        (
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode(),
    )


def read_baseline(value):
    need(
        value.get("format") == "workflow-acceptance/1"
        and value.get("id") == digest(value["accepted"]),
        "invalid acceptance baseline",
    )
    need(value["accepted"].get("standard") == STANDARD, "unsupported baseline standard")
    return value


def git_file(project, ref, file, *, required, acceptance=True):
    top = subprocess.run(
        ["git", "-C", str(project), "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
    )
    if top.returncode:
        need(not required, "baseline Git ref requires a Git repository")
        return None
    sha = subprocess.run(
        [
            "git",
            "-C",
            str(project),
            "rev-parse",
            "--verify",
            "--end-of-options",
            ref + "^{commit}",
        ],
        text=True,
        capture_output=True,
    )
    if sha.returncode:
        need(not required, f"unknown baseline ref {ref}")
        return None
    repo = Path(top.stdout.strip()).resolve()
    path = (project.resolve() / file).relative_to(repo).as_posix()
    q = subprocess.run(
        ["git", "-C", str(repo), "show", sha.stdout.strip() + ":" + path],
        capture_output=True,
    )
    if q.returncode:
        need(not required, f"no accepted baseline at {ref}:{path}")
        return None
    value = parse(q.stdout.decode())
    return read_baseline(value) if acceptance else value


def select_baseline(project, path, ref, required):
    need(not (path and ref), "select one baseline source")
    if path:
        p = Path(path)
        return read_baseline(load(p / BASELINE if p.is_dir() else p)), str(p)
    if ref:
        old = git_file(project, ref, BASELINE, required=True)
        need((project / BASELINE).is_file(), "tracked acceptance baseline was removed")
        return old, "git:" + ref
    old = git_file(project, "HEAD", BASELINE, required=False)
    if old:
        need((project / BASELINE).is_file(), "tracked acceptance baseline was removed")
        return old, "git:HEAD"
    if (project / BASELINE).exists():
        return read_baseline(load(project / BASELINE)), "working-tree"
    need(not required, "previously accepted baseline required")
    return None, "first acceptance"


def compare(old, new, model, changes):
    report = {
        "added": [],
        "changed": [],
        "removed": [],
        "affected_nodes": [],
        "affected_entries": [],
        "issues": [],
    }
    if not old:
        return report, []
    history = old["accepted"]
    need(history["skill"] == new["skill"], "baseline belongs to another skill")
    acknowledgement = {}
    if changes and changes.get("baseline") == old["id"]:
        acknowledgement = changes["changes"]
        need(
            isinstance(acknowledgement, dict), "changes must map exact requirement IDs"
        )

    def retired(key):
        note = acknowledgement.get(key)
        if not note:
            report["issues"].append(
                f"{key}: missing migration reason and replacement acceptance case"
            )
            return False
        fields(note, {"reason", "replacement"}, set(), key)
        need(
            isinstance(note["reason"], str)
            and note["reason"].strip()
            and note["replacement"] in new["cases"],
            f"{key}: invalid rationale or unknown replacement acceptance case",
        )
        return True

    for ref, old_hash in history["contracts"].items():
        if ref not in new["contracts"]:
            retired("contract:" + ref)
        elif old_hash != new["contracts"][ref]:
            report["issues"].append(
                f"{ref}: changed schema under the same version; allocate a new contract ID"
            )
    older = history["surface"]
    current = new["surface"]
    report["added"] = sorted(current.keys() - older.keys())
    report["removed"] = sorted(older.keys() - current.keys())
    report["changed"] = sorted(
        k for k in older.keys() & current.keys() if older[k] != current[k]
    )
    for k in report["removed"] + report["changed"]:
        retired(k)
    inherited = []
    for name, case in history["cases"].items():
        if new["cases"].get(name) != case:
            if not retired("oracle:" + name):
                inherited.append(case)
    for name, suite in history["suites"].items():
        if new["suites"].get(name) != suite:
            retired("suite:" + name)
    changed_files = sorted(
        k
        for k in history["sources"].keys() | new["sources"].keys()
        if history["sources"].get(k) != new["sources"].get(k)
    )
    changed_blocks = {
        k
        for k in history["blocks"].keys() | new["blocks"].keys()
        if history["blocks"].get(k) != new["blocks"].get(k)
    }
    changed_refs = {
        k
        for k in history["contracts"].keys() | new["contracts"].keys()
        if history["contracts"].get(k) != new["contracts"].get(k)
    }
    changed_nodes = {
        n
        for n, node in model.nodes.items()
        if node["block"] in changed_blocks or new["nodes"][n] != history["nodes"].get(n)
    }
    for n, node in model.nodes.items():
        b = node["definition"]
        refs = {
            b["input"],
            *b.get("outputs", {}).values(),
            *(p["contract"] for p in b.get("events", {}).values()),
        }
        refs.update(b[k] for k in ("item_input", "item_output") if k in b)
        if any(
            ref in changed_refs or set(model.schema_dependencies(ref)) & changed_refs
            for ref in refs
        ):
            changed_nodes.add(n)
    source_changed = any(
        k == "adapters.py" or k.startswith("blocks/") for k in changed_files
    )
    if source_changed:
        changed_nodes.update(model.nodes)
    for k in report["added"] + report["changed"] + report["removed"]:
        typ, value = k.split(":", 1)
        if typ == "entry":
            changed_nodes.add(current.get(k, older.get(k))["node"])
        else:
            changed_nodes.add(
                value.rsplit(".", 1)[0] if typ in ("edge", "event") else value
            )
    for node, b in model.nodes.items():
        if set(b["definition"].get("branches", {}).values()) & changed_blocks:
            changed_nodes.add(node)

    # Include downstream consumers and the public entries which can reach a change.
    def reach(seeds, edges):
        seen = set()
        todo = list(seeds)
        while todo:
            n = todo.pop()
            if n not in seen:
                seen.add(n)
                todo.extend(edges.get(n, ()))
        return seen

    graph = {n: list(r.values()) for n, r in model.edges.items()}
    downstream = reach(changed_nodes, graph)
    report.update(
        affected_nodes=sorted(downstream),
        affected_entries=sorted(
            e for e, n in model.entries.items() if reach([n], graph) & changed_nodes
        ),
        changed_sources=changed_files,
        changed_blocks=sorted(changed_blocks),
        changed_contracts=sorted(changed_refs),
    )
    return report, inherited


def subprocess_check(argv, cwd, timeout):
    with tempfile.TemporaryFile() as out:
        with subprocess.Popen(
            argv, cwd=cwd, stdout=out, stderr=subprocess.STDOUT, start_new_session=True
        ) as proc:
            try:
                code = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
                raise Fault(
                    f"test timed out after {timeout}s: {Path(argv[2]).name}"
                ) from exc
            out.seek(max(0, out.tell() - 6000))
            text = out.read().decode(errors="replace")
            need(code == 0, f"test exited {code}: {text[-2500:]}")
            return text


def offline_project(project, src):
    storage.snapshot(project, src)
    for name in (
        "SKILL.md",
        "fixtures.json",
        "acceptance.json",
        "checks.json",
        "requirements.txt",
    ):
        if (project / name).is_file():
            shutil.copyfile(project / name, src / name)
    for name in ("tests", "references", "assets", "agents"):
        if (project / name).is_dir():
            shutil.copytree(
                project / name,
                src / name,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
    twin = project / "test_adapters.py"
    if twin.is_file():
        shutil.copyfile(twin, src / "adapters.py")
    return src


def audit(
    project,
    trusted,
    *,
    baseline=None,
    baseline_ref=None,
    require_baseline=False,
    record=False,
    runs=(),
):
    project = Path(project).resolve()
    report = {"standard": STANDARD, "passed": False, "checks": []}

    def step(name, fn):
        try:
            value = fn()
            report["checks"].append({"id": name, "status": "pass"})
            return value
        except Exception as exc:
            report["checks"].append(
                {"id": name, "status": "fail", "error": str(exc) or type(exc).__name__}
            )
            return None

    def package():
        meta = skill_info(project)
        data = load(project / "workflow.json")
        need(meta["name"] == data["name"], "skill name differs from workflow name")
        for path in ("fixtures.json", "acceptance.json"):
            need((project / path).is_file(), f"missing {path}")
        return True

    step("package", package)

    def runtime():
        actual = runtime_hashes(project)
        need(
            load(project / MANAGED) == actual,
            "runtime differs from the project manifest",
        )
        need(
            actual == runtime_hashes(Path(trusted)),
            "runtime differs from the trusted builder release",
        )
        return True

    trusted_ok = step("runtime", runtime)

    def composition():
        model = Model(project)
        # Trusted adapter modules must be import-safe: invoking a handler owns external I/O.
        impl = storage.adapters(project)
        for name, b in model.blocks.items():
            for field in ("handler", "worker"):
                if field in b:
                    need(
                        callable(getattr(impl, b[field], None)),
                        f"{name}: missing production {field} {b[field]}",
                    )
        return model, source_info(project, model)

    built = step("composition", composition)
    inherited = []
    if built:
        model, info = built

        def compatibility():
            old, origin = select_baseline(
                project, baseline, baseline_ref, require_baseline
            )
            report["baseline"] = {"source": origin, "id": old["id"] if old else None}
            migrations = (
                load(project / "changes.json")
                if (project / "changes.json").is_file()
                else None
            )
            if migrations is not None:
                fields(migrations, {"baseline", "changes"}, set(), "change record")
            impact, extra = compare(old, info, model, migrations)
            report["impact"] = impact
            inherited.extend(extra)
            if (project / BASELINE).is_file():
                local = read_baseline(load(project / BASELINE))
                allowed = {checkpoint(info)["id"], old["id"] if old else None}
                need(
                    local["id"] in allowed,
                    "working baseline matches neither the trusted reference nor the audited project",
                )
            need(not impact["issues"], " | ".join(impact["issues"]))
            return True

        step("compatibility", compatibility)
    if built and trusted_ok:

        def behavior():
            result = verify(project, inherited_cases=inherited)
            report["tests"] = result
            impact = report.get("impact", {})
            affected = set(impact.get("affected_nodes", []))
            impact["affected_tests"] = sorted(
                {
                    test
                    for row in result["obligations"]
                    if (
                        row["requirement"][0]
                        if isinstance(row["requirement"], tuple)
                        else row["requirement"]
                    )
                    in affected
                    for test in row["tests"]
                }
            )
            need(
                result["passed"], "coverage or independent acceptance failed; see tests"
            )
            return True

        behavior_ok = step("behavior", behavior)
        if behavior_ok:
            with tempfile.TemporaryDirectory(prefix="workflow-audit-") as temp:
                base = Path(temp)
                src = offline_project(project, base / "project")

                def cli(*args):
                    return subprocess_check(
                        [
                            sys.executable,
                            "-B",
                            str(src / "scripts" / "flow.py"),
                            *map(str, args),
                        ],
                        base,
                        30,
                    )

                def entry():
                    cli("check")
                    seed = load(project / "fixtures.json")["seeds"][0]
                    run = base / "smoke"
                    view = json.loads(
                        cli("start", run, seed["entry"], json.dumps(seed["data"]))
                    )
                    need(
                        view["status"] in ("waiting", "completed"),
                        f"entry smoke: {view}",
                    )
                    cli("status", run)
                    cli("clean", run)
                    cli("delivery", run)
                    need(
                        {p.name for p in run.iterdir()} == {"delivery"},
                        "cleaned delivery is not standalone",
                    )
                    return True

                step("entry", entry)

                def extensions():
                    result = []
                    for key, row in info["suites"].items():
                        command = [sys.executable, "-B", str(src / row["file"])]
                        if "origin_cases" in row:
                            command = [sys.executable, "-B", str(src / "scripts/wfcore/origin_cases.py"),
                                       str(src / row["file"]), json.dumps(row["origin_cases"])]
                        subprocess_check(
                            command,
                            src,
                            row["timeout"],
                        )
                        result.append(key)
                        if "origin_cases" in row:
                            report.setdefault("origin_cases", {})[key] = row["origin_cases"]
                    report["extension_suites"] = result
                    return True

                step("extensions", extensions)

        def history():
            report["replayed"] = [
                replay(load(Path(run) / "work" / "state.json"), model) for run in runs
            ]
            return True

        step("replay", history)
    tested = {r["id"] for r in report["checks"]}
    for rule in RULES.keys() - tested:
        report["checks"].append(
            {
                "id": rule,
                "status": "blocked",
                "error": "prerequisite check did not pass",
            }
        )
    report["checks"].sort(key=lambda r: list(RULES).index(r["id"]))
    report["passed"] = all(r["status"] == "pass" for r in report["checks"])
    if report["passed"] and record:
        with storage.lock(project):
            fresh = source_info(project, Model(project))
            need(
                fresh == info,
                "project changed during audit; run again before recording",
            )
            save_baseline(project / BASELINE, checkpoint(info))
        report["recorded"] = checkpoint(info)["id"]
    return report
