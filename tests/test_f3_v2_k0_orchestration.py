"""Bounded isolated engineering points and authorization guards, no natural run."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest
from dynamic_lisl.f3_v2.k0_audit_runner import (
    PointRuntimeSpec,run_audit,validate_natural_request,validate_natural_scene,runtime_from_dict)
from dynamic_lisl.f3_v2.k0_snapshot import (
    INITIALIZATION,SnapshotBudget,SourceScanBudget,SnapshotIncomplete,produce_snapshot)
from dynamic_lisl.f3_v2.k0_fixture import fixture
from dynamic_lisl.f3_v2.k0_ledger import KS,TIMES
from dynamic_lisl.f3_v2.joint_action import canonical_sha256
from dynamic_lisl.f3_v2.evidence import file_sha256

ROOT=Path(__file__).resolve().parents[1]


def runtime(source_cap=100,solver_nodes=100000,timeout=20):
    return PointRuntimeSpec(SnapshotBudget(solver_nodes,5.,solver_nodes,5.),
        SourceScanBudget(source_cap,10.),1,timeout,5.,'STRICT_CONNECTED')


def fixture_run(root,out,points,rt):
    args,scene=fixture()
    return run_audit(root=root,output_dir=out,scene=scene,points=points,runtime=rt,
        input_hashes=args['input_hashes'],mode='ENGINEERING_FIXTURE_ONLY')


def reseal(value):
    value.pop('canonical_sha256',None);value['canonical_sha256']=canonical_sha256(value)


def mock_authorized_documents(root):
    """Temporary schema-only human-approval fixture, never used to run a worker."""
    draft=json.loads((ROOT/'configs/gate_k0_contract_v1_1_DRAFT.json').read_text(encoding='utf-8'))
    contract=deepcopy(draft);contract.update(status='FROZEN',frozen=True,
        scope='NATURAL_K0_STRUCTURAL_AUDIT',initialization_convention=INITIALIZATION,
        human_approval_required=False,revision_execution_forbidden=[])
    reseal(contract)
    sources=['src/dynamic_lisl/f3_v2/'+n for n in ('k0_audit_runner.py','k0_snapshot.py','k0_support.py',
        'k0_ledger.py','structural.py','certified_topology.py','candidate_source.py','source_diagnostics.py',
        'batch_executor.py','joint_action.py','physical_trial.py','evidence.py','preflight.py')]
    sources+=['src/dynamic_lisl/'+n for n in ('terminal_executor.py','terminal_pair_intervals.py',
        'gate_c_simplified_feasibility.py','transition_profiler.py','operational_policy.py')]
    sources+=['tools/run_f3_v2_k0_audit.py']
    for rel in sources:
        p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('SCHEMA_ONLY_NOT_EXECUTABLE_FIXTURE')
    for p,x in (('contract.json',contract),('draft.json',draft),('scene.json',{'not_loaded':True})):
        (root/p).write_text(json.dumps(x),encoding='utf-8')
    hardware_path=draft['setup_source']
    for rel in ('backbone.json','windows.jsonl',hardware_path):
        p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}',encoding='utf-8')
    sources+=['contract.json','draft.json','scene.json','backbone.json','windows.jsonl',hardware_path]
    points=[{'K':K,'time_s':t,'replay_index':r} for K in KS for t in TIMES for r in (0,1)]
    manifest={'schema':'f3_v2_k0_audit_execution_v1','scope':'NATURAL_K0_STRUCTURAL_AUDIT',
        'status':'FROZEN','frozen':True,'points':points,'initialization_convention':INITIALIZATION,
        'contract_canonical_sha256':contract['canonical_sha256'],'file_hashes':{p:file_sha256(root/p) for p in sources},
        'scene_path':'scene.json','contract_path':'contract.json','authorization_path':'approval.json',
        'backbone_path':'backbone.json','windows_path':'windows.jsonl','setup_path':hardware_path,
        'parent_draft_path':'draft.json','runtime':asdict(runtime())}
    reseal(manifest)
    auth={'status':'APPROVED','actor':'HUMAN','scope':'NATURAL_K0_STRUCTURAL_AUDIT',
        'manifest_canonical_sha256':manifest['canonical_sha256'],
        'authorized_points_sha256':canonical_sha256(points),'K_star_selection_authorized':False}
    (root/'approval.json').write_text(json.dumps(auth),encoding='utf-8')
    return manifest,contract,auth


class K0OrchestrationTests(unittest.TestCase):
    def test_budget_observer_and_readonly_stages_are_exact(self):
        args,_=fixture();old=produce_snapshot(**args,K=4,time_s=0);stages=[]
        def sink(stage,evidence):
            stages.append((stage,deepcopy(evidence)));evidence.clear()
        new=produce_snapshot(**args,K=4,time_s=0,source_scan_budget=SourceScanBudget(100,10),stage_sink=sink)
        # solver_sha256 deliberately binds wall_s; compare the already-frozen
        # structural replay checkpoint rather than volatile audit timing bytes.
        self.assertEqual({k:v for k,v in old['snapshot'].items() if k!='solver_sha256'},
            {k:v for k,v in new['snapshot'].items() if k!='solver_sha256'})
        self.assertEqual(old['inventory'],new['inventory'])
        self.assertTrue(new['source_observation']['complete_raw_coverage_known'])
        self.assertEqual(new['source_observation']['evaluations_completed'],28)
        self.assertEqual(stages[0][0],'IDLE_ROOT');self.assertEqual(stages[-1][0],'SNAPSHOT_COMPLETE')

    def test_uncapped_exhaustion_keeps_solver_and_prefix_but_no_snapshot(self):
        args,_=fixture();stages=[]
        with self.assertRaises(SnapshotIncomplete) as caught:
            produce_snapshot(**args,K=4,time_s=0,source_scan_budget=SourceScanBudget(1,10),
                stage_sink=lambda s,e:stages.append((s,e)))
        self.assertEqual(caught.exception.status,'UNCAPPED_INVENTORY_UNKNOWN')
        e=caught.exception.evidence
        self.assertEqual(e['solver']['status'],'EXACT')
        self.assertTrue(e['source_observation']['partial_result_not_usable_as_source'])
        self.assertEqual(e['source_observation']['evaluations_completed'],1)
        self.assertTrue(e['source_observation']['live_unchanged'])
        self.assertEqual(stages[-1][0],'SOURCE_INCOMPLETE')

    def test_isolated_two_replays_and_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'attempt'
            points=[{'K':4,'time_s':0,'replay_index':r} for r in (0,1)]
            report=fixture_run(root,out,points,runtime())
            self.assertEqual(report['status'],'ENGINEERING_STRUCTURAL_ORCHESTRATION_PASS')
            self.assertEqual(report['completed_points'],2);self.assertFalse(report['Gate_K0_PASS'])
            for p in out.glob('point_*/process_report.json'):
                data=json.loads(p.read_text());self.assertFalse(data['child_still_alive']);self.assertEqual(data['exitcode'],0)
            before=(out/'report.json').read_bytes()
            with self.assertRaises(FileExistsError):fixture_run(root,out,points,runtime())
            self.assertEqual(before,(out/'report.json').read_bytes())

    def test_unknown_inventory_stops_later_point_and_persists_partial(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'attempt'
            points=[{'K':4,'time_s':t,'replay_index':0} for t in (0,30)]
            report=fixture_run(root,out,points,runtime(source_cap=1))
            self.assertEqual(report['status'],'AUDIT_STOPPED_BY_UNCAPPED_INVENTORY_UNKNOWN')
            self.assertFalse((out/'point_001').exists())
            self.assertTrue((out/'point_000/incomplete_evidence.json').is_file())
            self.assertTrue((out/'point_000/replace_rows.jsonl').read_text())
            self.assertTrue(list((out/'point_000').glob('stage_*_SOLVER.json')))
            self.assertFalse((out/'point_000/complete_bundle').exists())
            self.assertTrue((out/'failure_summary.json').is_file())
            self.assertTrue((out/'artifact_hashes.json').is_file())

    def test_solver_unknown_is_not_inventory_unknown_or_infeasible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'attempt'
            report=fixture_run(root,out,[{'K':4,'time_s':0,'replay_index':0}],runtime(solver_nodes=1))
            self.assertEqual(report['status'],'AUDIT_STOPPED_BY_SOLVER_UNKNOWN')
            snapshot=json.loads((out/'point_000/complete_bundle/snapshot.json').read_text())
            self.assertIsNone(snapshot['metrics']);self.assertEqual(snapshot['solver_status'],'UNKNOWN')

    def test_matching_infeasible_is_complete_certified_point(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'attempt'
            report=fixture_run(root,out,[{'K':16,'time_s':0,'replay_index':0}],runtime())
            self.assertEqual(report['status'],'ENGINEERING_STRUCTURAL_ORCHESTRATION_PASS')
            self.assertEqual(report['outcomes'][0]['solver_status'],'EXACT_INFEASIBLE')

    def test_spawn_timeout_only_terminates_own_child_and_preserves_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'attempt'
            report=fixture_run(root,out,[{'K':4,'time_s':0,'replay_index':0}],runtime(timeout=.000001))
            self.assertEqual(report['status'],'AUDIT_STOPPED_BY_POINT_TIMEOUT_UNKNOWN')
            data=json.loads((out/'point_000/process_report.json').read_text())
            self.assertTrue(data['timed_out']);self.assertFalse(data['child_still_alive'])
            self.assertTrue(data['terminated_only_this_attempt_child'])
            self.assertTrue((out/'point_000/point_input.json').is_file())

    def test_current_draft_and_unknown_mode_fail_before_spawning(self):
        args,scene=fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for mode in ('NATURAL_K0_STRUCTURAL_AUDIT','UNDECLARED'):
                out=root/mode
                r=run_audit(root=root,output_dir=out,scene=scene,points=[{'K':4,'time_s':0,'replay_index':0}],
                    runtime=runtime(),input_hashes=args['input_hashes'],mode=mode)
                self.assertEqual(r['status'],'STRUCTURAL_AUDIT_FAIL_STOP')
                self.assertFalse(list(out.glob('point_*')))

    def test_exact_detached_approval_chain_no_hash_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);m,c,a=mock_authorized_documents(root)
            r=validate_natural_request(root,m,c,a)
            self.assertEqual(r['status'],'AUTHORIZED_STRUCTURAL_EXECUTION_ONLY')
            self.assertFalse(r['K_star_selection_authorized'])
            self.assertNotIn('approval.json',m['file_hashes'])
            self.assertEqual(r['file_hashes']['approval.json'],file_sha256(root/'approval.json'))

    def test_authorization_hash_scope_sequence_and_scientific_field_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);m,c,a=mock_authorized_documents(root)
            for key,value in (('actor','AGENT'),('scope','REGISTERED_F3_V2'),('K_star_selection_authorized',True),
                              ('manifest_canonical_sha256','a'*64)):
                bad=dict(a);bad[key]=value
                with self.assertRaises(ValueError):validate_natural_request(root,m,c,bad)
            bad=deepcopy(m);bad['points'].pop();reseal(bad)
            with self.assertRaisesRegex(ValueError,'480'):validate_natural_request(root,bad,c,a)
            p=root/'scene.json';p.write_text('tampered')
            with self.assertRaisesRegex(ValueError,'HASH_MISMATCH'):validate_natural_request(root,m,c,a)
            m,c,a=mock_authorized_documents(root)
            c['hard_constraints'].remove('no_parallel_satellite_pair');reseal(c)
            (root/'contract.json').write_text(json.dumps(c));m['file_hashes']['contract.json']=file_sha256(root/'contract.json')
            m['contract_canonical_sha256']=c['canonical_sha256'];reseal(m)
            a['manifest_canonical_sha256']=m['canonical_sha256'];(root/'approval.json').write_text(json.dumps(a))
            with self.assertRaisesRegex(ValueError,'PARENT_SCIENTIFIC_FIELD_CHANGED'):validate_natural_request(root,m,c,a)

    def test_runtime_validation_and_duplicate_points(self):
        self.assertEqual(runtime_from_dict(asdict(runtime())),runtime())
        for value in (0,True,float('inf')):
            with self.assertRaises(ValueError):SourceScanBudget(1,value)
        with self.assertRaises(ValueError):runtime_from_dict({})
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);point={'K':4,'time_s':0,'replay_index':0}
            r=fixture_run(root,root/'duplicate',[point,point],runtime())
            self.assertEqual(r['status'],'STRUCTURAL_AUDIT_FAIL_STOP')
            self.assertFalse(list((root/'duplicate').glob('point_*')))

    def test_pinned_scene_preflight_rejects_modified_setup_windows_backbone(self):
        # A temporary parametric160-node metadata fixture only. No propagation,
        # matching, topology construction, traffic or controller evaluation.
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);nodes=sorted('X%d_%02d'%(p,s) for p in range(4) for s in range(40))
            fixed=[['X%d_%02d'%(p,s),'X%d_%02d'%(p,(s+1)%40)] for p in range(4) for s in range(40)]
            setup={'retarget_a_s':1.,'retarget_b_s':1.,'acquisition_s':1.}
            scene={'scope':'NATURAL_160_STRUCTURAL_ONLY','nodes':nodes,'fixed_edges':fixed,
                'plane_by_satellite':{n:int(n.split('_')[0][1:]) for n in nodes},'windows':[],
                'setup':setup,'initialization_convention':INITIALIZATION,'controller_or_traffic_invoked':False,
                'K_star_selected':False}
            files={'scene.json':scene,'backbone.json':{'fixed_edges':fixed},'hardware.json':{'audit_setup_fixture':setup}}
            for p,data in files.items():(root/p).write_text(json.dumps(data),encoding='utf-8')
            (root/'windows.jsonl').write_text('',encoding='utf-8')
            manifest={'scene_path':'scene.json','backbone_path':'backbone.json','windows_path':'windows.jsonl',
                'setup_path':'hardware.json','file_hashes':{p:file_sha256(root/p) for p in (*files,'windows.jsonl')}}
            self.assertEqual(validate_natural_scene(root,scene,manifest,manifest['file_hashes'])['status'],'PINNED_160_STRUCTURAL_SCENE_PASS')
            for field in ('setup','fixed_edges','windows'):
                bad=deepcopy(scene)
                if field=='setup':bad[field]['acquisition_s']=0
                else:bad[field].append(bad['fixed_edges'][0])
                (root/'scene.json').write_text(json.dumps(bad),encoding='utf-8')
                manifest['file_hashes']['scene.json']=file_sha256(root/'scene.json')
                with self.assertRaisesRegex(ValueError,'NOT_DERIVED'):
                    validate_natural_scene(root,bad,manifest,manifest['file_hashes'])

    def test_unresolved_draft_metadata_not_accepted_by_status_relabel(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);m,c,a=mock_authorized_documents(root)
            for key,value in (('human_approval_required',True),('revision_execution_forbidden',['maximum_matching'])):
                bad=deepcopy(c);bad[key]=value;reseal(bad)
                with self.assertRaisesRegex(ValueError,'UNRESOLVED_DRAFT'):
                    validate_natural_request(root,m,bad,a)


if __name__=='__main__':unittest.main()
