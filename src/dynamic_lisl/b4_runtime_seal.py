"""Read-only, fail-closed validation of B4 runtime and paused evidence seals."""
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime

CHAIN_SHA='61bd7dc640a3f97eec35a88785202a3ae8655e5cee67080b80cd45f58b97e7df'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def canonical(doc):
    body=dict(doc);body.pop('canonical_sha256',None)
    return hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def executor_compatibility_successor(root, parent, current):
    """Accept only the separately validated, exact optional-sink repair."""
    try:
        registry=read(root/'configs/b4_executor_compatibility_successor_v1.json')
        assert canonical(registry)==registry['canonical_sha256']
        assert registry['status']=='AUTHORIZED_RUNTIME_SUCCESSOR'
        assert registry['authorization_gate']=='B4_RUNTIME_SUCCESSOR_BOOTSTRAP'
        assert registry['parent_hash']==parent and registry['successor_hash']==current
        evidence=registry['evidence']
        assert sha(root/evidence['report'])==evidence['report_sha256']
        doc=read(root/evidence['report'])
        assert doc['status']=='CANDIDATE_SUCCESSOR_VALIDATED'
        assert doc['H_old']==parent and doc['H_new']==current
        assert doc['scientific_semantics_unchanged'] is True
        assert doc['previous_FAIL_attempts_preserved'] is True
        assert doc['registered_P1_executed'] is False
        assert doc['P2_started'] is False and doc['RL_started'] is False
        assert doc['telemetry_equivalence']=='PASS'
        assert len(doc['supporting_test_results'])==3
        assert all(item['pass'] is True and item['count']>0 for item in doc['supporting_test_results'])
        for item in doc['supporting_evidence']:
            assert sha(root/item['report'])==item['report_sha256']
        multi=read(root/doc['multi_epoch_report'])
        assert multi['status']=='MULTI_EPOCH_EXACT_EQUIVALENCE_PASS'
        assert multi['all_epoch_branch_and_state_exact'] is True
        assert multi['epochs_s']==[0,2,4,6,8,10]
        name='src/dynamic_lisl/gate_f3_p1_execution.py'
        assert registry['file']==name and sha(root/name)==current
        assert {k.replace('\\','/'):v for k,v in multi['source_hashes'].items()}[name]==current
        classification=read(root/Path(doc['multi_epoch_report']).parent.parent/'candidate_test_classification.json')
        assert classification['scientific_tests_pass'] is True and not classification['skipped']
        data=(root/name).read_bytes()
        new=b'        sink = getattr(self, "_checkpoint_sink", None)\n        if sink is not None:\n            sink({'
        old=b'        if self._checkpoint_sink is not None:\n            self._checkpoint_sink({'
        # Historical files use CRLF; preserve exact bytes in the inverse diff.
        if b'\r\n' in data:new=new.replace(b'\n',b'\r\n');old=old.replace(b'\n',b'\r\n')
        assert data.count(new)==1
        assert hashlib.sha256(data.replace(new,old)).hexdigest()==parent
        return True
    except (AssertionError,KeyError,OSError,ValueError,TypeError):
        return False

def _production_suffix(root, supplied=None, only_file=None):
    if supplied is not None:
        doc=supplied
        candidate=True
    else:
        registration=root/'configs/gate_f3_b4_production_multiprocessing_registration_v1.json'
        if registration.is_file():
            record=read(registration)
            assert canonical(record)==record['canonical_sha256']
            assert record['parent_chain_canonical_sha256']==CHAIN_SHA
            assert sha(root/record['overlay'])==record['overlay_sha256']
            doc=read(root/record['overlay']);candidate=False
        elif os.environ.get('B4_ENGINEERING_RUNTIME_CANDIDATE'):
            candidate_path=Path(os.environ['B4_ENGINEERING_RUNTIME_CANDIDATE']).resolve()
            assert candidate_path.is_relative_to((root/'outputs').resolve())
            doc=read(candidate_path);candidate=True
        else:
            return None
    assert canonical(doc)==doc['canonical_sha256']
    assert doc['status']==('EQUIVALENCE_VALIDATED_PENDING_ACCEPTANCE' if candidate else 'PASS')
    assert doc['parent_chain_canonical_sha256']==CHAIN_SHA
    assert doc['registered_P1_executed'] is False
    assert doc['frozen_scientific_semantics_changed'] is False
    assert doc['production_worker_count']==8
    assert doc['horizon_s']==10 and doc['decision_cadence_s']==2 and doc['top_k']==16
    ev=doc['equivalence_evidence']
    assert sha(root/ev['report'])==ev['report_sha256']
    report=read(root/ev['report'])
    assert report['status']=='MULTI_EPOCH_EXACT_EQUIVALENCE_PASS'
    assert report['epochs_s']==[0,2,4,6,8,10]
    assert report['all_epoch_branch_and_state_exact'] is True
    assert report['natural_state_evolution'] is True
    assert report['pool_created_once'] is True and report['worker_shutdown_clean'] is True
    assert report['registered_P1_executed'] is False
    branch_ev=doc['branch_equivalence_evidence']
    assert sha(root/branch_ev['report'])==branch_ev['report_sha256']
    branch=read(root/branch_ev['report'])
    assert branch['status']=='B4_BRANCH_MULTIPROCESSING_GATE_PASS'
    assert branch['scientific_exact_equivalence'] is True
    assert [row['workers'] for row in branch['scaling']]==[1,2,4,8]
    assert all(row['exact'] is True for row in branch['scaling'])
    branch_sources={k.replace('\\','/'):v for k,v in branch['source_hashes'].items()}
    assert branch_sources['src/dynamic_lisl/b4_branch_multiprocessing.py']==sha(root/'src/dynamic_lisl/b4_branch_multiprocessing.py')
    report_sources={name.replace('\\','/'):value
                    for name,value in report['source_hashes'].items()}
    for name,expected in doc['optimized_code_hashes'].items():
        if only_file is not None and name!=only_file:
            continue
        actual=sha(root/name)
        assert (report_sources[name]==expected==actual or
                (name=='src/dynamic_lisl/gate_f3_p1_execution.py'
                 and report_sources[name]==expected
                 and executor_compatibility_successor(root,expected,actual)))
    for name,expected in doc['bookkeeping_code_hashes'].items():
        assert sha(root/name)==expected
    if not candidate:
        acceptance=doc['acceptance_evidence']
        assert sha(root/acceptance['report'])==acceptance['report_sha256']
        accepted=read(root/acceptance['report'])
        assert accepted['status']=='PRE_REGISTRATION_ACCEPTANCE_PASS'
        assert accepted['full_regression_pass'] is True
        assert accepted['focused_tests_pass'] is True
        assert accepted['p1_preflight_pass'] is True
        assert accepted['registered_P1_executed'] is False
    return doc


def approved_production_file_successor(root,name,parent,current):
    """Narrow per-file acceptance; all other scientific files stay frozen."""
    if name!='src/dynamic_lisl/rollout_controller.py':
        return False
    try:
        chain=read(root/'configs/gate_f3_b4_runtime_chain_v1.json')
        assert canonical(chain)==chain['canonical_sha256']==CHAIN_SHA
        reuse_name='configs/gate_f3_b4_decision_hash_reuse_overlay_v1.json'
        assert sha(root/reuse_name)==chain['overlays'][reuse_name]
        reuse=read(root/reuse_name)
        assert reuse['optimized_code_hashes'][name]==parent
        doc=_production_suffix(root,only_file=name)
        assert doc is not None
        assert doc['parent_code_hashes'][name]==parent
        assert doc['optimized_code_hashes'][name]==current==sha(root/name)
        return True
    except (AssertionError,KeyError,OSError,ValueError,TypeError):
        return False


def validate_runtime(root, production_overlay=None):
    chain=read(root/'configs/gate_f3_b4_runtime_chain_v1.json')
    assert canonical(chain)==chain['canonical_sha256']==CHAIN_SHA
    suffix=_production_suffix(root,production_overlay)
    def current_matches(name,expected):
        actual=sha(root/name)
        return actual==expected or (suffix is not None
            and suffix['parent_code_hashes'].get(name)==expected
            and (suffix['optimized_code_hashes'].get(name)==actual or
                 (name=='src/dynamic_lisl/gate_f3_p1_execution.py' and
                  executor_compatibility_successor(root,suffix['optimized_code_hashes'].get(name),actual))))
    overlays=[]
    for name,expected in chain['overlays'].items():
        assert sha(root/name)==expected
        doc=read(root/name)
        assert canonical(doc)==doc['canonical_sha256'] and doc['status']=='PASS'
        assert doc['registered_P1_executed'] is False
        ev=doc['equivalence_evidence'];assert sha(root/ev['report'])==ev['report_sha256']
        report=read(root/ev['report'])
        if 'source_hashes' in doc:
            assert report['status']=='B4_LIGHTWEIGHT_CLONE_ENGINEERING_PASS'
            assert len(report['branch_comparisons'])==3 and all(x['exact_equal'] for x in report['branch_comparisons'])
            expected_sources={k.replace('\\','/'):v for k,v in report['source_hashes'].items()}
            assert all(expected_sources[k]==v and current_matches(k,v) for k,v in doc['source_hashes'].items())
        else:
            assert report['pass'] is True and report['b4_decision_hash_reuse_equivalence'] is True
            assert report['legacy_decision']==report['optimized_decision']
            assert report['legacy_branch_results']==report['optimized_branch_results']
            assert all(current_matches(k,v) for k,v in doc['optimized_code_hashes'].items())
        overlays.append(doc)
    if suffix is not None:
        assert suffix['parent_code_hashes']['src/dynamic_lisl/gate_f3_p1_execution.py']==overlays[0]['source_hashes']['src/dynamic_lisl/gate_f3_p1_execution.py']
        assert suffix['parent_code_hashes']['src/dynamic_lisl/rollout_controller.py']==overlays[1]['optimized_code_hashes']['src/dynamic_lisl/rollout_controller.py']
        overlays.append(suffix)
    return chain,overlays

def paused_record(root,attempt,chain):
    """Accept only the exact archived attempt with unchanged file set/content."""
    archive=root/chain['pause_archive']
    assert sha(archive/'archive_manifest.json')==chain['pause_archive_manifest_sha256']
    manifest=read(archive/'archive_manifest.json')
    for item in manifest['archive_files']:
        p=archive/item['name']
        assert p.stat().st_size==item['size_bytes'] and sha(p)==item['sha256']
    record=read(archive/'pause_record.json')
    if Path(record['scientific_attempt_path']).resolve()!=attempt.resolve():return None
    assert record['active_p1_process_count_after_stop']==0
    assert record['result_seal']=='NO' and record['originals_modified_by_archive'] is False
    assert record['registered_P1_status']=='PAUSED_INCOMPLETE_5_OF_12_PLUS_PARTIAL_RUN_6'
    for name in ('scientific_attempt_tree_hashes.json','telemetry_tree_hashes.json'):
        tree=read(archive/name); base=Path(tree['root'])
        expected={row['path'].replace('\\','/'):row['sha256'] for row in tree['files']}
        observed={str(p.relative_to(base)).replace('\\','/'):sha(p) for p in base.rglob('*') if p.is_file()}
        assert observed==expected
    ledger=[json.loads(x) for x in (attempt/'run_ledger.jsonl').read_text().splitlines()]
    def normalize(rows):
        return [{k:(datetime.strptime(v,'%Y-%m-%dT%H:%M:%S.%fZ')
                    if k in ('start_timestamp','finish_timestamp') else v)
                 for k,v in row.items()} for row in rows]
    # PowerShell archive serialized .588120Z as .58812Z: exact same instant.
    assert normalize(ledger)==normalize(record['completed_ledger'])
    assert len(ledger)==record['completed_registered_runs']==5
    return {'attempt':attempt.name,'status':'PAUSED_INCOMPLETE','result_seal':'NO',
            'source':chain['pause_archive']+'/pause_record.json','archive_verified':True,
            'resume_authorized':False}
