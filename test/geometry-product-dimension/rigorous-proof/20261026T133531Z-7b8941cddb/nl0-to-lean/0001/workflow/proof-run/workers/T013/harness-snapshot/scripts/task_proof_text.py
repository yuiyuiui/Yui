"""Literal serialization of selected task proof/definition/H text; no new premise."""
from __future__ import annotations

import hashlib


def materialize(graph, documents, *, spec=None):
    """Expand explicitly selected own-input text atomically, without interpreting it."""
    bindings=[]
    changes=[]
    requests=[]
    hypotheses=spec.get('hypotheses',[]) if isinstance(spec,dict) else []
    if isinstance(hypotheses,list):
        for i,hypothesis in enumerate(hypotheses):
            if isinstance(hypothesis,dict) and isinstance(hypothesis.get('statement'),dict):
                requests.append((hypothesis,'statement',f'/spec/hypotheses/{i}/statement'))
    definitions=spec.get('definitions',[]) if isinstance(spec,dict) else []
    if isinstance(definitions,list):
        for i,definition in enumerate(definitions):
            if isinstance(definition,dict) and isinstance(definition.get('definition'),dict):
                requests.append((definition,'definition',f'/spec/definitions/{i}/definition'))
    inferences=graph.get('inferences',[]) if isinstance(graph,dict) else []
    if not isinstance(inferences,list):inferences=[]
    for i,inference in enumerate(inferences):
        if not isinstance(inference,dict) or not isinstance(inference.get('argument'),list):continue
        for j,paragraph in enumerate(inference['argument']):
            if not isinstance(paragraph,dict) or not isinstance(paragraph.get('text'),dict):continue
            requests.append((paragraph,'text',f'/graph/inferences/{i}/argument/{j}/text'))
    for target,field,location in requests:
        request=target[field]
        if set(request)!={'from_task','start_line','end_line'}:
            raise ValueError('TASK_TEXT: '+location+' expects exactly from_task, start_line and end_line')
        identifier,start,end=request['from_task'],request['start_line'],request['end_line']
        if not isinstance(identifier,str) or identifier not in documents:
            raise ValueError('TASK_TEXT: '+location+' may copy only a declared same-stage task input ID')
        source=documents[identifier]
        if not isinstance(source,str):raise ValueError('TASK_TEXT: source is not frozen UTF-8 text')
        lines=source.splitlines(keepends=True)
        if type(start) is not int or type(end) is not int or not 1<=start<=end<=len(lines):
            raise ValueError('TASK_TEXT: '+location+' needs positive inclusive line bounds within '+str(len(lines))+' source lines')
        text=''.join(lines[start-1:end])
        if not text.strip():raise ValueError('TASK_TEXT: the selected proof/definition/hypothesis text is empty')
        bindings.append({'path':location,'from_task':identifier,'start_line':start,'end_line':end,
            'input_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'text_sha256':hashlib.sha256(text.encode()).hexdigest()})
        changes.append((target,field,text))
    for target,field,text in changes:target[field]=text
    return bindings
