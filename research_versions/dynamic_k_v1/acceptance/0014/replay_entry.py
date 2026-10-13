"""Durable clean-process read-only recovery after revision chain advances.

Original recipe/worker/source bytes are retained. The supplied independent
current revision anchor validates the complete chain; original parent and every
root artifact/input binding are additionally checked, never silently replaced.
No branch actions or prediction entry points exist in this launcher.
"""
import argparse,hashlib,json,os,sys
from pathlib import Path
import replay_worker as w
import full_state as fs
RECIPE_SHA='da5c7ddfade01045cdea1f787e3802fe75d56d16c5ca8c0b5c86c3e050551916'
ARTIFACT_ANCHOR_SHA='918f57102a8ccf00db087a6fafd6f48ebdc6de82cb67353cfbc621331ead3dc0'
def main():
    q=argparse.ArgumentParser();q.add_argument('--expected-revision-sha256',required=True)
    q.add_argument('--output');args=q.parse_args()
    A=w.A;P=w.P;V=w.V
    assert hashlib.sha256((A/'replay_recipe.json').read_bytes()).hexdigest()==RECIPE_SHA,'REPLAY_RECIPE_ANCHOR'
    anchor=A/'independent_root_evidence_anchor.json'
    assert hashlib.sha256(anchor.read_bytes()).hexdigest()==ARTIFACT_ANCHOR_SHA,'ROOT_ARTIFACT_ANCHOR'
    for row in w.vc.read_json(anchor)['files']:assert w.info(Path(row['path']))==row,'ROOT_ARTIFACT_DRIFT'
    d=w.vc.read_json(A/'replay_recipe.json')
    def verify():
        assert os.environ.get('PYTHONHASHSEED')==d['environment']['PYTHONHASHSEED'],'REPLAY_SEED'
        assert sys.version==d['environment']['python_version'],'REPLAY_PYTHON_VERSION'
        assert sys.executable.lower()==d['environment']['python_executable'].lower(),'REPLAY_EXECUTABLE'
        for row in d['bound_files']:assert w.info(Path(row['path']))==row,'REPLAY_FILE_BINDING:'+row['path']
        w.vc.load_expected(P,w.ORIGIN,args.expected_revision_sha256)
        assert w.vc.file_info(V/'revisions/0013/record.json')['sha256']==w.PARENT,'ORIGINAL_PARENT_ANCHOR'
        w.builder.stage_manifest('c23f188ebc7bfcea9b04d53749d9111b48872ac46ac3eec84669263378de5ec7')
        return d
    # Only the verification lifecycle seam is changed; constructor, state codec,
    # all N1a/b/N2/SGP4 methods and original per-file checks remain unchanged.
    w.verify_recipe=verify
    live,root,_=w.build(A,audit_prefix=False)
    comparisons={}
    for name,obj in [('LIVE_PRE_ACTION',live),('SANITIZED_PRE_ACTION',root.atomic),('ROOT',root)]:
        path=A/'ROOT_BASELINE'/('ROOT_FULL_STATE.json' if name=='ROOT' else name+'_FULL_STATE.json')
        expected=w.vc.read_json(path);actual=fs.capture(obj);diff=fs.first_diff(expected,actual)
        comparisons[name]=dict(exact_all_fields_equal=diff is None,expected_sha256=fs.sha(expected),
            actual_sha256=fs.sha(actual),first_difference=diff)
    baseline=w.vc.read_json(A/'ROOT_BASELINE/root_binding.json')
    hashes=dict(causal_root=root.view.state_sha256==baseline['root_view_sha256'],
        forecast=root.forecast.sha256==baseline['forecast_sha256'],prefix=root.prefix_sha256==baseline['prefix_sha256'])
    ok=all(r['exact_all_fields_equal'] for r in comparisons.values()) and all(hashes.values())
    result=dict(status='DURABLE_ROOT_RECONSTRUCTION_PASS' if ok else 'STOP_DURABLE_RECONSTRUCTION_MISMATCH',
        scenario_id=w.SCENE,clean_process=True,pid=os.getpid(),hash_seed=os.environ['PYTHONHASHSEED'],
        supplied_latest_revision_sha256=args.expected_revision_sha256,original_parent_sha256=w.PARENT,
        recipe_sha256=RECIPE_SHA,root_artifact_anchor_sha256=ARTIFACT_ANCHOR_SHA,
        complete_state_comparisons=comparisons,hashes=hashes,
        prediction_branches=0,actions_submitted=0,project_files_written=bool(args.output),
        exact_original_0011_replay_claimed=False)
    if args.output:w.write(Path(args.output),result)
    print(json.dumps(result),flush=True)
    assert ok,'STOP_DURABLE_RECONSTRUCTION_MISMATCH'
if __name__=='__main__':main()
