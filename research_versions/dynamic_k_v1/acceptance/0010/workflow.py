"""Append-only P0 engineering workflow; never runs the paired pilot matrix."""
import argparse,hashlib,importlib.util,io,json,sys,time,unittest,subprocess
from pathlib import Path
from datetime import datetime,timezone,timedelta
V=Path(__file__).resolve().parents[2];P=V.parents[1];A=Path(__file__).parent
sys.path.insert(0,str(V));sys.path.insert(0,str(P/'src'))
ORIGIN='ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691'
PARENT='bd54f8efb78375acca995b8ed43f5ccbfb4be80228d46eb2ca2ab5e954d86342'
NS='research_versions/dynamic_k_v1/'

def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
vc=load('p0_version',V/'tools/version_control_readme_v1.py')
from runtime.bindings import EngineeringBinding
from runtime.n1b_evaluator import N1bEvidenceBinding
from runtime.n2_binding import N2EvidenceBinding
from runtime.n3_baselines import N3EvidenceBinding
from runtime.n4_p0 import P0EvidenceBinding

def write(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as f:
        if isinstance(x,str):f.write(x)
        else:json.dump(x,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
def bind(p):return vc.binding(P,p.relative_to(P).as_posix())
def dependencies():
    out=[]
    for rev,cls,name,h in [('0004',EngineeringBinding,'implementation_manifest.json','227043a6bcf318846bbc2e854130613b49082ef6a7e17f3913160f24f40456ad'),
        ('0005',N1bEvidenceBinding,'implementation_manifest.json','c27ac2866d4bfd12a8384bd91a990f841daad45a7079230301d1aaef4436031a'),
        ('0006',N2EvidenceBinding,'implementation_manifest.json','34e3412da99a96c58fe603af5de69777d69e0e2bc292fba4cbd3cfca8acb0b4a'),
        ('0007',N3EvidenceBinding,'implementation_manifest_attempt02.json','dbc7e0d54d6d9bb864ec216a0b7c6cd1b86ec6353ed3ab41a3c3c64b471b9129')]:
        b=cls(P,NS+'acceptance/'+rev+'/'+name,h);b.verify();out.append(b)
    return out

def fixtures():
    f=load('p0_n3_fixtures',V/'tests/test_n3_baselines.py');f.N1A_BINDING,f.N1B_BINDING,f.N2_BINDING,f.N3_BINDING=dependencies();return f

class Progress(unittest.TextTestResult):
    def startTest(self,t):print('START '+str(t),flush=True);super().startTest(t)
    def stopTest(self,t):print('DONE '+str(t),flush=True);super().stopTest(t)
def test_module(m,only=None):
    stream=io.StringIO();start=time.perf_counter()
    suite=unittest.defaultTestLoader.loadTestsFromModule(m) if not only else unittest.TestSuite(
        m.P0Tests(n) for n in sorted(unittest.defaultTestLoader.getTestCaseNames(m.P0Tests)) if any(n.startswith(x) for x in only))
    r=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=Progress).run(suite)
    return dict(status='PASS' if r.wasSuccessful() else 'FAIL',tests_run=r.testsRun,
        failures=[dict(test=str(t),traceback=s) for t,s in r.failures],errors=[dict(test=str(t),traceback=s) for t,s in r.errors],
        skipped=[dict(test=str(t),reason=s) for t,s in r.skipped],output=stream.getvalue(),wallclock_s=time.perf_counter()-start)

def prepare(name):
    manifest_name=name
    deps=dependencies();assert vc.binding(P,NS+'revisions/0007/record.json')['sha256']=='f58cc5eb037eaf6ee804c9aa1c5ec54f38894d00ca0d715f8b7baae8a47e06db'
    assert vc.binding(P,NS+'revisions/0009/record.json')['sha256']==PARENT
    if not (A/'pre_implementation_verification.json').exists():
        write(A/'pre_implementation_verification.json',dict(status='PASS',revision_id='0009',verified_file_count=5966,
            baseline_file_count=5810,excluded_file_count=202,expected_version_sha256=ORIGIN,expected_revision_sha256=PARENT,
            undeclared_changes=dict(added=[],modified=[],deleted=[],possible_renames=[]),
            source='actual full verifier command output before creating P0 assets in this turn',
            dependency_verifications=[b.verify() for b in deps],scientific_gate_pass=False))
    c=V/'configs/n4_p0_pilot_semantics_v1.json'
    if not c.exists():
        write(c,dict(schema='dynamic_k_n4_p0_pilot_v1',status='PILOT_ONLY_NOT_SCIENCE_FROZEN',formal_experiments_authorized=False,
            scientific_parameters={k:None for k in ('T_A_s','T_s','tau_res_s','R_min','alpha','D_ref_s','E_ref_J')},
            formal_control_parameters=dict(decision_cadence_s=None,search_budget=None,maximum_concurrent_actions=None),
            PILOT_ONLY=dict(T_s=30.,T_A_s=20.,H_s=6.,decision_cadence_s=3.,decision_epochs_s=list(range(0,30,3)),
                retarget_a_s=.5,retarget_b_s=.5,acquisition_s=.5,lambda_N_s=6.,lambda_E_bit_s_per_J=1000.,
                maximum_atomic_actions_per_epoch=1,maximum_scored_branches=7,
                main_pilot_branch_upper_bound=840,sensitivity_extra_branch_upper_bound=1680,
                all_branch_upper_bound=2520,main_branch_seconds_upper_bound=4788.,all_branch_seconds_upper_bound=14364.),
            full_pilot_execution_authorized=False,gnn_training_authorized=False,current_state_greedy_implemented=False))
    contract=V/'contracts/N4_P0_CAUSAL_ROOT_SCORING_CN.md'
    if not contract.exists():
        write(contract,'# N4-P0 \u56e0\u679c\u52a8\u6001 K \u8bc4\u5206\u63a5\u7f1d\n\n\u4ec5\u5de5\u7a0b\u5b9e\u73b0\u3002\u590d\u7528\u51bb\u7ed3 N1a/N1b/N2/N3\uff0c\u4e0d\u6539\u751f\u4ea7\u5185\u6838\uff1b\u65e7 B4 \u4e0d\u8c03\u7528\u3002\n'
            '\u56e0\u679c\u89c6\u56fe\u63d0\u4f9b\u5f53\u524d\u4e1a\u52a1\u3001\u7ec8\u7aef\u3001\u9884\u7ea6\u4ee5\u53ca\u8fc7\u53bb\u53d1\u5c04\u4ea7\u751f\u7684\u627f\u8bfa\u4e8b\u4ef6\u3002\u89c2\u5bdf\u65e5\u5fd7\u6784\u9020\u771f\u5b9e\u5386\u53f2\u6ce8\u5165\u524d\u7f00\uff1bdeepcopy memo \u5728\u590d\u5236\u65f6\u66ff\u6362\u771f trace \u4e0e\u8fb9\u754c\uff0c\u65e7\u6e90\u4e0e\u542b\u65e7\u6e90\u54c8\u5e0c\u7684\u7f13\u5b58\u7ed3\u679c\u4e0d\u8fdb\u5165\u8bc4\u5206\u5bf9\u8c61\u3002\n'
            'ZERO \u4ec5\u4ee4\u672a\u6765\u5916\u751f\u6ce8\u5165\u4e3a\u96f6\uff0cPERSIST \u5ef6\u62d3\u5f53\u524d\u7387\u3002\u4fdd\u7559 Q/I/A/D\u3001\u4f20\u64ad agenda\u3001setup/TX/\u81ea\u7136\u5230\u671f\u3001FIFO \u4e0e\u80fd\u8017\u6e38\u6807\uff1b\u4e0d\u91cd\u65b0\u51fa\u751f cohort\u3002\u6b64\u4e3a\u6570\u636e\u5f15\u7528\u9694\u79bb\uff0c\u4e0d\u662f\u6076\u610f Python \u7684\u6587\u4ef6\u7cfb\u7edf\u5b89\u5168\u6c99\u7bb1\u3002\n'
            'C=J_h+lambda_N*N_end+lambda_E*DeltaE_h\uff1b\u5355\u4f4d bit\u00b7s\uff0clambda_N \u4e3a s\uff0clambda_E \u4e3a bit\u00b7s/J\u3002\u539f 320 \u7ec8\u7aef\u79ef\u5206\uff1b\u4e0d\u91cd\u590d\u8ba1\u5386\u53f2 J/E\u3002\n'
            'PILOT_ONLY T30/TA20/H6\uff0c\u51b3\u7b56\u5468\u671f3\u79d2\uff0cepoch0,3,6,9,12,15,18,21,24,27\uff1bt27\u6709\u6548H3\uff0c\u5176\u4f59H6\u3002\u771f\u5b9e\u4e8b\u4ef6\u4e0d\u5bf9\u9f50\u51b3\u7b56\u7f51\u683c\u3002\u6bcf\u5019\u9009\u4e00\u6b21\u771f\u5b9e\u539f\u5b50\u52a8\u4f5c\u540e\u4fdd\u6301\uff0c\u5230\u539f\u8bc4\u4ef7\u8fb9\u754c\u524d\u7ed3\u675f\u3002\u6240\u6709\u6b63\u5f0f\u79d1\u5b66\u4e03\u53c2\u6570\u53ca\u6b63\u5f0f\u5468\u671f/\u9884\u7b97\u7ee7\u7eednull\u3002\n'
            '\u5168\u90e8 N2 \u5408\u6cd5\u5019\u9009\u679a\u4e3e\u540e\u624d\u4fdd\u7559\u81f3\u591a7\u4e2a\uff0c\u4e24\u4e2a\u516c\u5f00OD\u76ee\u6807\u4f18\u5148\u3001\u5b57\u5178\u5e8f\u786e\u5b9a\uff1bREPLACE\u4ecd\u662fN2\u65e2\u5b9a\u751f\u6210\u8303\u56f4\u3002\u5168\u90e8\u5019\u9009\u540c\u6839/\u540c\u9884\u6d4b\uff0c\u6309\u4ee3\u4ef7\u3001HOLD\u5e73\u5206\u4f18\u5148\u3001action_key\u9009\u53d6\u3002\n'
            '\u672c\u8f6e\u53ea\u65b0\u63a5\u7f1d\u9a8c\u6536\u53ca\u4e00\u4e2a\u72ec\u7acb\u9884\u6d4b\u5206\u652f\u548c\u4e00\u4e2a\u5b8c\u6574epoch\u6210\u672c\u68c0\u67e5\uff0c\u4e0d\u6267\u884c\u516d\u573a\u666f24\u6b21\u6216\u654f\u611f\u6027\u3002\n')
    old=Path('C:/Users/11656/.codex/visualizations/2026/10/10/01a123b2-70a3-7090-a938-138b860cbb46/pilot_preregistration_20261012T070653Z')
    review=A/'pilot_review_3s'
    if not review.exists():
        hashes=[]
        for p in sorted(old.glob('*.md')):
            raw=p.read_bytes();target=A/'prior_pilot_drafts_1s'/p.name;target.parent.mkdir(exist_ok=True)
            with target.open('xb') as f:f.write(raw)
            hashes.append(dict(original_path=p.as_posix(),sha256=hashlib.sha256(raw).hexdigest(),snapshot=bind(target)))
        write(A/'prior_pilot_draft_hashes.json',hashes)
        common='\u72b6\u6001\uff1aPILOT_ONLY / \u672a\u6267\u884c\u9884\u5b9e\u9a8c / \u4eba\u5de5\u4fee\u8ba2\u51b3\u7b56\u5468\u671f\u4e3a3\u79d2\u3002\u65e71\u79d2\u8349\u6848\u539f\u5b57\u8282\u53ca\u54c8\u5e0c\u4fdd\u5b58\u5728 ../prior_pilot_drafts_1s \u548c ../prior_pilot_draft_hashes.json\uff0c\u539f\u6587\u4ef6\u672a\u8986\u76d6\u3002\n\n'
        params='T=30 s\uff0cT_A=20 s\uff0cH=6 s\uff0cdecision_cadence_s=3.0\uff0cepoch=(0,3,6,9,12,15,18,21,24,27)\u3002\u6240\u6709\u56db\u63a7\u5236\u5668\u5171\u7528\u8be5\u65f6\u95f4\u8868\uff1b\u771f\u5b9e\u6ce8\u5165/\u4f20\u64ad/setup/\u91ca\u653e\u4ecd\u6309\u4e8b\u4ef6\u65f6\u95f4\u5904\u7406\uff0c\u4e0d\u5f3a\u884c\u5bf9\u9f50\u3002\u53cc\u7aefretarget\u54040.5 s\uff0cacquisition0.5 s\uff0c\u7a7a\u95f2ready=t+1 s\u3002t0\u81f3t24\u7684h=6 s\uff0ct27\u7684h=3 s\uff0c\u9884\u6d4b\u5747\u4e0d\u8d8aT\u3002lambda_N=6 s\uff0clambda_E=1000 bit\u00b7s/J\u3002\u6b63\u5f0f\u79d1\u5b66\u53c2\u6570\u548c\u6b63\u5f0f\u5468\u671f/\u9884\u7b97\u7ee7\u7eednull\u3002\n\n'
        budgets='\u4e3b\u8ba1\u52126\u573a\u666f\u00d72MPC\u00d710epoch\u00d7\u6700\u591a7\u5206\u652f=840\u5206\u652f\uff1b\u6bcf\u4e2a\u5019\u9009\u7d2f\u8ba1h=9\u00d76+3=57 s\uff0c\u4e3b\u9884\u6d4b\u4e0a\u96504788 branch-s\u3002\u654f\u611f\u6027\u989d\u591624\u4e2aMPC\u8fd0\u884c=1680\u5206\u652f/9576 branch-s\uff1b\u5168\u90e82520\u5206\u652f/14364 branch-s\uff0c\u771f\u5b9e\u8fd0\u884c24\u621648\u6b21\u7684T\u4ecd30 s\u3002\u8fd9\u91cc\u4ec5\u9884\u7b97\uff0c\u5747\u672a\u6267\u884c\u4e14\u672c\u8f6e\u65e0\u8fd0\u884c\u6388\u6743\u3002\n\n'
        names=['PILOT_PARAMETER_MANIFEST_DRAFT.md','PILOT_SCENARIO_MATRIX.md','MPC_INTERFACE_GAP_AUDIT.md','PILOT_ACCEPTANCE_CRITERIA.md']
        for name in names:
            extra=''
            if name==names[0]:extra='\u9664\u5468\u671f\u4e0e\u968f\u4e4b\u6539\u53d8\u7684\u672b\u7aefh/\u9884\u7b97\u5916\uff0c\u539f\u529f\u7387\u3001\u5bb9\u5dee\u3001\u5bb9\u91cfC=10^6bit/s\u3001\u654f\u611f\u6027\u5355\u56e0\u7d20\u7cfb\u6570\u3001\u56e0\u679cZERO/PERSIST\u53ca\u5355\u4f4d\u6b63\u786e\u4ee3\u4ef7\u5747\u4e0d\u53d8\u3002\u53c2\u8003\u65e7\u8349\u6848\u5feb\u7167\u5b8c\u6574\u8868\uff1b\u4e0d\u8bfb\u53d6\u672a\u6765TA\u622a\u6b62\u6765\u4fee\u6b63PERSIST\u3002\n'
            if name==names[1]:extra='\u4fdd\u7559\u516d\u573a\u666fU-STABLE/U-SHORT/U-SUSTAIN/C-STABLE/C-SHORT/C-SUSTAIN\uff1bOD\u4e3af_bg:X0_1\u2192X1_1\uff0cf_hot:X0_10\u2192X1_10\u3002\u80cc\u666f200000bit/s\uff0c\u70ed\u70b9\u57fa\u7840400000\uff0c\u77ed\u7a81\u53d1[8,10)\u4e3a1200000\uff0c\u6301\u7eed[8,20)\u4e3a1200000\u3002\u65e7\u573a\u666f\u77e9\u9635\u7684\u5b8c\u65742742\u884ccatalog\u3001160\u56fa\u5b9a\u73af\u8fb9\u3001\u8f93\u5165\u539f\u5b57\u8282\u54c8\u5e0c\u3001U/C\u521d\u6001\u53ca\u5c0f\u57df\u4fdd\u7559\u89c4\u5219\u5168\u90e8\u4e0d\u53d8\u3002t8\u548ct10\u7a81\u53d1\u8fb9\u754c\u4e0d\u4e0eepoch\u5f3a\u5236\u5bf9\u9f50\u3002\u56db\u81c2\u4ecd\u4e3aSTATIC_HOLD/\u539fN3 REACTIVE/MPC-ZERO/PERSIST\uff0c\u4f46\u56db\u81c2runner\u548c\u9884\u5b9e\u9a8c\u672c\u8f6e\u4e0d\u5b9e\u73b0\u3002\n'
            if name==names[2]:extra='\u65b0\u7248\u6700\u5c0f\u63a5\u53e3\u5df2\u8fdb\u5165\u72ec\u7acb\u5de5\u7a0b\u5b9e\u65bd\uff1aruntime/n4_p0.py\uff0c\u662f\u5426\u901a\u8fc7\u89c1../RESULT_CN.md\u3002\u65e7B4\u4e0d\u8c03\u7528\uff0c\u56e0\u679c\u89c6\u56fe/\u524d\u7f00\u51c0\u5316/\u540c\u6839\u540c\u9884\u6d4b/N2\u8bc4\u5206\u63a5\u7f1d\u6309\u539f\u5ba1\u8ba1\u843d\u5b9e\u3002\u539fN3\u89c2\u5bdf\u4ecd\u975e\u5b8c\u5907\u9884\u6d4b\u72b6\u6001\uff1b\u53ea\u8bfb\u6269\u5c55\u5df2\u627f\u8bfasetup/TX/\u4f20\u64ad/cohort\uff0c\u4fdd\u7559\u5ba1\u8ba1G29\u62ab\u9732\u3002\u8ba1\u7b97\u6210\u672c\u672c\u8f6e\u6d4b\u91cf\u4e0d\u9760\u65e7B4\u63a8\u7b97\u3002\n'
            if name==names[3]:extra='\u539f\u9a8c\u6536\u6761\u76ee\u5168\u90e8\u7ee7\u7eed\u9002\u7528\u3002\u5355\u6b65\u9884\u6d4b\u8bef\u5dee\u6539\u4e3at+min(3,h)\u7684\u68c0\u67e5\u70b9\uff0c\u771f\u5b9e\u7aef\u53d6\u4e0b\u4e00epoch\u63d0\u4ea4\u65b0\u52a8\u4f5c\u4e4b\u524d\uff1b6\u79d2\u5dee\u5f02\u4ecd\u4e0d\u80fd\u5ffd\u7565\u4e0b\u4e00\u6b21\u91cd\u51b3\u7b56\u3002\u672b\u7aeft27\u4ec53\u79d2\uff0ct30\u53ea\u8bc4\u4ef7\u4e0d\u63d0\u4ea4\u52a8\u4f5c\u3002\u5386\u53f2/FIFO/\u80fd\u8017/\u5b88\u6052\u3001\u5019\u9009\u987a\u5e8f\u3001\u51c0\u5316\u53cc\u751f\u3001checkpoint\u53ca\u540c\u52a8\u4f5c\u771f\u5b9e\u63a8\u8fdb\u9010\u5b57\u6bb5\u68c0\u67e5\u4e0d\u964d\u7ea7\u3002\u672c\u8f6e\u53ea\u5de5\u7a0b\u6d4b\u8bd5\u3001\u4e00\u4e2abranch\u548c\u4e00\u4e2aepoch\u6210\u672c\uff1b\u975e\u5b8c\u6574\u9884\u5b9e\u9a8cPASS\u3002\n'
            write(review/name,'# '+name.removesuffix('.md')+' \u2014 3\u79d2\u5ba1\u9605\u4fee\u8ba2\n\n'+common+params+budgets+extra+'\n\u5b8c\u6574\u672a\u53d8\u6761\u76ee\u9010\u9879\u7ee7\u627f\u5bf9\u5e94\u65e7\u5feb\u7167\uff0c\u4e0d\u8986\u76d6\u539f\u6587\uff1b\u672c\u4fee\u8ba2\u53ea\u5bf9\u5468\u671f\u3001\u68c0\u67e5\u70b9\u3001\u9884\u7b97\u53ca\u672c\u8f6e\u5b9e\u65bd\u72b6\u6001\u5f62\u6210\u660e\u786e\u8986\u76d6\u3002\n')
    paths=list((P/'src').rglob('*.py'))+list((V/'runtime').glob('*.py'))+list((V/'tests').glob('test_n*.py'))
    paths += [c,contract,Path(__file__),A/'cost_measurement.py',A/'seal_revision.py']+list(review.glob('*.md'))
    paths += [V/'acceptance'/b.manifest_path.split('/')[-2]/Path(b.manifest_path).name for b in deps]
    paths += [P/'configs/hardware_gate_c_simplified_v1.json']+[P/'outputs/gate_c_simplified_20260922T064019_313843Z'/f for f in ('terminal_pair_intervals.jsonl','z_ref.json')]
    paths += [P/'data/raw/sgp4_x720'/f for f in ('manifest.json','hashes.json','constellation.tle')]
    version=vc.read_json(V/'version_record.json')
    write(A/manifest_name,dict(schema='dynamic_k_n4_p0_candidate_v1',candidate_revision_id='0010',formal_experiments_authorized=False,
        configuration_path=c.relative_to(P).as_posix(),files=[bind(p) for p in sorted(set(paths))],
        anchors=dict(version_origin=bind(V/'version_record.json'),parent_revision=bind(V/'revisions/0009/record.json'),
                     implementation_0007=bind(V/'revisions/0007/record.json'),baseline_seal=version['baseline_seal'])))
    print(json.dumps(bind(A/manifest_name)),flush=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('prepare','tests','regress','historical','cost','seal'))
    parser.add_argument('--manifest',default='manifest_attempt01.json');parser.add_argument('--sha');parser.add_argument('--attempt',default='attempt01')
    parser.add_argument('--only',nargs='*');args=parser.parse_args()
    if args.command=='prepare':prepare(args.manifest);return 0
    if args.command=='historical':
        r=subprocess.run([sys.executable,'-B',str(V/'acceptance/0006/run_historical_regression.py'),str(A/'historical_regression.json')],
            cwd=P,capture_output=True,text=True,encoding='utf-8')
        write(A/'historical_execution.json',dict(command=r.args,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
        print(r.stdout,flush=True);return 0
    assert args.sha,'Independent candidate hash required'
    guard=P0EvidenceBinding(P,NS+'acceptance/0010/'+args.manifest,args.sha);guard.verify()
    if args.command=='tests':
        m=load('p0_tests',V/'tests/test_n4_p0.py');m.FIXTURES=fixtures();m.BINDING=guard
        result=test_module(m,args.only);result['selected_prefixes']=args.only
        write(A/args.attempt/'p0_tests.json',result)
        if result['status']!='PASS':
            for p in (V/'runtime/n4_p0.py',V/'tests/test_n4_p0.py',Path(__file__)):
                write(A/args.attempt/(p.name+'.snapshot'),p.read_text(encoding='utf-8'))
        print(json.dumps({k:v for k,v in result.items() if k!='output'}),flush=True);return result['status']!='PASS'
    if args.command=='regress':
        b=dependencies();reports={}
        for n,path,attrs in [('N1a','test_n1a.py',('EVIDENCE',)),('N1b','test_n1b_fifo.py',('N1A_BINDING','N1B_BINDING')),
            ('N2','test_n2_actions.py',('N1A_BINDING','N1B_BINDING','N2_BINDING')),
            ('N3','test_n3_baselines.py',('N1A_BINDING','N1B_BINDING','N2_BINDING','N3_BINDING'))]:
            previous=A/('regression_'+n+'.json')
            if previous.exists():
                reports[n]=vc.read_json(previous);assert reports[n]['status']=='PASS'
                print('REUSE_COMPLETED_THIS_TURN '+n,flush=True);continue
            m=load('p0_regression_'+n,V/'tests'/path)
            for a,v in zip(attrs,b):setattr(m,a,v)
            reports[n]=test_module(m);write(A/('regression_'+n+'.json'),reports[n])
        print(json.dumps({k:{x:y for x,y in v.items() if x!='output'} for k,v in reports.items()}),flush=True)
        return not all(r['status']=='PASS' for r in reports.values())
    if args.command=='cost':
        from cost_measurement import run
        return run(guard)
    if args.command=='seal':
        from seal_revision import seal
        return seal(args.manifest,args.sha,args.attempt)
if __name__=='__main__':sys.exit(main())
