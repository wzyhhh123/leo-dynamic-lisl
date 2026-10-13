"""Correct instrumentation's delegated-return double count, not measurements.

Only dependency verification is observed; no new business prediction branch.
"""
import workflow as w
from trace_costs import CallTrace
from runtime.n4_p0r_handle_reader import HandleReaderLease
class LeafTrace(CallTrace):
    def classify(self,f):
        if f.f_code.co_name=='raw_info' and f.f_code.co_filename.startswith('<N4_P0R_'):
            return 'fresh_raw_reader_dispatch'
        return super().classify(f)
def main():
    guards=w.old.dependencies()+[w.guard()];out=[]
    with HandleReaderLease(guards,w.vc) as lease:
        for g in guards:
            h=lease.guard(g);before_reads=lease.reads;before_bytes=lease.bytes_hashed
            actual,trace=LeafTrace().run(h.verify);expected=g.verify();assert actual==expected
            assert trace['raw_sha256_total_bytes']==lease.bytes_hashed-before_bytes
            assert sum(row['calls'] for row in trace['raw_files'].values())==lease.reads-before_reads
            out.append(dict(guard=type(g).__name__,actual_native_reads=lease.reads-before_reads,
                actual_native_bytes_hashed=lease.bytes_hashed-before_bytes,trace=trace,descriptor_exact=True))
    w.write('immutable_dependency_actual_leaf_counts.json',dict(status='PASS_COUNTER_RECONCILIATION',guards=out,
        original_instrumentation_note='Earlier raw_info delegated return was also counted; raw trace retained; this excludes the outer delegated return and reconciles with actual native reads.'))
    # Repair byte/read totals of existing paired traces independently. Every
    # successful N1a verification has the exact same raw file multiset.
    manifest=w.vc.read_json(w.P/guards[0].manifest_path)
    multiset=[dict(path=guards[0].manifest_path,**w.vc.file_info(w.P/guards[0].manifest_path))]+manifest['files']+list(manifest['anchors'].values())
    one_bytes=sum(r['byte_count'] for r in multiset);one_reads=len(multiset);pair={}
    for instrumented in (True,):
        artifact=w.vc.read_json(w.A/'paired_handle_instrumented.json');sections={}
        for section in ('root','branch'):
            trace=artifact[section];delegated=trace['call_rows'].get('<N4_P0R_FRESH_HANDLE_SHA_ADAPTER>:raw_info',{}).get('calls',0)
            assert delegated%one_reads==0;verify_count=delegated//one_reads
            rows={k:dict(v) for k,v in trace['raw_files'].items()}
            for row in multiset:
                key=str(w.P/row['path']);rows[key]['calls']-=verify_count;rows[key]['bytes_hashed']-=verify_count*row['byte_count']
            sections[section]=dict(actual_reads=sum(r['calls'] for r in rows.values()),actual_bytes_hashed=sum(r['bytes_hashed'] for r in rows.values()),
                removed_delegated_returns=delegated,removed_delegated_bytes=verify_count*one_bytes,actual_files=rows)
        assert sum(s['actual_reads'] for s in sections.values())==artifact['fresh_native_file_reads']
        assert sum(s['actual_bytes_hashed'] for s in sections.values())==artifact['fresh_native_bytes_hashed']
        pair['paired_handle_instrumented']=sections
    w.write('paired_trace_native_counter_reconciliation.json',dict(status='PASS',sections=pair,
        timing_values_unchanged=True,old_raw_reports_preserved=True,state_hash_calls_not_changed=True))
if __name__=='__main__':main()
