"""Eight-node engineering geometry fixture; never a natural K* scene."""
from ..terminal_pair_intervals import TerminalPairCatalog, TerminalPairWindow
from ..gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from .joint_action import canonical_sha256
from .k0_snapshot import SnapshotBudget, INITIALIZATION


def fixture():
    nodes=tuple('X%d_%s'%(p,s) for p in range(4) for s in ('A','B'))
    mapping={n:int(n[1]) for n in nodes}
    fixed=tuple(('X%d_A'%p,'X%d_B'%p) for p in range(4))
    windows=[]
    for p in range(4):
        q=(p+1)%4
        for s in ('A','B'):
            windows.append(TerminalPairWindow('X%d_%s'%(p,s),'D1',
                'X%d_%s'%(q,s),'D2',0.,600.,right_censored=True,
                plane_gap=abs(p-q),distance_km=1000.))
    physical=TerminalPairPhysicalFeasibility(TerminalPairCatalog(windows,mapping))
    setup={'retarget_a_s':1.,'retarget_b_s':1.,'acquisition_s':1.}
    description={'scope':'EIGHT_NODE_SYNTHETIC_ENGINEERING_ONLY','nodes':nodes,
        'fixed_edges':fixed,'plane_by_satellite':mapping,'windows':[w.to_dict() for w in windows],
        'setup':setup,'initialization_convention':INITIALIZATION,
        'controller_or_traffic_invoked':False,'K_star_selected':False}
    return {'nodes':nodes,'fixed_edges':fixed,'plane_by_satellite':mapping,
        'physical_layer':physical,'setup':setup,
        'budget':SnapshotBudget(100000,5.,100000,5.),
        'initialization_convention':INITIALIZATION,
        'input_hashes':{'eight_node_synthetic_fixture':canonical_sha256(description)}},description
