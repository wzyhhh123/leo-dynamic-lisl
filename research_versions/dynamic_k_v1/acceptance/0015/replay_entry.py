"""Post-seal read-only variant recovery, latest independent anchor required."""
import argparse,os,sys,hashlib
from pathlib import Path
import support as w
import variant_worker as worker
def main():
    q=argparse.ArgumentParser();q.add_argument('--expected-revision-sha256',required=True);args=q.parse_args()
    _,_,expected,*_=w.vc.load_expected(w.P,w.ORIGIN,args.expected_revision_sha256)
    assert w.vc.file_info(w.V/'revisions/0014/record.json')['sha256']==w.PARENT
    recipe=Path(w.A/'replay_recipe.json');rel=recipe.relative_to(w.P).as_posix()
    assert w.vc.file_info(recipe)==expected[rel],'RECIPE_NOT_REGISTERED_OR_MODIFIED'
    anchor=w.A/'root_artifact_anchor.json'
    assert w.vc.file_info(anchor)==expected[anchor.relative_to(w.P).as_posix()]
    for r in w.vc.read_json(anchor)['files']:assert w.info(Path(r['path']))==r
    d=w.vc.read_json(recipe)
    def verify():
        assert os.environ.get('PYTHONHASHSEED')=='1414'
        assert sys.version==d['python']
        for r in d['bound_files']:assert w.info(Path(r['path']))==r
        w.binding().verify();return d
    worker.verify=verify
    c,root=worker.build(w.A)
    reports={}
    for name,obj in [('LIVE_PRE_ACTION',c),('SANITIZED_PRE_ACTION',root.atomic),('ROOT',root)]:
        path=w.A/'ROOT_BASELINE'/('ROOT_FULL_STATE.json' if name=='ROOT' else name+'_FULL_STATE.json')
        old=w.vc.read_json(path);actual=worker.fs.capture(obj);diff=worker.fs.first_diff(old,actual)
        reports[name]=dict(exact_equal=diff is None,first_difference=diff,actual_sha256=worker.fs.sha(actual))
    assert all(x['exact_equal'] for x in reports.values()),'DURABLE_VARIANT_REPLAY_MISMATCH'
    import json
    print(json.dumps(dict(status='DURABLE_VARIANT_REPLAY_PASS',independent_revision_sha256=args.expected_revision_sha256,
        complete_state_comparisons=reports,actions_submitted=0,prediction_branches=0,files_written=0)),flush=True)
if __name__=='__main__':main()
