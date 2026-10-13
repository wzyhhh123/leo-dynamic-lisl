"""Append-only N4-P0R acceptance. Does not run pilot experiments."""
import argparse,importlib.util,json,sys,time,unittest
from pathlib import Path
V=Path(__file__).resolve().parents[2];P=V.parents[1];A=Path(__file__).parent
sys.path[:0]=[str(V),str(P/'src')]
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
old=load('p0r_old_workflow',V/'acceptance/0010/workflow.py');vc=old.vc
from runtime.n4_p0 import P0EvidenceBinding
from runtime.n4_p0r_reader import ReaderLease
from runtime.n4_p0r_handle_reader import HandleReaderLease
def write(name,data):
    p=A/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(data,f,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
def guard():return P0EvidenceBinding(P,old.NS+'acceptance/0010/manifest_final.json','8d15d8492b4662ad554b4cc25b27d4b3954fcbf340f9b38b5468de5bcfa17ebf')
def setup(lease=None):
    f=old.load('p0r_fixture',V/'tests/test_n3_baselines.py');deps=old.dependencies()
    if lease:deps=[lease.guard(g) for g in deps]
    f.N1A_BINDING,f.N1B_BINDING,f.N2_BINDING,f.N3_BINDING=deps;return f
def suite(mode):
    g=guard();deps=old.dependencies()
    def run(lease):
        f=setup(lease);m=old.load('p0r_frozen_tests_'+mode,V/'tests/test_n4_p0.py');m.FIXTURES=f;m.BINDING=lease.guard(g) if lease else g
        result=old.test_module(m);result['frozen_test_source_unmodified']=True;result['mode']=mode
        write('p0_'+mode+'.json',result)
        if lease:write('reader_adapter_source_audit_'+mode+'.json',lease.audit)
        print(json.dumps({k:v for k,v in result.items() if k!='output'}),flush=True)
        return 0 if result['status']=='PASS' else 1
    if mode=='original':return run(None)
    with (HandleReaderLease if mode=='handle' else ReaderLease)(deps+[g],vc) as lease:return run(lease)
def regress(mode):
    deps=old.dependencies();g=guard()
    with HandleReaderLease(deps+[g],vc) as lease:
        b=[lease.guard(x) for x in deps]
        for n,path,attrs in [('N1a','test_n1a.py',('EVIDENCE',)),('N1b','test_n1b_fifo.py',('N1A_BINDING','N1B_BINDING')),
            ('N2','test_n2_actions.py',('N1A_BINDING','N1B_BINDING','N2_BINDING')),('N3','test_n3_baselines.py',('N1A_BINDING','N1B_BINDING','N2_BINDING','N3_BINDING'))]:
            m=old.load('p0r_reg_'+n,V/'tests'/path)
            for a,v in zip(attrs,b):setattr(m,a,v)
            if n=='N3':
                expected=vc.load_expected(P,'ce3fe1dfd2291714508c5a0f907b83711675a01079bca8a7229d99cb75fce691','fa9564caf795279ce608cf7ff31c9a86693c7336238b285a52c95c7ffb66c897')[2]
                cp=V/'acceptance/0007/attempt01/catalog_coverage.json';rel=cp.relative_to(P).as_posix()
                assert vc.file_info(cp)==expected[rel];m.PRIOR_CATALOG_EVIDENCE=(cp,expected[rel]['sha256'])
            r=old.test_module(m);r['reader_mode']='FRESH_HANDLE_SHA256_PATH_PINS';write('final_regression_'+n+'.json',r)
            if n=='N3':write('n3_retained_coverage_validation.json',m.COVERAGE)
            print(n+' '+str(r['status'])+' '+str(r['tests_run']),flush=True)
            if r['status']!='PASS':return 1
    return 0
if __name__=='__main__':
    q=argparse.ArgumentParser();q.add_argument('command',choices=('original','optimized','handle','regress'));args=q.parse_args()
    sys.exit(regress(args.command) if args.command=='regress' else suite(args.command))
