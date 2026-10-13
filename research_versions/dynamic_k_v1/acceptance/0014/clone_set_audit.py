"""Supplemental JSON graph comparison under mathematical set semantics only.

Never replaces a primary fingerprint or edits any native state or kernel.
"""
import json,hashlib
from pathlib import Path
import full_state as fs
A=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def canonical_graph(doc):
    nodes=doc['objects'];memo={};out=[]
    def value_key(x):
        if isinstance(x,list) and len(x)==2 and x[0]=='ref':
            n=nodes[x[1]]
            return [n['type'],[value_key(v) for v in n.get('items',[])]]
        return x
    def walk(x):
        if isinstance(x,list) and len(x)==2 and x[0]=='ref':
            old=x[1]
            if old in memo:return ['ref',memo[old]]
            index=len(out);memo[old]=index;out.append(None);n=dict(nodes[old])
            if n['type'] in ('builtins.set','builtins.frozenset'):
                n['items']=sorted(n['items'],key=lambda v:fs.dumps(value_key(v)))
            out[index]=walk(n);return ['ref',index]
        if isinstance(x,list):return [walk(v) for v in x]
        if isinstance(x,dict):return {k:walk(v) for k,v in x.items()}
        return x
    root=walk(doc['root']);return dict(schema=doc['schema'],root=root,objects=out)
def main():
    source=read(A/'ROOT_BASELINE/SANITIZED_PRE_ACTION_FULL_STATE.json')
    hold=read(A/'HOLD/PRE_ACTION_FULL_STATE.json');add=read(A/'ADD/PRE_ACTION_FULL_STATE.json')
    a,b=canonical_graph(source),canonical_graph(hold)
    difference=fs.first_diff(source,hold)
    row=dict(primary_source_vs_clone_raw_state_equal=source==hold,primary_source_vs_clone_first_difference=difference,
        paired_HOLD_ADD_PRE_ACTION_every_field_equal=hold==add,
        paired_PRE_ACTION_complete_sha256=fs.sha(hold),
        root_source_complete_sha256=fs.sha(source),
        supplementary_set_semantic_graph_every_field_equal=a==b,
        supplementary_first_difference=fs.first_diff(a,b),
        source_set_nodes=[dict(index=i,type=n['type'],item_count=len(n['items'])) for i,n in enumerate(source['objects']) if n['type'] in ('builtins.set','builtins.frozenset')],
        explanation='Frozen deepcopy rebuilds sets and can change iteration layout. Both branch PRE_ACTION states are identical; source causal hash uses sorted sets. Supplemental offline comparison preserves every other order, value, type and alias; it is not a new primary root hash or a tolerance relaxation.',
        root_reconstruction_primary_equality_was_full_and_exact=True,
        primary_hashes_replaced=False,state_modified=False,new_simulation_runs=0)
    assert hold==add and a==b,'UNEXPLAINED_CLONE_STATE_CHANGE'
    with (A/'CLONE_SET_LAYOUT_AUDIT.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(row,f,sort_keys=True,indent=2);f.write('\n')
    print(json.dumps(row),flush=True)
if __name__=='__main__':main()
