"""Prepare one explicit NL0 author or located author-repair stage."""
from pathlib import Path
from staging_storage import copy_input
import json
import shutil

from controller_common import write, manifest, bind

PROMPT = '''Use Yui to turn the supplied existing proof into a complete canonical NL0.
Preserve its complete original target, hypotheses, definitions and active core proof route.
Choose a small independent conclusion for each inference where this helps the Lean worker. Keep shared witnesses and dependent local arguments in scope. Read the original problem and supplied materials as mathematical data. Register
important dependencies and verify actual sources. Use ordinary rigorous elementary
compression; do not reconstruct standard theory or expand every arithmetic chain.
Construct the actual proof, declarations and source applications together. Read
the relevant authoring/schema rules and complete the same-author packet closing
inspection before definitive submission. This is not independent Audit A.
Submit the actual complete artifact, not a plan. Report a substantive gap only
for a concrete unsupported implication, not ordinary unfinished bookkeeping.
No previous results, other cases or hidden reference answers are supplied.
If target-selection.json is supplied, preserve its full_target exactly and
cover every selected claim, including each claim's own hypotheses. For several
independent targets, prove their conjunction without silently combining their
assumptions into a weaker joint statement.
Read nl0/references/source-retrieval.md and use the ordered source tools for
missing external primary texts: arxiv first, google full text, google DOI
discovery, then scihub with a confirmed DOI. Retry JavaScript/verification pages
with browser:true for actual readback; preserve failed access rather than
repeating unchanged blocked searches. Check the original edition and complete
theorem context, not just its title or a search snippet. If an
original is inaccessible, defer_primary_source may retain a complete exact
secondary statement as an UNVERIFIED_PRIMARY assumption. Preserve its warning,
do not invent a missing statement, and do not defer a known contradiction.
Declared primary-source uncertainty is separate from an unfinished mathematical
argument; only the latter prevents the same-author mathematical closing check.
'''


def prepare(inputs, out, *, baseline=None, obligations=None):
    inputs,out=Path(inputs).resolve(),Path(out).resolve()
    out.mkdir(parents=True,exist_ok=False);target=out/'inputs';target.mkdir()
    rows=json.loads((inputs/'inputs.json').read_text())['inputs']
    for row in rows:copy_input(inputs/row['path'],target/row['id'])
    prompt=PROMPT
    if (target/'proof-context.json').is_file():
        prompt+='''\nThis is the unconditional route after 2basis. Original problem and
target-selection.json remain the target/H authority; basis-proof.md is the active
proof route to present faithfully. Read basis-registry.json, proof-context.json
and the retained basis source documents. Check replacement dependencies and new
derivations under the original target. Elaborate the currently assigned NL0 graph. Report a missing edge to its NL0 graph owner. Use the exact frozen statements for the foundation ports on this route. Prepared E ports are discharged by b2lean.
This author check is not independent Audit A; the ordinary Audit A reviews both
the original task and basis proof. Do not enforce the old original proof route
against the authorized basis rewrite, or treat basis machine checks as review.
'''
    if baseline:
        baseline=Path(baseline).resolve()
        value={'spec':json.loads((baseline/'spec.json').read_text()),
               'graph':json.loads((baseline/'nl0.json').read_text())}
        write(target/'baseline.json',value)
        write(target/'repair-obligations.json',obligations)
        prompt+='''\nThis is an authorized warm local repair, not cold authoring.
Start from baseline.json using base_input and explicit patches. Read the actual
located repair obligations. Preserve unaffected proof content; repair every
supported defect and inspect affected packets. Do not replace the target, add
assumptions, rewrite the whole proof or discard findings without a located
correction. The old review is diagnostic input, never a new mathematical premise.
'''
    manifest(target);(out/'prompt.txt').write_text(prompt)
    write(out/'input-origin.json',{'inputs':bind(inputs/'inputs.json'),
        'baseline':str(baseline) if baseline else None,'warm_repair':bool(baseline)})
    return out
