"""Stage only explicitly declared source evidence for a clean reviewer."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def stage_external(case, proposition, destination):
    """No network/browser access. Binary access failures remain visible, not PASS."""
    case=Path(case).resolve();destination=Path(destination)
    source=proposition['source'];records=[]
    primary={(e['path'],e['sha256']) for e in source['primary_evidence']}
    for index,evidence in enumerate(source['evidence'],1):
        path=(case/evidence['path']).resolve()
        if not path.is_relative_to(case) or not path.is_file():raise ValueError('Declared external evidence escapes/misses its case')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=evidence['sha256']:raise ValueError('External evidence changed')
        name=proposition['id']+f'-source-{index:03d}.txt'
        record={'source':evidence,'primary':(evidence['path'],evidence['sha256']) in primary,'readback':name}
        try:
            text=path.read_bytes().decode('utf-8')
            if '\x00' in text:raise UnicodeError('Binary source')
            record['readback_kind']='EXACT_UTF8_BYTES'
        except UnicodeError:
            converter=shutil.which('pdftotext')
            if path.suffix.lower()=='.pdf' and converter:
                record.update(readback_kind='PDF_TEXT_EXTRACTION',converter=str(converter),
                    converter_sha256=hashlib.sha256(Path(converter).read_bytes()).hexdigest())
                try:
                    result=subprocess.run([converter,'-layout',str(path),'-'],capture_output=True)
                    text=result.stdout.decode('utf-8',errors='replace')
                    if result.returncode or not text.strip():raise ValueError(result.stderr.decode('utf-8',errors='replace')[:1000] or 'Empty PDF extraction')
                except (OSError,ValueError,subprocess.TimeoutExpired) as error:
                    text='UNVERIFIED: no usable text extraction for this declared primary document.\n'
                    record.update(readback_kind='UNAVAILABLE',error=str(error)[:1000])
            else:
                text='UNVERIFIED: this declared binary source has no supported text readback. Its citation checks remain unverified.\n'
                record['readback_kind']='UNAVAILABLE'
        (destination/name).write_text(text)
        record['readback_sha256']=hashlib.sha256((destination/name).read_bytes()).hexdigest()
        records.append(record)
    return {'id':proposition['id'],'source_contract':source,'documents':records,
            'scope':'Staged access evidence only. Document identity, occurrence, statement, context, eligibility and applications still require actual review.'}
