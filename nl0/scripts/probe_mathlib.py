#!/usr/bin/env python3
"""Query exact library signatures/axioms; never build or prove the target."""
import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def prepare_output(out, replace=False):
    """Never overwrite frozen source evidence without an explicit archive."""
    names=["LibraryProbe.lean","library-probe.log","library-sources.json","registry.json"]
    present=[out/name for name in names if (out/name).exists()]
    if present and not replace:
        raise FileExistsError("EVIDENCE-EXISTS: choose a new --out directory, or use --replace-existing to archive the previous query")
    out.mkdir(parents=True,exist_ok=True)
    if present:
        archive=out/"history"/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        archive.mkdir(parents=True)
        for path in present:
            shutil.copy2(path,archive/path.name)
        manifest={"files":[dict(path=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in present]}
        (archive/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
        # A failed replacement must not leave an old successful receipt active.
        for path in present:
            path.unlink()
        return str(archive)
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry", type=Path)
    parser.add_argument("--mathlib", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--replace-existing",action="store_true",
                        help="archive previous query artifacts before replacing them")
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text())
    out = args.out.resolve()
    try:
        previous_archive=prepare_output(out,args.replace_existing)
    except FileExistsError as error:
        print(json.dumps({"status":"REFUSED","error":str(error)},indent=2))
        return 1
    (out/"registry.json").write_text(json.dumps(registry,ensure_ascii=False,indent=2)+"\n")
    probe = out / "LibraryProbe.lean"
    lines = ["import Mathlib", "set_option pp.universes true", "set_option pp.explicit true"]
    for item in registry:
        name = item["declaration"]
        lines += [f'#eval IO.println "BEGIN_SIGNATURE:{item["id"]}"', f"#check @{name}",
                  f'#eval IO.println "BEGIN_AXIOMS:{item["id"]}"', f"#print axioms {name}",
                  f'#eval IO.println "END_SOURCE:{item["id"]}"']
    probe.write_text("\n".join(lines) + "\n")
    command = ["lake", "env", "lean", "-DmaxHeartbeats=0", str(probe)]
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(command, cwd=args.mathlib, capture_output=True, text=True)
    (out / "library-probe.log").write_text(result.stdout + result.stderr)
    if result.returncode:
        print(json.dumps({"status": "FAILED", "exit_code": result.returncode,
                          "log": str(out / "library-probe.log")}, indent=2))
        return 1
    sources = {}
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=args.mathlib, text=True).strip()
    for item in registry:
        key = item["id"]
        signature = result.stdout.split(f"BEGIN_SIGNATURE:{key}\n", 1)[1].split(f"BEGIN_AXIOMS:{key}\n", 1)[0].strip()
        axioms = result.stdout.split(f"BEGIN_AXIOMS:{key}\n", 1)[1].split(f"END_SOURCE:{key}\n", 1)[0].strip()
        source_path = Path(item["module"].replace(".", "/") + ".lean")
        source = args.mathlib / source_path
        data = dict(item)
        data.update({"signature": signature, "axioms": axioms,
                     "source_path": str(source_path),
                     "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                     "mathlib_commit": commit})
        sources[key] = data
    report = {"probe_version": 1, "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
              "command": command, "cwd": str(args.mathlib), "exit_code": result.returncode,
              "lean_version": subprocess.check_output(["lake", "env", "lean", "--version"], cwd=args.mathlib, text=True).strip(),
              "mathlib_commit": commit, "sources": sources,
              "previous_artifacts_archive":previous_archive}
    (out / "library-sources.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": "PASSED", "sources": len(sources), "report": str(out / "library-sources.json")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
