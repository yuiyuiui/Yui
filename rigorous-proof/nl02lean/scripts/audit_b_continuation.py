"""Explicit fresh Audit B on an existing checked native build; no new proof or compiler run."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'nl0/scripts'))
from controller_common import bind, write
from execution_health import StageFailure
import audit_b
import audit_b_review as reviewer


def run(original, out, *, budget=None):
    original,out=Path(original).resolve(),Path(out).resolve()
    out.mkdir(parents=True,exist_ok=False)
    before=bind(original/'Proof.lean')['sha256']
    audit_b.prepare_review_reuse(original,out/'native')
    reviewer.prepare(out/'native',out/'review')
    reviewer.run(out/'review',budget=budget)
    result=reviewer.collect(out/'review')
    unchanged=before==bind(original/'Proof.lean')['sha256']==bind(out/'native/Proof.lean')['sha256']
    if not unchanged:raise ValueError('Inherited proof bytes changed')
    checked=audit_b.check(out/'native',out/'review/review.json') if result['all_checks_passed'] else None
    report={'status':'AUDIT-B-PASSED' if checked else result['review_status'],
        'actual_audit_b_verdict':'PASS' if checked else 'FAIL_OR_UNVERIFIED',
        'native_checks_rerun':False,'semantic_review_inherited':False,
        'original_and_copied_proof_unchanged':True,'check':checked,'review':result}
    write(out/'result.json',report)
    return report
