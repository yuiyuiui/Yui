"""Review and freeze one named piece of content, on the actual outcome taken."""

from .protocol import digest, fields, need, symbol


def declarations(block, where):
    rules = block["content"]
    need(isinstance(rules, dict) and rules, f"{where}: content needs named outcomes")
    for port, rule in rules.items():
        need(port in block["outputs"], f"{where}: content rule on unknown outcome {port}")
        fields(rule, {"subject", "action", "path"}, set(), f"{where}.{port}")
        symbol(rule["subject"], where)
        need(rule["action"] in ("review-pass", "review-fail", "freeze", "freeze-reviewed", "revise"),
             f"{where}.{port}: invalid content action")
        need(isinstance(rule["path"], list) and all(isinstance(k, str) and k for k in rule["path"]),
             f"{where}.{port}: path must list object keys (empty selects the whole output)")


def transition(state, action, where):
    if action == "revise":
        return "draft"
    if action in ("review-pass", "review-fail"):
        need(state not in ("frozen", "frozen-approved"), f"{where}: review after freeze; revise into new content first")
        return "approved" if action == "review-pass" else "rejected"
    if action == "freeze-reviewed" or state == "rejected":
        need(state in ("approved", "frozen-approved"), f"{where}: this version needs a passing review before freeze")
    return "frozen-approved" if state in ("approved", "frozen-approved") else "frozen"


def check_routes(model):
    # Explore one subject at a time; independent subjects never multiply the state space.
    subjects = {rule["subject"] for block in model.blocks.values() for rule in block.get("content", {}).values()}
    for subject in sorted(subjects):
        pending = [(node, "draft") for node in model.entries.values()]
        visited = set()
        while pending:
            node, state = pending.pop()
            if (node, state) in visited:
                continue
            visited.add((node, state))
            rules = model.nodes[node]["definition"].get("content", {})
            for port, dest in model.edges[node].items():
                rule = rules.get(port)
                next_state = state
                if rule and rule["subject"] == subject:
                    next_state = transition(state, rule["action"], f"{node}.{port} ({subject})")
                pending.append((dest, next_state))


def record(ledger, rule, output, where):
    if rule is None:
        return
    value = output
    for key in rule["path"]:
        need(isinstance(value, dict) and key in value, f"{where}: missing content field {key!r}")
        value = value[key]
    revision = digest(value)
    subject, action = rule["subject"], rule["action"]
    where = f"{where} ({subject})"
    prior = ledger.get(subject, {})
    frozen = prior.get("frozen", [])
    current = prior.get("revision") == revision
    state = prior["state"] if current else "draft"
    if not current and revision in frozen:
        state = "frozen"
    if action == "revise":
        need(not current and revision not in frozen, f"{where}: revision must supply new, unfrozen content")
    result = transition(state, action, where)
    if result in ("frozen", "frozen-approved") and revision not in frozen:
        frozen = [*frozen, revision]
    ledger[subject] = {"revision": revision, "state": result, "frozen": frozen}
