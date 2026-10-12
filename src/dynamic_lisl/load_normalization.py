"""Maximum-concurrent-flow calibration on the frozen reference graph."""
from __future__ import annotations

import math
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix


def maximum_concurrent_flow(nodes, directed_edges, capacities_bit_s,
                            commodities, reference_shape):
    nodes = tuple(sorted(nodes))
    edges = tuple(sorted(set(tuple(edge) for edge in directed_edges)))
    commodities = tuple(sorted(commodities))
    if set(reference_shape) != {item.commodity_id for item in commodities}:
        raise ValueError("REFERENCE_SHAPE_COMMODITY_MISMATCH")
    if any(value < 0.0 or not math.isfinite(value) for value in reference_shape.values()):
        raise ValueError("INVALID_REFERENCE_SHAPE")
    shape_sum = sum(reference_shape.values())
    if abs(shape_sum-1.0) > 1e-12:
        raise ValueError("REFERENCE_SHAPE_NOT_NORMALIZED")
    capacity = ({edge: float(capacities_bit_s[edge]) for edge in edges}
                if isinstance(capacities_bit_s, dict)
                else {edge: float(capacities_bit_s) for edge in edges})
    if any(value <= 0.0 or not math.isfinite(value) for value in capacity.values()):
        raise ValueError("INVALID_MCF_CAPACITY")

    edge_index = {edge: index for index, edge in enumerate(edges)}
    flow_variables = len(commodities)*len(edges)
    alpha_index = flow_variables
    variable_count = flow_variables+1

    eq_row = []
    eq_col = []
    eq_data = []
    eq_rhs = []
    row = 0
    for f_index, commodity in enumerate(commodities):
        for node in nodes:
            for edge_index_value, (a, b) in enumerate(edges):
                column = f_index*len(edges)+edge_index_value
                if a == node:
                    eq_row.append(row); eq_col.append(column); eq_data.append(1.0)
                if b == node:
                    eq_row.append(row); eq_col.append(column); eq_data.append(-1.0)
            if node == commodity.source:
                eq_row.append(row); eq_col.append(alpha_index)
                eq_data.append(-reference_shape[commodity.commodity_id])
            elif node == commodity.destination:
                eq_row.append(row); eq_col.append(alpha_index)
                eq_data.append(reference_shape[commodity.commodity_id])
            eq_rhs.append(0.0)
            row += 1
    a_eq = coo_matrix((eq_data, (eq_row, eq_col)),
                      shape=(row, variable_count)).tocsr()

    ub_row = []
    ub_col = []
    ub_data = []
    ub_rhs = []
    for e_index, edge in enumerate(edges):
        for f_index in range(len(commodities)):
            ub_row.append(e_index)
            ub_col.append(f_index*len(edges)+e_index)
            ub_data.append(1.0)
        ub_rhs.append(capacity[edge])
    a_ub = coo_matrix((ub_data, (ub_row, ub_col)),
                      shape=(len(edges), variable_count)).tocsr()
    objective = np.zeros(variable_count)
    objective[alpha_index] = -1.0
    result = linprog(objective, A_ub=a_ub, b_ub=np.asarray(ub_rhs),
                     A_eq=a_eq, b_eq=np.asarray(eq_rhs),
                     bounds=(0.0, None), method="highs")
    if not result.success:
        raise ValueError("MAXIMUM_CONCURRENT_FLOW_FAILED: " + result.message)
    alpha = float(result.x[alpha_index])
    flows = {}
    edge_load = {edge: 0.0 for edge in edges}
    for f_index, commodity in enumerate(commodities):
        for e_index, edge in enumerate(edges):
            value = float(result.x[f_index*len(edges)+e_index])
            if value > max(1e-6, alpha*1e-12):
                flows[(commodity.commodity_id, edge)] = value
            edge_load[edge] += value
    utilization = {edge: edge_load[edge]/capacity[edge] for edge in edges}
    return {
        "alpha_star_bit_s": alpha,
        "solver": "scipy.optimize.linprog(method=highs)",
        "reference_shape": dict(sorted(reference_shape.items())),
        "edge_load_bit_s": {edge[0] + "->" + edge[1]: value
                            for edge, value in edge_load.items() if value > 0.0},
        "edge_utilization": {edge[0] + "->" + edge[1]: value
                             for edge, value in utilization.items() if value > 0.0},
        "maximum_edge_utilization": max(utilization.values(), default=0.0),
        "saturated_edges": [edge[0] + "->" + edge[1] for edge, value in utilization.items()
                            if value >= 1.0-1e-8],
        "nonzero_flow_variable_count": len(flows),
        "flow_conservation_max_residual": float(np.max(np.abs(a_eq @ result.x))),
        "capacity_max_excess_bit_s": max(
            0.0, max((edge_load[edge]-capacity[edge] for edge in edges), default=0.0)),
        "status": "PASS",
    }


def scaled_rates(alpha_star_bit_s, rho, spatial_shape):
    if rho < 0.0 or abs(sum(spatial_shape.values())-1.0) > 1e-12:
        raise ValueError("INVALID_RHO_OR_SPATIAL_SHAPE")
    return {key: float(rho)*float(alpha_star_bit_s)*float(value)
            for key, value in spatial_shape.items()}
