"""Resolve and bind requested targets before dispatch; never infer a proof."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re

VERSION='yui-target-selection-1'
HEADING=re.compile(r'(?m)^[ \t]*(Theorem|Proposition|Corollary|定理|命题|推论)[ \t]+'
    r'([A-Z]?\d+(?:\.\d+)*|[A-Z])(?=[ \t]*(?:\.(?!\d)|[(:：．（])|[ \t]+(?:Let|Suppose|Assume|If)\b)',re.I)


def text(path):
    path=Path(path).expanduser().resolve(strict=True)
    if path.is_dir():path=path/'problem.md'
    if path.suffix.lower()!='.pdf':return path.read_text(encoding='utf-8')
    import shutil,subprocess
    if shutil.which('pdftotext'):
        result=subprocess.run(['pdftotext','-layout',str(path),'-'],capture_output=True,text=True)
        if result.returncode:raise ValueError('PDF extraction failed: '+result.stderr[-1000:])
        value=result.stdout
    else:
        try:
            from pypdf import PdfReader
        except ImportError as error:
            raise ValueError('PDF needs pdftotext or pypdf; supply a checked text transcription') from error
        try:value='\n\n'.join(page.extract_text() or '' for page in PdfReader(path).pages)
        except Exception as error:raise ValueError('Unreadable PDF text; supply a checked transcription: '+str(error)) from error
    if not value.strip():raise ValueError('No readable PDF text; a checked transcription is required')
    return value


def inspect(path):
    path=Path(path).expanduser().resolve(strict=True)
    if path.is_dir():path=path/'problem.md'
    value=text(path);matches=list(HEADING.finditer(value));candidates=[]
    for i,m in enumerate(matches):
        end=matches[i+1].start() if i+1<len(matches) else len(value)
        tail=value[m.start():end]
        stop=re.search(r'(?m)^[ \t]*(?:Proof\b|证明[.：:]|Remark\b|注[.：:]|\d+(?:\.\d+)*[ \t]+[A-Za-z])',tail)
        if stop:tail=tail[:stop.start()]
        label=(m.group(1)+' '+(m.group(2) or '')).strip()
        candidates.append({'id':str(i+1),'label':label,'start_line':value.count('\n',0,m.start())+1,
                           'statement_excerpt':tail.strip()[:8000],'delimited':bool(stop) and len(tail)<=8000})
    # Heading detection is an index, not a semantic claim that every hypothesis
    # was repeated in that block. The calling skill reads surrounding context.
    return {'version':VERSION,'document':{'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()},
            'candidates':candidates,'status':'TARGET_SELECTION_REQUIRED' if len(candidates)>1 else 'TARGET_REVIEW_REQUIRED',
            'needs_user_input':None if len(candidates)>1 else False,
            'question':'Which complete theorem(s) should be formalized? Select their labels or supply the complete intended statement.',
            'boundary':'Read surrounding assumptions. Labels and extraction alone do not establish a complete mathematical target.'}


def resolve(path, *, requested=None, selection_file=None):
    view=inspect(path)
    if requested is not None and selection_file is not None:raise ValueError('Choose --target or --target-file')
    if selection_file:
        selection=json.loads(Path(selection_file).read_text())
        if selection.get('version')!=VERSION or selection.get('document')!=view['document']:
            raise ValueError('Target selection belongs to different document bytes')
        validate(selection)
        return selection
    if requested:
        labels=[s.strip() for s in requested.split(';') if s.strip()]
        selected=[]
        for label in labels:
            found=[c for c in view['candidates'] if label.casefold() in {c['id'].casefold(),c['label'].casefold()}]
            if len(found)==1:selected.append(found[0])
            elif re.fullmatch(r'(?:theorem|proposition|corollary|定理|命题|推论)?\s*[A-Z]?\d+(?:\.\d+)*',label,re.I):
                return {**view,'status':'TARGET_SELECTION_REQUIRED','unresolved_selection':label}
            else:
                return select(path,[{'id':'explicit','label':'Explicit requested target','statement':requested,'start_line':None}],basis='explicit_statement')
        return {**view,'status':'TARGET_REVIEW_REQUIRED','needs_user_input':False,'selected_labels':[c['label'] for c in selected]}
    return view


def select(path,targets,*,basis='caller_readback'):
    view=inspect(path);selected=targets
    if not isinstance(selected,list) or not selected:raise ValueError('Select at least one complete target')
    statements=[c['statement'].strip() for c in selected]
    result={'version':VERSION,'document':view['document'],'status':'SELECTED',
            'basis':basis,
            'targets':[{k:c[k] for k in ('id','label','statement','start_line')} for c in selected],
            'full_target':statements[0] if len(statements)==1 else '\nAND\n'.join('('+s+')' for s in statements)}
    validate(result);return result


def validate(value):
    if value.get('version')!=VERSION or value.get('status')!='SELECTED':raise ValueError('Select the target before dispatch')
    if not isinstance(value.get('full_target'),str) or not value['full_target'].strip():raise ValueError('Empty target')
    if not isinstance(value.get('targets'),list) or not value['targets']:raise ValueError('Missing selected targets')
    ids=[]
    for item in value['targets']:
        if not all(isinstance(item.get(k),str) and item[k].strip() for k in ('id','label','statement')):
            raise ValueError('Every selected target needs its complete statement and identity')
        line=item.get('start_line')
        if line is not None and (type(line) is not int or line<=0):raise ValueError('Invalid target source line')
        ids.append(item['id'])
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate selected target')
    statements=[item['statement'].strip() for item in value['targets']]
    expected=statements[0] if len(statements)==1 else '\nAND\n'.join('('+s+')' for s in statements)
    if value['full_target']!=expected:raise ValueError('Full target differs from the selected complete statements')
    document=value.get('document',{});path=Path(document.get('path',''))
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=document.get('sha256'):
        raise ValueError('Original target document changed')
    return value
