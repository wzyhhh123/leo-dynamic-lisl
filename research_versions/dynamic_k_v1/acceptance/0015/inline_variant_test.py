"""Supplement the frozen P0 inline observer import using an explicit local seam.

Only constructor selection changes in a copied in-memory method. Every original
test assertion remains verbatim, and frozen modules/classes are never patched.
"""
import ast,inspect,textwrap,types,unittest
import support as w
from runtime.n4_p0r_handle_reader import HandleReaderLease
def main():
    deps=w.old.old.dependencies();g=w.old.guard()
    with HandleReaderLease(deps+[g],w.vc) as lease:
        f=w.old.old.load('p0f_inline_fixture',w.V/'tests/test_n3_baselines.py')
        f.N1A_BINDING,f.N1B_BINDING,f.N2_BINDING,f.N3_BINDING=[lease.guard(x) for x in deps];w.bind_test_module(f,'variant')
        m=w.old.old.load('p0f_inline_frozen',w.V/'tests/test_n4_p0.py');m.FIXTURES=f;m.BINDING=lease.guard(g)
        selected=[]
        for name in unittest.defaultTestLoader.getTestCaseNames(m.P0Tests):
            source=textwrap.dedent(inspect.getsource(getattr(m.P0Tests,name)))
            needle='from runtime.n1b_observer import ObservedD2Engine'
            if needle not in source:continue
            replacement=source.replace(needle,'ObservedD2Engine = FIXTURES.ObservedD2Engine')
            namespace={};exec(compile(replacement,'<p0f_local_inline_fixture>','exec'),m.__dict__,namespace)
            selected.append((name,namespace[name],source,replacement))
        assert len(selected)==1
        local=type('P0InlineVariantTest',(unittest.TestCase,),{name:fn for name,fn,_,_ in selected})
        temp=types.ModuleType('p0f_inline_explicit_suite');temp.P0InlineVariantTest=local
        r=w.old.old.test_module(temp);r.update(original_test_names=[x[0] for x in selected],
            original_source=[x[2] for x in selected],constructor_seam_source=[x[3] for x in selected],
            frozen_test_expectations_changed=False,global_monkeypatch=False)
        w.write(w.A/'variant_P0_inline_constructor_test.json',r)
        print(r['status'],r['tests_run'],flush=True);return r['status']!='PASS'
if __name__=='__main__':raise SystemExit(main())
