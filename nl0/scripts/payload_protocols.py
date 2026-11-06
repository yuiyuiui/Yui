"""Reusable author payload boundaries; domain validators own semantic checks."""
from artifact_protocol import obj, array, choice, literal, TEXT, STRING


OBJECT = {'type':'object','additionalProperties':True}
POSITIVE = {'type':'integer','minimum':1}
POINTER = {'type':'string','pattern':'^/'}


def edit_schema():
    branches=[]
    for op in ('add','remove','replace','test','replace_text','replace_lines'):
        fields={'op':literal(op),'path':POINTER}
        if op=='replace_text':fields.update(old=STRING,new=STRING)
        elif op=='replace_lines':
            fields.update(start_line=POSITIVE,end_line={'type':'integer','minimum':0},text=STRING,text_sha256=TEXT)
        elif op!='remove':fields['value']={}
        branches.append(obj(fields))
    return choice(*branches)


def editable(full, *, source_uses=False):
    patches=array(edit_schema(),minItems=1)
    choices=[full,obj({'accept_candidate':POSITIVE}),
             obj({'base_candidate':POSITIVE,'patches':patches}),
             obj({'base_input':TEXT,'patches':patches,'reset_base':literal(True)},required=['base_input','patches'])]
    if source_uses:
        choices.append(obj({'base_candidate':POSITIVE,'source_uses':array(source_use_schema(),minItems=1)}))
    return choice(*choices)


def parameter_schema():
    return obj({'name':TEXT,'type':TEXT,'binder_kind':{'enum':['explicit','implicit','instance']}},
               required=['name','type'])


def source_use_schema():
    return obj({'inference':TEXT,'at':TEXT,'input':TEXT,'bindings':TEXT,
                'hypothesis_checks':array(TEXT),'id':TEXT},
               required=['inference','at','input','bindings','hypothesis_checks'])


def obstacle_schema(kind):
    statuses=['SUBSTANTIVE_GAP','SUSPECTED_GAP','MISSING_SOURCE_STATEMENT','INPUT_CONFLICT']
    if kind!='nl0':statuses.append('SOURCE_UNAVAILABLE')
    return obj({'status':{'type':'string','enum':statuses},
                **{key:TEXT for key in ['location','explanation','basis','partial_progress']}})
