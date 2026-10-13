"""Create immutable executable reconstruction recipe before any simulation."""
import sys,os,json,hashlib,importlib.metadata,platform
from pathlib import Path
A=Path(__file__).resolve().parent;V=A.parents[1];P=V.parents[1]
sys.path[:0]=[str(A),str(V/'acceptance/0011'),str(V),str(P/'src')]
import workflow as old
import replay_worker as w
import numpy,sgp4
def main():
    expected=old.vc.load_expected(P,w.ORIGIN,w.PARENT)[2]
    project=list((P/'src').rglob('*.py'))+list((V/'runtime').rglob('*.py'))
    project+=[V/'tests/test_n3_baselines.py',V/'tools/version_control.py',V/'tools/version_control_readme_v1.py']
    for n in ('0010','0011'):project+=list((V/'acceptance'/n).glob('*.py'))
    project+=[V/'acceptance/0012/event_auditor.py']
    for binding in old.old.dependencies()+[old.guard()]:
        binding.verify();doc=old.vc.read_json(P/binding.manifest_path)
        project.append(P/binding.manifest_path)
        for row in doc['files']+list(doc['anchors'].values()):
            if row['path'].startswith('research_versions/dynamic_k_v1/revisions/'):continue
            project.append(P/row['path'])
    for name in ('outputs/gate_c_simplified_20260922T064019_313843Z/z_ref.json',
        'outputs/gate_c_simplified_20260922T064019_313843Z/terminal_pair_intervals.jsonl',
        'configs/hardware_gate_c_simplified_v1.json','data/raw/sgp4_x720/manifest.json',
        'data/raw/sgp4_x720/hashes.json','data/raw/sgp4_x720/constellation.tle'):project.append(P/name)
    for p in set(project):
        if p==V/'version_record.json':
            assert old.vc.file_info(p)['sha256']==w.ORIGIN,'VERSION_ORIGIN_DRIFT'
        else:assert old.vc.file_info(p)==expected[p.relative_to(P).as_posix()],'SOURCE_DRIFT:'+str(p)
    external=[Path(sys.executable)]
    external+=list(Path(sys.executable).parent.glob('python*.dll'))
    for package in (numpy,sgp4):
        external+=[p for p in Path(package.__file__).parent.rglob('*') if p.is_file() and p.suffix.lower() in ('.py','.pyd','.dll')]
    # Source and compiled dependencies actually imported by this worker are also pinned.
    for m in tuple(sys.modules.values()):
        p=getattr(m,'__file__',None)
        if p and Path(p).is_file() and Path(p).suffix.lower() in ('.py','.pyd','.dll'):external.append(Path(p))
    script_files=list(A.glob('*.py'))
    files=sorted(set(p.resolve() for p in project+external+script_files),key=str)
    environment=dict(PYTHONHASHSEED='1414',python_version=sys.version,python_executable=sys.executable,
        platform=platform.platform(),numpy=importlib.metadata.version('numpy'),sgp4=importlib.metadata.version('sgp4'))
    recipe=dict(schema='dynamic_k_p0e_executable_complete_reconstruction_v1',scenario_id=w.SCENE,
        origin_sha256=w.ORIGIN,parent_revision_sha256=w.PARENT,environment=environment,
        bound_files=[w.info(p) for p in files],
        constructor='Bound acceptance/0011/controlled_cost.py real_fixture used as input recipe, not old failure root',
        trace=dict(commodity_ids=['f_bg','f_hot'],segments=[dict(start_s=0.,end_s=8.,rates_bit_s=dict(f_bg=200000.,f_hot=400000.)),
            dict(start_s=8.,end_s=20.,rates_bit_s=dict(f_bg=200000.,f_hot=1200000.))]),
        initial_link=dict(a=['X0_1','D2'],b=['X1_1','D1'],expiry_s=600.,setup_s=0.),
        capacity_bit_s=1e6,root_time_s=3.,T_s=30.,T_A_s=20.,mode='PERSIST',H_s=6.,
        decision_cadence_s=3.,cuts_s=[6.,9.],
        add_pair=[['X0_10','D2'],['X1_10','D1']],setup=dict(retarget_a_s=.5,retarget_b_s=.5,acquisition_s=.5),
        state_comparison='Every typed Python graph field, aliases, insertion and list/set iteration order, ndarray bytes; native SGP4 reconstructed by bound TLE+binary and full call recipe, exposed native fields compared',
        native_checkpoint_pickle_claimed=False,executable_reconstruction_from_t0=True,
        branch_budget=dict(HOLD=1,ADD=1),prediction_requires_independent_clean_rebuild_pass=True,
        original_0011_failure_replay_claimed=False,formal_experiments_authorized=False,
        scientific_parameters={k:None for k in ('T_A_s','T_s','tau_res_s','R_min','alpha','D_ref_s','E_ref_J')})
    w.write(A/'replay_recipe.json',recipe)
    print(json.dumps(dict(status='RECIPE_BOUND',files=len(files),recipe=w.info(A/'replay_recipe.json'))),flush=True)
if __name__=='__main__':main()
