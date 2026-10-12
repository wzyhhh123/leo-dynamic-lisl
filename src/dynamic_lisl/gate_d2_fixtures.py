"""Preregistered deterministic Gate D2 correctness fixtures."""
from __future__ import annotations

import json
from pathlib import Path

from .commodity import Commodity
from .common import PROJECT, read_json
from .gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility
from .gate_d_scenarios import Sgp4EdgeDelayProvider
from .operational_policy import OperationalPolicy
from .sgp4_model import Sgp4Model
from .terminal_executor import Connect, TerminalExecutor
from .terminal_pair_intervals import TerminalPairCatalog, TerminalPairWindow
from .traffic_trace import PiecewiseConstantTrafficTrace, TrafficSegment
from .transition_service_orchestrator import (
    ScriptedProposal, TransitionAwareNetworkServiceEngine,
)


GBIT = 1e9


class ConstantDelay:
    def __init__(self, default_s=1e-12, overrides=None):
        self.default_s = float(default_s)
        self.overrides = {tuple(edge): float(value)
                          for edge, value in (overrides or {}).items()}

    def __call__(self, edge, time_s):
        return self.overrides.get(tuple(edge), self.default_s)


def _trace(rates, horizon_s):
    return PiecewiseConstantTrafficTrace(
        tuple(sorted(rates)),
        (TrafficSegment(0.0, float(horizon_s), dict(rates), "constant"),),
    )


def _catalog(nodes, records):
    windows = [TerminalPairWindow(**row) for row in records]
    return TerminalPairCatalog(windows, {node: index for index, node in enumerate(nodes)})


def _window(a, da, b, db, end_s=30.0):
    if (a, da) > (b, db):
        a, da, b, db = b, db, a, da
    return dict(sat_a=a, terminal_a=da, sat_b=b, terminal_b=db,
                start_s=0.0, end_s=float(end_s), parent_start_s=0.0,
                parent_end_s=float(end_s), plane_gap=1, distance_km=1000.0)


def _activate(executor, a, b, end_s=30.0):
    executor.submit([Connect(tuple(a), tuple(b), float(end_s), 0.0, 0.0, 0.0)])


def _engine(nodes, fixed, commodities, rates, horizon, executor, actions,
            delay=None, capacity=10*GBIT):
    return TransitionAwareNetworkServiceEngine(
        nodes, fixed, capacity, commodities, _trace(rates, horizon),
        delay or ConstantDelay(), executor, actions,
        conservation_abs_tolerance_bits=1.0,
        conservation_relative_tolerance=1e-12,
        state_tolerance_bits=0.01,
    )


def fixture_a_bbm_forced_outage():
    nodes = ("A", "B", "C", "D")
    fixed = (("A", "B"), ("C", "D"))
    commodities = (Commodity("f0", "A", "D"),)
    executor = TerminalExecutor(nodes)
    _activate(executor, ("B", "D1"), ("C", "D1"))
    physical = TerminalPairPhysicalFeasibility(_catalog(
        nodes, [_window("B", "D1", "D", "D1")]))
    action = ScriptedProposal(
        1.0, "D2-A-BBM", {
            "a": ("B", "D1"), "b": ("D", "D1"),
            "retarget_a": 2.0, "retarget_b": 2.0, "acquisition": 0.0,
        }, physical, OperationalPolicy("BOUNDED_OUTAGE", 2.0), 4.0, True)
    return _engine(nodes, fixed, commodities, {"f0": 8*GBIT}, 12.0,
                   executor, (action,))


def fixture_b_genuine_mbb():
    nodes = ("A", "B", "C", "D")
    fixed = (("A", "B"), ("C", "D"))
    commodities = (Commodity("f0", "A", "D"),)
    executor = TerminalExecutor(nodes)
    old = (("B", "D1"), ("C", "D1"))
    _activate(executor, *old)
    physical = TerminalPairPhysicalFeasibility(_catalog(
        nodes, [_window("A", "D2", "D", "D2")]))
    action = ScriptedProposal(
        1.0, "D2-B-MBB", {
            "a": ("A", "D2"), "b": ("D", "D2"),
            "retarget_a": 1.0, "retarget_b": 1.0, "acquisition": 1.0,
            "release_after": (old,),
        }, physical, OperationalPolicy("STRICT_CONNECTED"), 4.0, True)
    return _engine(nodes, fixed, commodities, {"f0": 8*GBIT}, 12.0,
                   executor, (action,))


def fixture_c_false_mbb_rejection():
    nodes = ("A", "B", "C", "D")
    fixed = (("A", "B"), ("C", "D"))
    commodities = (Commodity("f0", "A", "D"),)
    executor = TerminalExecutor(nodes)
    old = (("B", "D1"), ("C", "D1"))
    _activate(executor, *old)
    physical = TerminalPairPhysicalFeasibility(_catalog(nodes, ()))
    action = ScriptedProposal(
        1.0, "D2-C-FALSE-MBB", {
            "a": ("A", "D2"), "b": ("D", "D2"),
            "retarget_a": 1.0, "retarget_b": 1.0, "acquisition": 1.0,
            "release_after": (old,),
        }, physical, OperationalPolicy("STRICT_CONNECTED"), 4.0, False)
    return _engine(nodes, fixed, commodities, {"f0": 8*GBIT}, 4.0,
                   executor, (action,))


def fixture_d_draining_split():
    nodes = ("A", "B", "C", "D")
    fixed = (("A", "B"), ("C", "D"))
    commodities = (Commodity("f0", "A", "D"),)
    executor = TerminalExecutor(nodes)
    _activate(executor, ("B", "D1"), ("C", "D1"))
    executor.start_tx(("B", "D1"), 1.5)
    physical = TerminalPairPhysicalFeasibility(_catalog(
        nodes, [_window("B", "D1", "D", "D1")]))
    action = ScriptedProposal(
        1.0, "D2-D-DRAINING", {
            "a": ("B", "D1"), "b": ("D", "D1"),
            "retarget_a": 0.5, "retarget_b": 0.5, "acquisition": 0.5,
        }, physical, OperationalPolicy("BOUNDED_OUTAGE", 2.0), 4.0, True)
    return _engine(nodes, fixed, commodities, {"f0": 8*GBIT}, 5.0,
                   executor, (action,))


def fixture_e_partition_with_unaffected_flow():
    nodes = ("A", "B", "C", "D", "E", "F")
    fixed = (("A", "B"), ("C", "D"), ("D", "E"), ("E", "F"))
    commodities = (Commodity("affected", "A", "D"),
                   Commodity("unaffected", "E", "F"))
    executor = TerminalExecutor(nodes)
    _activate(executor, ("B", "D1"), ("C", "D1"))
    physical = TerminalPairPhysicalFeasibility(_catalog(
        nodes, [_window("B", "D1", "D", "D1")]))
    action = ScriptedProposal(
        1.0, "D2-E-PARTITION", {
            "a": ("B", "D1"), "b": ("D", "D1"),
            "retarget_a": 2.0, "retarget_b": 2.0, "acquisition": 0.0,
        }, physical, OperationalPolicy("BOUNDED_OUTAGE", 2.0), 4.0, True)
    return _engine(nodes, fixed, commodities,
                   {"affected": 8*GBIT, "unaffected": 4*GBIT}, 6.0,
                   executor, (action,))


def fixture_f_alternate_path():
    nodes = ("A", "B", "C", "D", "E")
    fixed = (("A", "B"), ("B", "D"), ("C", "D"), ("D", "E"))
    commodities = (Commodity("target", "A", "D"),
                   Commodity("third_party", "B", "D"))
    executor = TerminalExecutor(nodes)
    _activate(executor, ("A", "D1"), ("C", "D1"))
    physical = TerminalPairPhysicalFeasibility(_catalog(
        nodes, [_window("A", "D1", "E", "D1")]))
    action = ScriptedProposal(
        1.0, "D2-F-ALT", {
            "a": ("A", "D1"), "b": ("E", "D1"),
            "retarget_a": 1.0, "retarget_b": 1.0, "acquisition": 0.0,
        }, physical, OperationalPolicy("STRICT_CONNECTED"), 3.0, True)
    overrides = {}
    for edge, value in {
        ("A", "C"): 0.05, ("C", "D"): 0.05,
        ("A", "B"): 0.2, ("B", "D"): 0.2,
        ("A", "E"): 0.05, ("E", "D"): 0.05,
    }.items():
        overrides[edge] = overrides[edge[::-1]] = value
    return _engine(nodes, fixed, commodities,
                   {"target": 4*GBIT, "third_party": 4*GBIT}, 4.0,
                   executor, (action,), ConstantDelay(0.2, overrides))


def fixture_g_natural_expiry():
    nodes = ("A", "B", "C", "D")
    fixed = (("A", "B"), ("B", "D"), ("C", "D"))
    commodities = (Commodity("f0", "A", "D"),)
    executor = TerminalExecutor(nodes)
    _activate(executor, ("A", "D1"), ("C", "D1"), end_s=2.0)
    overrides = {}
    for edge, value in {
        ("A", "C"): 0.05, ("C", "D"): 0.05,
        ("A", "B"): 0.2, ("B", "D"): 0.2,
    }.items():
        overrides[edge] = overrides[edge[::-1]] = value
    return _engine(nodes, fixed, commodities, {"f0": 4*GBIT}, 4.0,
                   executor, (), ConstantDelay(0.2, overrides))


def fixture_h_clone_base():
    nodes = ("A", "B", "C", "D")
    fixed = (("A", "B"), ("C", "D"))
    commodities = (Commodity("f0", "A", "D"),)
    executor = TerminalExecutor(nodes)
    _activate(executor, ("B", "D1"), ("C", "D1"))
    return _engine(nodes, fixed, commodities, {"f0": 8*GBIT}, 6.0,
                   executor, ())


def fixture_h_switch_action(time_s=1.0):
    nodes = ("A", "B", "C", "D")
    physical = TerminalPairPhysicalFeasibility(_catalog(
        nodes, [_window("B", "D1", "D", "D1")]))
    return ScriptedProposal(
        time_s, "D2-H-SWITCH", {
            "a": ("B", "D1"), "b": ("D", "D1"),
            "retarget_a": 1.0, "retarget_b": 1.0, "acquisition": 0.0,
        }, physical, OperationalPolicy("BOUNDED_OUTAGE", 1.0), time_s+2.0, True)


SMALL_FIXTURE_BUILDERS = {
    "D2-A": fixture_a_bbm_forced_outage,
    "D2-B": fixture_b_genuine_mbb,
    "D2-C": fixture_c_false_mbb_rejection,
    "D2-D": fixture_d_draining_split,
    "D2-E": fixture_e_partition_with_unaffected_flow,
    "D2-F": fixture_f_alternate_path,
    "D2-G": fixture_g_natural_expiry,
}


def load_160_pilot(case_id):
    """Build one deterministic, traffic-agnostic 160-satellite D2 pilot."""
    if case_id not in ("bridge_temporary_partition", "connected_mbb_reroute"):
        raise ValueError("UNKNOWN_160_PILOT_CASE")
    contract = read_json(PROJECT/"configs/gate_d0_traffic_contract.json")
    reference = read_json(PROJECT/contract["reference_topology"])
    fixed = tuple(tuple(edge) for edge in reference["fixed_edges"])
    nodes = tuple(sorted({node for edge in fixed for node in edge}))
    executor = TerminalExecutor(nodes)
    for binding in reference["bindings"]:
        _activate(executor, binding["a"], binding["b"], binding["end_s"])

    interval_path = PROJECT/"outputs/gate_c_simplified_20260922T064019_313843Z/terminal_pair_intervals.jsonl"
    records = [json.loads(line) for line in interval_path.read_text(encoding="utf-8").splitlines()]
    planes = {node: int(node.split("_")[0][1:]) for node in nodes}
    catalog = TerminalPairCatalog.from_records(records, planes)
    physical = TerminalPairPhysicalFeasibility(catalog)
    old_middle = (("X1_11", "D1"), ("X2_11", "D2"))
    if case_id == "bridge_temporary_partition":
        proposal = {
            "a": ("X1_11", "D1"), "b": ("X2_12", "D2"),
            "retarget_a": 1.0, "retarget_b": 1.0, "acquisition": 1.0,
        }
        policy = OperationalPolicy("BOUNDED_OUTAGE", 2.0)
        action_id = "P160-BRIDGE-BBM"
    else:
        proposal = {
            "a": ("X1_1", "D2"), "b": ("X2_1", "D1"),
            "retarget_a": 1.0, "retarget_b": 1.0, "acquisition": 1.0,
            "release_after": (old_middle,),
        }
        policy = OperationalPolicy("STRICT_CONNECTED")
        action_id = "P160-CONNECTED-MBB"
    action = ScriptedProposal(1.0, action_id, proposal, physical, policy, 4.0, True)

    od_doc = read_json(PROJECT/"configs/gate_d0_od_manifest_16.json")
    commodities = tuple(Commodity.from_dict(row) for row in od_doc["commodities"])
    current = read_json(PROJECT/"configs/current.json")
    d1_evidence = PROJECT/current["gate_d1"]["evidence"]
    trace = PiecewiseConstantTrafficTrace.from_dict(
        read_json(d1_evidence/"pilot_traffic_trace.json"))
    model = Sgp4Model.load(PROJECT/"data/raw/sgp4_x720")
    delay = Sgp4EdgeDelayProvider(model, nodes)
    engine = TransitionAwareNetworkServiceEngine(
        nodes, fixed, contract["link_capacity_bit_s_per_direction"],
        commodities, trace, delay, executor, (action,),
        conservation_abs_tolerance_bits=contract["conservation_abs_tolerance_bits"],
        conservation_relative_tolerance=contract["conservation_relative_tolerance"],
        state_tolerance_bits=contract["state_tolerance_bits"],
    )
    return engine, contract["drain_limit_s"]
