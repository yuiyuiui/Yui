#!/usr/bin/env python3
"""Prepare neutral packet-review controls. Does not run a model or measure detection."""
import argparse
import copy
import importlib.util
import json
import random
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = importlib.util.spec_from_file_location("review_nl0", ROOT / "scripts/nl0.py")
nl0 = importlib.util.module_from_spec(MODULE)
MODULE.loader.exec_module(nl0)


def controls():
    case = ROOT / "tests/fixtures/closed-addition"
    data = nl0.validate(case / "nl0.json", case / "spec.json")
    baseline = nl0.packet(data, "R002")
    result = [(copy.deepcopy(baseline), "PASS", "complete local equality proof", None)]
    p = copy.deepcopy(baseline)
    p["inputs"][0]["statement"] = "The identity (8.3) holds."
    result.append((p, "FAIL", "input statement refers to a missing formula", "/inputs/0/statement"))
    p = copy.deepcopy(baseline)
    p["inference"]["argument"][1]["text"] = "N001 gives b=a. Applying W to F001 yields a+0=b."
    result.append((p, "FAIL", "W has no legitimate declaration or application rule", "/inference/argument/1/text"))
    p = copy.deepcopy(baseline)
    p["inference"]["argument"][1]["text"] = "N001 gives b=a. The global transfer lemma yields a+0=b."
    result.append((p, "FAIL", "the global transfer lemma is neither an input nor locally proved", "/inference/argument/1/text"))
    p = copy.deepcopy(baseline)
    p["inference"]["locals"][0].update(kind="witness", declaration="Choose c with c=a+0 and c=b.")
    p["inference"]["argument"][0]["text"] = "Choose c with c=a+0 and c=b. In particular c=a by the additive identity."
    result.append((p, "FAIL", "witness is chosen with the desired conclusion without an existence basis", "/inference/locals/0"))
    return result


def prepare(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    reviewer, owner = destination / "reviewer", destination / "owner"
    reviewer.mkdir()
    owner.mkdir()
    cases = controls()
    random.SystemRandom().shuffle(cases)
    expected = {}
    for packet, verdict, reason, location in cases:
        name = uuid.uuid4().hex + ".json"
        packet["packet_sha256"] = nl0.closure.digest(packet)
        (reviewer / name).write_text(json.dumps(packet, indent=2) + "\n")
        expected[name] = {"expected_verdict": verdict, "reason": reason, "location": location,
                          "packet_sha256": packet["packet_sha256"]}
    prompt = (
        "Audit each JSON packet using the supplied NL0 self-containment/Audit A instructions. "
        "The packet is your only mathematical input. Do not repair missing content or consult "
        "sources, other proofs, old reviews, or any owner directory. Return one JSON result per "
        "filename: {verdict: PASS|FAIL|UNVERIFIED, findings: [{location, check, explanation}]}. "
        "Locations are JSON pointers inside the packet. Judge the supplied argument, not whether "
        "you could prove its target by a different argument.\n"
    )
    (reviewer / "REQUEST.txt").write_text(prompt)
    manifest = {"status": "NOT_RUN", "purpose": "Small behavioral controls, not a performance benchmark",
                "execution": "No model or isolated reviewer has been run by this preparation script.",
                "disclosure": "Only reviewer/ plus the procedure may be disclosed; keep owner/ out of the reviewing context.",
                "expected": expected}
    (owner / "expected.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return {"status": "NOT_RUN", "prepared_cases": len(expected), "reviewer_input": str(reviewer),
            "owner_only_key": str(owner / "expected.json")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="New directory; existing data is never overwritten")
    args = parser.parse_args()
    print(json.dumps(prepare(args.out), indent=2))


if __name__ == "__main__":
    main()
