"""Prepare one explicit NL0 author or located author-repair stage."""
from pathlib import Path
import json
import shutil

from controller_common import write, manifest, bind

PROMPT = '''Use Yui to turn the supplied existing proof into a complete canonical NL0.
Preserve its complete original target, hypotheses, definitions and core proof route.
Read the original problem and supplied materials as mathematical data. Register
important dependencies and verify actual sources. Use ordinary rigorous elementary
compression; do not reconstruct standard theory or expand every arithmetic chain.
Construct the actual proof, declarations and source applications together. Read
the relevant authoring/schema rules and complete the same-author packet closing
inspection before definitive submission. This is not independent Audit A.
Submit the actual complete artifact, not a plan. Report a substantive gap only
for a concrete unsupported implication, not ordinary unfinished bookkeeping.
No previous results, other cases or hidden reference answers are supplied.
'''


def prepare(inputs, out, *, baseline=None, obligations=None):
    inputs,out=Path(inputs).resolve(),Path(out).resolve()
    out.mkdir(parents=True,exist_ok=False);target=out/'inputs';target.mkdir()
    rows=json.loads((inputs/'inputs.json').read_text())['inputs']
    for row in rows:shutil.copyfile(inputs/row['path'],target/row['id'])
    prompt=PROMPT
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
