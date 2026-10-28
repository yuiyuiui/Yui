#!/usr/bin/env python3
"""Replay functional checks without changing canonical proof/source evidence."""
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


CASE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[4]
RESULTS = CASE / "results"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    RESULTS.mkdir(exist_ok=True)
    stages = []
    started = datetime.now(timezone.utc).isoformat()
    summary_path = RESULTS / "summary.json"
    if summary_path.exists():
        archives = CASE / "history/smoke-runs"
        archives.mkdir(parents=True, exist_ok=True)
        archive_name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ.previous-summary.json")
        (archives / archive_name).write_bytes(summary_path.read_bytes())
    summary_path.write_text(json.dumps({"status": "RUNNING", "started_at": started}, indent=2) + "\n")
    commands = [
        ("skill-validation", ["/Users/syyui/.codex/bin/validate-skill", str(ROOT)]),
        ("graph-check", [sys.executable, str(ROOT / "nl0/scripts/nl0.py"), "check", str(CASE / "nl0.json"),
                         "--spec", str(CASE / "spec.json"), "--audit", str(CASE / "audit-a.json")]),
        ("render", [sys.executable, str(ROOT / "nl0/scripts/nl0.py"), "render", str(CASE / "nl0.json"),
                    "--spec", str(CASE / "spec.json"), "--out", str(CASE / "views")]),
        ("R015.packet", [sys.executable, str(ROOT / "nl0/scripts/nl0.py"), "packet", str(CASE / "nl0.json"),
                         "--spec", str(CASE / "spec.json"), "--audit", str(CASE / "audit-a.json"),
                         "--inference", "R015"]),
        ("tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]),
    ]
    for name, command in commands:
        clock = time.monotonic()
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        suffix = ".json" if name in {"graph-check", "render", "R015.packet"} else ".log"
        (RESULTS / (name + suffix)).write_text(result.stdout + result.stderr)
        stages.append({"stage": name, "command": command, "exit_code": result.returncode,
                       "elapsed_seconds": time.monotonic() - clock})
        if result.returncode:
            failure = {"status": "FAILED", "started_at": started,
                       "finished_at": datetime.now(timezone.utc).isoformat(),
                       "failed_stage": name, "stages": stages}
            (RESULTS / "failed-run.json").write_text(json.dumps(failure, indent=2) + "\n")
            summary_path.write_text(json.dumps(failure, indent=2) + "\n")
            print(json.dumps({"status": "FAILED", "stage": name}, indent=2))
            return 1
    baseline = json.loads((CASE / "evidence/baseline.json").read_text())
    changed = [item["path"] for item in baseline["protected_files"]
               if not Path(item["path"]).is_file() or sha(item["path"]) != item["sha256"]]
    runtime_link = str(Path("/Users/syyui/.codex/skills/rigorous-proof-development").resolve())
    candidate_links = [str(path) for path in [Path("/Users/syyui/.codex/skills/rigorous-proof-new"),
                                             Path("/Users/syyui/.claude/skills/rigorous-proof-new")]
                       if (path.exists() or path.is_symlink()) and path.resolve() == ROOT.resolve()]
    protection = {"protected_files": len(baseline["protected_files"]), "changed": changed,
                  "original_runtime_link_unchanged": runtime_link == baseline["original_runtime_link"],
                  "candidate_installed": bool(candidate_links), "candidate_runtime_links": candidate_links}
    (RESULTS / "protection.json").write_text(json.dumps(protection, ensure_ascii=False, indent=2) + "\n")
    require_unchanged = not changed and protection["original_runtime_link_unchanged"] and not candidate_links
    test_log = (RESULTS / "tests.log").read_text()
    count = int(re.search(r"Ran (\d+) tests? in", test_log).group(1))
    graph = json.loads((RESULTS / "graph-check.json").read_text())
    summary = {"status": "FUNCTIONAL-SMOKE-PASSED" if require_unchanged else "PROTECTED-INPUT-DRIFT",
               "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
               "propositions": graph["propositions"], "inferences": graph["inferences"], "kinds": graph["kinds"],
               "tests_passed": count, "tests_total": count,
               "mechanical_audit_record": graph["audit_status"],
               "recorded_mathematical_audit": "DRAFT-AUDIT-PASSED by the disclosed same-context reviewer",
               "independent_audit": False, "mathematics_automatically_verified": False,
               "new_lean_target_built": False, "isolation_test": False, "speed_benchmark": False,
               "protected_inputs_unchanged": require_unchanged,
               "graph_sha256": graph["graph_sha256"], "spec_sha256": graph["spec_sha256"],
               "stages": stages}
    (RESULTS / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    artifacts = []
    for path in sorted(ROOT.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path != RESULTS / "artifacts.json":
            artifacts.append({"path": str(path.relative_to(ROOT)), "sha256": sha(path)})
    (RESULTS / "artifacts.json").write_text(json.dumps({"algorithm": "sha256", "files": artifacts}, indent=2) + "\n")
    print(json.dumps({key: value for key, value in summary.items() if key != "stages"}, ensure_ascii=False, indent=2))
    return 0 if require_unchanged else 1


if __name__ == "__main__":
    raise SystemExit(main())
