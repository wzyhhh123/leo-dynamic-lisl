"""K1 candidate construction; formal K* audit approval is an external gate."""
from ..terminal_executor import Connect,TerminalExecutor
from .joint_action import canonical_sha256
from .structural import graph_structure


def build_k1_candidate(nodes,fixed_edges,solver_result,physical_layer,*,plane_by_satellite,
                       target_K,retarget_a_s,retarget_b_s,acquisition_s,initialization_convention):
    if solver_result['status']!='EXACT' or not solver_result.get('optimality_certified'):
        raise ValueError('K1_REQUIRES_CERTIFIED_EXACT_STRUCTURAL_SOLUTION')
    if solver_result['target_K']!=target_K or len(solver_result['bindings'])!=target_K:
        raise ValueError('K1_EXACT_K_MISMATCH')
    if initialization_convention!='PREESTABLISHED_AT_ZERO_WITH_FORWARD_GATE_C_CERTIFICATE':
        raise ValueError('EXPLICIT_SCIENTIFIC_INITIALIZATION_CONVENTION_REQUIRED')
    executor=TerminalExecutor(nodes);certificates=[];commands=[]
    for ends in solver_result['bindings']:
        a,b=ends
        if plane_by_satellite[a[0]]==plane_by_satellite[b[0]]:raise ValueError('K1_NOT_INTER_PLANE')
        p=physical_layer.evaluate(executor,a,b,retarget_a=retarget_a_s,retarget_b=retarget_b_s,acquisition=acquisition_s)
        if not p['accepted']:raise ValueError('K1_GATE_C_REJECT:'+p['reason'])
        certificates.append({'endpoints':ends,'geometry':p['geometry']})
        commands.append(Connect(a,b,p['geometry']['window']['end_s'],0,0,0))
    executor.submit(commands)
    structure=graph_structure(nodes,fixed_edges,solver_result['bindings'])
    if not structure['connected']:raise ValueError('K1_INITIAL_GRAPH_DISCONNECTED')
    executor.assert_invariants()
    doc={'schema':'f3_v2_k1_candidate_v1','status':'DRAFT_NOT_FROZEN','target_K':target_K,
         'nodes':tuple(nodes),'fixed_edges':tuple(fixed_edges),'bindings':solver_result['bindings'],
         'structural_solver_sha256':solver_result['structural_sha256'],
         'initialization_convention':initialization_convention,
         'initialization_status':'REQUIRES_HUMAN_FREEZE; pre-established initial links, not forward setup completed at0',
         'forward_Gate_C_certificates':certificates,'structure':structure,'terminal_state':executor.snapshot(),
         'batch_compatibility_status':'REQUIRES_SEPARATE_DIAGNOSTIC','K_star_selected_by_this_helper':False}
    doc['candidate_sha256']=canonical_sha256(doc)
    return executor,doc
