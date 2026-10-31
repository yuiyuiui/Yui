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
    index_path=destination/'source-readback-index.json'
    readbacks=json.loads(index_path.read_text()) if index_path.is_file() else {}
    primary={(e['path'],e['sha256']) for e in source['primary_evidence']}
    for index,evidence in enumerate(source['evidence'],1):
        path=(case/evidence['path']).resolve()
        if not path.is_relative_to(case) or not path.is_file():raise ValueError('Declared external evidence escapes/misses its case')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=evidence['sha256']:raise ValueError('External evidence changed')
        name='source-'+evidence['sha256']+'.txt'
        record={'source':evidence,'primary':(evidence['path'],evidence['sha256']) in primary,'readback':name}
        cached=readbacks.get(evidence['sha256'])
        if cached is not None:
            staged=destination/name
            if (cached.get('readback')!=name or not staged.is_file()
                    or hashlib.sha256(staged.read_bytes()).hexdigest()!=cached.get('readback_sha256')):
                raise ValueError('Shared source readback changed')
            records.append({**record,**cached})
            continue
        try:
            raw=path.read_bytes()
            if path.suffix.lower()=='.pdf' or raw.startswith(b'%PDF-'):raise UnicodeError('PDF document')
            text=raw.decode('utf-8')
            if '\x00' in text:raise UnicodeError('Binary source')
            record['readback_kind']='EXACT_UTF8_BYTES'
        except UnicodeError:
            converter=shutil.which('pdftotext')
            if path.suffix.lower()=='.pdf':
                try:
                    from target_selection import text as document_text
                    text=document_text(path)
                    record.update(readback_kind='PDF_TEXT_EXTRACTION',converter=str(converter) if converter else 'pypdf')
                    if converter:record['converter_sha256']=hashlib.sha256(Path(converter).read_bytes()).hexdigest()
                except (OSError,ValueError,subprocess.TimeoutExpired) as error:
                    text='UNVERIFIED: no usable text extraction for this declared primary document.\n'
                    record.update(readback_kind='UNAVAILABLE',error=str(error)[:1000])
            else:
                text='UNVERIFIED: this declared binary source has no supported text readback. Its citation checks remain unverified.\n'
                record['readback_kind']='UNAVAILABLE'
        (destination/name).write_text(text)
        record['readback_sha256']=hashlib.sha256((destination/name).read_bytes()).hexdigest()
        readbacks[evidence['sha256']]={k:v for k,v in record.items() if k not in {'source','primary'}}
        index_path.write_text(json.dumps(readbacks,ensure_ascii=False,indent=2)+'\n')
        records.append(record)
    return {'id':proposition['id'],'source_contract':source,'documents':records,
            'scope':'Staged access evidence only. Document identity, occurrence, statement, context, eligibility and applications still require actual review.'}
