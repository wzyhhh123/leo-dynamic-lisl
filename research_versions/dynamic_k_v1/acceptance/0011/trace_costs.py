"""Actual call-chain/raw-byte/JSON tracing. Profiler overhead is disclosed."""
from collections import Counter,defaultdict
import sys,time

class CallTrace:
    def __init__(self):
        self.stack=[];self.parts=defaultdict(float);self.calls=Counter();self.rows={};self.raw={};self.json=[];self.sha=Counter();self.last=0.;self.callbacks=0
    def classify(self,f):
        name=f.f_code.co_name;file=f.f_code.co_filename.replace('\\','/');obj=f.f_locals.get('self')
        if name=='verify' and type(obj).__name__.endswith('Binding'):return 'immutable_dependency_verification'
        if name in ('safe_path','checked_path'):return 'path_namespace_validation'
        if name in ('file_info','raw_info') and ('/n4_p0r_reader.py' in file or '/n4_p0r_handle_reader.py' in file):return 'fresh_raw_reader_dispatch'
        if name=='_read_verified':return 'fresh_raw_file_sha256'
        if name in ('file_info','raw_info'):return 'fresh_raw_file_sha256'
        if file.endswith('/json/__init__.py') and name in ('loads','dumps'):return 'json_'+name
        if name in ('_verify','_physical_digest') and file.endswith('/n2_controller.py'):return 'dynamic_physical_and_clock_guard'
        if name in ('data_hash','digest','canonical_state_sha256','sha256'):return 'state_or_evidence_sha256'
        if file.endswith('/n1b_fifo.py'):return 'fifo'
        if file.endswith('/transition_service_orchestrator.py'):return 'network'
        if file.endswith('/n1a.py') and type(obj).__name__=='TerminalEnergyLedger':return 'energy'
        return None
    def account(self):
        now=time.perf_counter();self.parts[self.stack[-1][1] if self.stack else 'other']+=now-self.last;self.last=now
    def callback(self,f,event,arg):
        self.callbacks+=1
        if event=='call':
            cat=self.classify(f)
            if not cat:return
            self.account();key=f.f_code.co_filename.replace('\\','/')+':'+f.f_code.co_name
            self.calls[key]+=1;self.stack.append((f,cat,time.perf_counter(),key))
            row=self.rows.setdefault(key,dict(category=cat,calls=0,inclusive_wallclock_s=0.,caller_chains=Counter()))
            row['calls']+=1;chain=[];q=f.f_back
            for _ in range(7):
                if q is None:break
                chain.append(q.f_code.co_filename.replace('\\','/').split('/')[-1]+':'+q.f_code.co_name);q=q.f_back
            row['caller_chains'][' <- '.join(chain)]+=1
        elif event=='return' and self.stack and self.stack[-1][0] is f:
            self.account();_,cat,start,key=self.stack.pop();self.rows[key]['inclusive_wallclock_s']+=time.perf_counter()-start
            if cat=='fresh_raw_file_sha256' and isinstance(arg,dict) and 'byte_count' in arg:
                path=str(f.f_locals.get('path'));r=self.raw.setdefault(path,dict(calls=0,bytes_hashed=0,per_call_byte_count=arg['byte_count'],sha256=arg['sha256']))
                r['calls']+=1;r['bytes_hashed']+=arg['byte_count']
            if cat in ('json_loads','json_dumps'):
                s=f.f_locals.get('s') if cat=='json_loads' else arg
                self.json.append(dict(kind=cat,characters=len(s) if isinstance(s,(str,bytes)) else None,
                    caller=f.f_back.f_code.co_name if f.f_back else None))
        elif event=='c_call' and (getattr(arg,'__module__','')=='_hashlib' or type(getattr(arg,'__self__',None)).__module__=='_hashlib'):
            self.sha[(getattr(arg,'__name__','unknown'),self.stack[-1][1] if self.stack else 'other')]+=1
    def run(self,fn):
        if sys.getprofile() is not None:raise ValueError('NESTED_PROFILER_FORBIDDEN')
        self.last=time.perf_counter();start=self.last;sys.setprofile(self.callback)
        try:r=fn()
        finally:sys.setprofile(None);self.account()
        rows={k:{**v,'caller_chains':dict(v['caller_chains'])} for k,v in self.rows.items()}
        return r,dict(wallclock_s=time.perf_counter()-start,exclusive_instrumented_s=dict(self.parts),
            call_rows=rows,raw_files=self.raw,raw_sha256_total_bytes=sum(r['bytes_hashed'] for r in self.raw.values()),
            distinct_raw_files=len(self.raw),json_operations=self.json,
            native_sha256_constructor_calls=[dict(function=k[0],category=k[1],calls=v) for k,v in self.sha.items()],
            profiler_callback_events=self.callbacks,instrumentation='sys.setprofile; exclusive totals INCLUDE callback overhead; not production timing')

def guard_diagnostic(suffix=''):
    import workflow as w
    guards=w.old.dependencies()+[w.guard()];reports=[]
    for g in guards:
        start=time.perf_counter();a=g.verify();plain=time.perf_counter()-start
        b,trace=CallTrace().run(g.verify);assert a==b
        reports.append(dict(guard=type(g).__name__,manifest=g.manifest_path,plain_wallclock_s=plain,trace=trace,descriptor_equal=True))
    w.write('actual_binding_callchain_original'+suffix+'.json',reports)
    from runtime.n4_p0r_handle_reader import HandleReaderLease
    with (HandleReaderLease if 'handle' in suffix else w.ReaderLease)(guards,w.vc) as lease:
        reports=[]
        for g in guards:
            h=lease.guard(g);start=time.perf_counter();a=h.verify();plain=time.perf_counter()-start
            b,trace=CallTrace().run(h.verify);assert a==b==g.verify()
            reports.append(dict(guard=type(g).__name__,plain_wallclock_s=plain,trace=trace,descriptor_equal=True))
        w.write('actual_binding_callchain_path_pinned'+suffix+'.json',reports)

if __name__=='__main__':guard_diagnostic(sys.argv[1] if len(sys.argv)>1 else '')
