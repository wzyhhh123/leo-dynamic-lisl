"""Additional declared-release and physics rejection coverage, finite windows."""
import support18 as s
from correctness import compare
from dynamic_lisl.terminal_executor import TerminalExecutor,Connect
from dynamic_lisl.terminal_pair_intervals import TerminalPairCatalog,TerminalPairWindow
from dynamic_lisl.gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from runtime.n2_physical import N2PhysicalLayer,SyntheticWindowGuard
from runtime.n2_actions import Add,Drop,Replace,Setup,LinkRef
def main():
    nodes=tuple('X%d_%d'%(p,n) for p in range(4) for n in range(40));a,b=('X0_1','D1'),('X1_1','D2');c,d=('X0_2','D1'),('X1_2','D2')
    cat=TerminalPairCatalog([TerminalPairWindow(a[0],a[1],b[0],b[1],0.,100.),TerminalPairWindow(c[0],c[1],d[0],d[1],0.,100.)],{n:int(n[1]) for n in nodes})
    physical=N2PhysicalLayer(TerminalPairPhysicalFeasibility(cat),SyntheticWindowGuard());ex=TerminalExecutor(nodes);setup=Setup(.5,.5,.5)
    ex.submit([Connect(a,b,100.,0.,0.,0.),Connect(c,d,100.,0.,0.,0.)]);refs=[LinkRef.from_link(x) for x in ex.links.values()]
    rows=[];compare('undeclared_third_party_release',physical,ex,Replace((refs[1],),a,b,setup,'BBM'),rows)
    compare('duplicate_release_ref',physical,ex,Replace((refs[0],refs[0]),c,d,setup,'BBM'),rows)
    compare('unknown_replace_mode',physical,ex,Replace((refs[0],),c,d,setup,'INVALID'),rows)
    for reason in ('LOS_BLOCKED','FOR_FAIL_LOCAL','FOR_FAIL_REMOTE','FOR_FAIL_BILATERAL'):
        idle=TerminalExecutor(nodes);p=N2PhysicalLayer(TerminalPairPhysicalFeasibility(cat),SyntheticWindowGuard({tuple(sorted((a,b))):reason}))
        compare('physics_'+reason,p,idle,Add(a,b,setup),rows)
    s.write('REJECTION_COVERAGE_TUPLE.json',dict(status='PASS',cases=rows,full_catalog=False,synthetic_fixed_rejection_guards=True))
    print('REJECTION_COVERAGE_PASS',flush=True)
if __name__=='__main__':main()
