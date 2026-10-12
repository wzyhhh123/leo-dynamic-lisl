"""Engineering-only current-geometry hash-reuse equivalence; never registered P1."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

PROJECT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PROJECT/'src'), str(PROJECT/'tests'), str(PROJECT/'tools')]
from dynamic_lisl.common import read_json
from dynamic_lisl.controller_runner import controller_visible_state
from dynamic_lisl.gate_e2_experiments import GateE2Assets
from dynamic_lisl.gate_f3_p1_execution import P1RunExecutor
from test_b4_decision_hash_reuse import compare
from check_b4_lightweight_clone import history


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    out = PROJECT/'outputs'/('b4_decision_hash_reuse_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    out.mkdir(parents=True)
    config_hashes = {str(p.relative_to(PROJECT)): sha(p) for p in (PROJECT/'configs').glob('*.json')}
    assets = GateE2Assets()
    rows = read_json(PROJECT/'configs/gate_f3_execution_manifest_v1.json')['runs']
    template = next(r for r in rows if r['block_id']=='P1' and r['controller']=='B4' and r['rho']==0.5)
    runner = P1RunExecutor(assets, {**template, 'run_id':'ENGINEERING_HASH_REUSE_ONLY', 'block_id':'ENGINEERING_PROFILE_ONLY'})
    engine = runner.engine
    state = controller_visible_state(engine)
    specs = tuple(runner.candidate_source(state, {'epoch_index':0,'regime':'Z_MODERATE','terminal_executor':engine.executor}))
    proposed = runner.proposer.propose(engine.executor, specs, assets.physical, assets.fixed, 'Z_MODERATE')
    selected = [next(r for r in proposed['proposals'] if r['stratum']==s)
                for s in ('BBM_REQUIRED', 'MBB_STRUCTURALLY_FEASIBLE')]
    # Structural test subset only; production proposer/action universe unchanged.
    fixture = {**proposed, 'proposals':selected}
    before = history(engine)
    started = time.perf_counter()
    observed = compare(runner.controller, fixture)
    assert history(engine)==before
    assert controller_visible_state(engine)==state
    assert all(sha(PROJECT/k)==v for k,v in config_hashes.items())
    report = {
        'pass':True, 'b4_decision_hash_reuse_equivalence':True,
        'scope':'160-star t=0 HOLD+first-BBM+first-MBB structural engineering subset',
        'full_17_branch_decision_executed':False, 'registered_P1_executed':False,
        'wall_s_two_modes':time.perf_counter()-started,
        'legacy_hash_calls':observed[0][2], 'optimized_hash_calls':observed[1][2],
        'legacy_decision':observed[0][0], 'optimized_decision':observed[1][0],
        'legacy_branch_results':observed[0][1], 'optimized_branch_results':observed[1][1],
        'raw_candidate_ids':[s.proposal_id for s in specs],
        'production_proposal_ids':[r['proposal_id'] for r in proposed['proposals']],
        'production_proposal_set_sha256':proposed['proposal_set_sha256'],
        'config_hashes_unchanged':True, 'config_hashes':config_hashes,
        'negative_controls':'test_b4_decision_hash_reuse.py',
        'source_hashes':{str(p.relative_to(PROJECT)):sha(p) for p in (PROJECT/'src/dynamic_lisl').glob('*.py')},
    }
    (out/'report.json').write_text(json.dumps(report, indent=2),encoding='utf-8')
    print(json.dumps({'output':str(out), 'pass':True, 'legacy':observed[0][2], 'optimized':observed[1][2]}),flush=True)


if __name__=='__main__':
    main()
