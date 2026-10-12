"""Register existing engineering evidence only; never execute a simulation."""
from pathlib import Path
import json, hashlib
ROOT=Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def seal(name,body):
    body['canonical_sha256']=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    (ROOT/name).write_text(json.dumps(body,indent=2,ensure_ascii=False),encoding='utf-8')
    return body
def main():
    status=read(ROOT/'configs/gate_f3_b4_lightweight_clone_status.json')
    evidence=ROOT/status['equivalence_report']
    assert sha(evidence)==status['equivalence_report_sha256']
    report=read(evidence)
    assert report['status']=='B4_LIGHTWEIGHT_CLONE_ENGINEERING_PASS'
    assert all(b['exact_equal'] for b in report['branch_comparisons'])
    files=['src/dynamic_lisl/rollout_clone.py','src/dynamic_lisl/gate_f3_p1_execution.py']
    source_hashes={k.replace('\\','/'):v for k,v in report['source_hashes'].items()}
    assert all(sha(ROOT/f)==source_hashes[f] for f in files)
    clone=seal('configs/gate_f3_b4_lightweight_clone_overlay_v1.json',{
        'status':'PASS','scope':'B4_LIGHTWEIGHT_CLONE_EXISTING_EVIDENCE_REGISTRATION',
        'registered_P1_executed':False,'frozen_scientific_semantics_changed':False,
        'source_hashes':{f:sha(ROOT/f) for f in files},
        'equivalence_evidence':{'report':str(evidence.relative_to(ROOT)).replace('\\','/'),'report_sha256':sha(evidence)}})
    pause=ROOT/'outputs/gate_f3_p1_paused_archive_20260926T141022_5579539Z'
    manifest=read(pause/'archive_manifest.json')
    assert all(sha(pause/r['name'])==r['sha256'] for r in manifest['archive_files'])
    assert sha(pause/'paused_evidence_bundle.zip')=='9f16af068e5576979e52006e37dba8c2c7509e6261153486f446c8208e6c0336'
    paths=['configs/gate_f3_b4_lightweight_clone_overlay_v1.json','configs/gate_f3_b4_decision_hash_reuse_overlay_v1.json']
    value=seal('configs/gate_f3_b4_runtime_chain_v1.json',{
        'schema':'b4_runtime_bookkeeping_chain_v1','status':'FROZEN',
        'overlays':{p:sha(ROOT/p) for p in paths},
        'pause_archive':str(pause.relative_to(ROOT)).replace('\\','/'),
        'pause_archive_manifest_sha256':sha(pause/'archive_manifest.json'),
        'new_registered_P1_executed':False,'P2_started':False,'RL_started':False})
    print(value['canonical_sha256'])
if __name__=='__main__':main()
