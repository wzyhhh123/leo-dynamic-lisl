"""Explain the single occupied-catalog REPLACE rejection, without a rescan."""
import json,sys
from pathlib import Path
V=Path(__file__).resolve().parents[2];P=V.parents[1];A=Path(__file__).parent
sys.path[:0]=[str(V),str(P/'src')]
from runtime.n2_actions import Add,Replace,Setup,LinkRef,ActionValidator,action_key
from runtime.n2_binding import N2EvidenceBinding
from runtime.n2_physical import ReplayableSgp4Model,Sgp4PhysicalGuard,N2PhysicalLayer
from runtime.n1a import digest
from dynamic_lisl.terminal_executor import TerminalExecutor
from dynamic_lisl.terminal_pair_intervals import TerminalPairCatalog
from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from dynamic_lisl.gate_c_terminal_geometry import TerminalGeometryConfig

def main():
    N2EvidenceBinding(P,'research_versions/dynamic_k_v1/acceptance/0006/implementation_manifest.json',
        '34e3412da99a96c58fe603af5de69777d69e0e2bc292fba4cbd3cfca8acb0b4a').verify()
    base=P/'outputs/gate_c_simplified_20260922T064019_313843Z'
    fixed=json.loads((base/'z_ref.json').read_text())['fixed_edges'];nodes=tuple(sorted({n for e in fixed for n in e}))
    rows=[json.loads(x) for x in (base/'terminal_pair_intervals.jsonl').read_text().splitlines()]
    cat=TerminalPairCatalog.from_records(rows,{n:int(n.split('_')[0][1:]) for n in nodes})
    config=TerminalGeometryConfig.from_dict(json.loads((P/'configs/hardware_gate_c_simplified_v1.json').read_text()))
    layer=N2PhysicalLayer(TerminalPairPhysicalFeasibility(cat),Sgp4PhysicalGuard(
        ReplayableSgp4Model.load(P/'data/raw/sgp4_x720'),config,earth_radius_km=6378.137))
    validator=ActionValidator(layer);ex=TerminalExecutor(nodes);profile=Setup(.2,.2,.2)
    chosen=min((Add(w.endpoint_a,w.endpoint_b,profile) for w in cat.terminal_pair_candidates(0.,nodes)),key=action_key)
    plan=validator.validate(ex,Add(chosen.a,chosen.b,Setup(0.,0.,0.)));assert plan['accepted'];ex.submit(plan['commands'])
    before=digest(ex.snapshot());ref=LinkRef.from_link(next(iter(ex.links.values())))
    verdict=validator.validate(ex,Replace((ref,),chosen.a,chosen.b,profile,'BBM'))
    assert not verdict['accepted'] and verdict['reason']=='DUPLICATE_LINK' and before==digest(ex.snapshot())
    result=dict(status='PASS_KNOWN_OCCUPIED_CATALOG_DUPLICATE_REPRODUCED',
        scope='TARGETED_READ_ONLY_REJECTION_EXPLANATION_ONLY',reason=verdict['reason'],
        link_reference=dict(link_id=ref.link_id,endpoints=ref.endpoints),
        accepted=False,live_state_changed=False,complete_catalog_rescanned=False,
        scientific_gate_pass=False,formal_experiments_executed=False)
    with (A/'occupied_catalog_rejection_detail.json').open('x',encoding='utf-8',newline='\n') as f:
        json.dump(result,f,ensure_ascii=False,sort_keys=True,indent=2);f.write('\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
