"""Observable proof structure for authors selecting natural, independently provable cuts."""
from collections import Counter


def local(inference):
    paragraphs = inference['argument']
    independent = [s['id'] for s in paragraphs if not s.get('uses_local') and
                   not s.get('introduces') and not s.get('discharges') and not s.get('produces')]
    return {'paragraphs':len(paragraphs),'source_applications':len(inference.get('applications',[])),
            'local_binders':len(inference.get('locals',[])),'paragraphs_without_local_binders':independent,
            'review':'Consider separate conclusions when distinct arguments can be checked from these inputs. Keep local witnesses and the final implication in scope. Explain any substantial retained block in the dependency check.'}


def jobs(nodes, order):
    depths={}
    loads={}
    consumers=Counter(i for row in nodes.values() for i in row['inputs'] if i in nodes)
    for key in order:
        row=nodes[key]
        previous=[i for i in row['inputs'] if i in nodes]
        depths[key]=1+max((depths[i] for i in previous),default=0)
        loads[key]=len(set(row['source_steps']))+max((loads[i] for i in previous),default=0)
    return {'levels':dict(sorted(Counter(depths.values()).items())),
            'jobs':{k:{'dependency_depth':depths[k],'consumers':consumers[k],
                       'paragraphs_on_longest_chain':loads[k]} for k in order},
            'review':'Inspect the longest dependency chains and shared consumers. Split independent mathematical results with stable types, and keep tightly coupled local arguments together.'}
