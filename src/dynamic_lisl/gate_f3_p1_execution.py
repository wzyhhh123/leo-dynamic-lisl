"""Manifest-driven Gate F3 P1 execution adapter.

This module is deliberately a thin orchestration/reporting layer over the
frozen Gate B--F2 scientific components.  It does not define a controller,
candidate score, router, traffic policy, or service rule.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import time

from .baseline_controllers import StaticHoldController
from .candidate_proposer import (FrozenTerminalPairProposer,
                                 RegimeSafetyAdapter, canonical_sha256)
from .common import PROJECT, read_json
from .controller_runner import controller_visible_state
from .gate_e2_experiments import (E2Sgp4EdgeDelayProvider,
                                  E2TransitionEngine, GateE2Assets)
from .f3_drain_continuation import (
    F3_BOUNDARY_REACHED, F3_CENSORED, F3_COMPLETE,
    F3DrainContinuationAdapter,
)
from .outage_metrics import derive_separated_outage_metrics
from .production_candidate_source import (DrainDecisionPolicy,
                                          ProductionCandidateSource)
from .rollout_controller import RootActionRolloutMPCController
from .scientific_controllers import (IgnoreSetupDynamicController,
                                     SetupAwareGreedyController)
from .terminal_executor import Connect, TerminalExecutor
from .traffic_trace import PiecewiseConstantTrafficTrace, TrafficSegment
from .transition_service_orchestrator import ScriptedProposal


F3_SHA = "118d3a61175b08b6ba53f4d92504b52ab879659682799d26c1965baf7bb600a6"
EXECUTION_SHA = "0222d30e69ec9f565e1d55d5e74391934d63d7357cc7f1d652532f6a30ac945a"
OVERLAY_SHA = "ba527d3bc2c4ebca742ec21b8c390d512931d56d9c9ba68ed4eb22a7f47a7f39"


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def canonical_hash(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _totals(engine):
    return {
        "N_total_bits": math.fsum(engine.arrived.values())
                        - math.fsum(engine.delivered.values()),
        "Q_total_bits": engine.queues.total(),
        "I_total_bits": engine.in_flight.total(),
        "delivered_bits_cumulative": math.fsum(engine.delivered.values()),
    }


class ObservationalE2Engine(E2TransitionEngine):
    """Frozen E2 dynamics plus nonintrusive one-second interpolation samples."""

    def __init__(self, *args, **kwargs):
        self.reporting_enabled = True
        self.reporting_samples = []
        super().__init__(*args, **kwargs)
        self.reporting_samples.append({"time_s": 0.0, **_totals(self)})

    def clone(self):
        from .rollout_clone import clone_rollout_engine
        clone = clone_rollout_engine(self)
        clone.reporting_enabled = False
        clone.reporting_samples = []
        return clone

    def clone_legacy_reference(self):
        """Test-only reference; never used by the production B4 evaluator."""
        clone = deepcopy(self)
        clone.reporting_enabled = False
        clone.reporting_samples = []
        return clone

    def _integrate(self, next_time, external, inputs, queue_derivative,
                   delivery_rates):
        start = float(self.now)
        before = _totals(self)
        super()._integrate(next_time, external, inputs, queue_derivative,
                           delivery_rates)
        if not self.reporting_enabled:
            return
        end = float(self.now)
        after = _totals(self)
        first = int(math.floor(start+1e-12))+1
        last = int(math.floor(end+1e-12))
        for second in range(first, last+1):
            sample_time = float(second)
            if sample_time > end+1e-12:
                continue
            fraction = (sample_time-start)/(end-start)
            row = {"time_s": sample_time}
            for key in before:
                row[key] = before[key]+fraction*(after[key]-before[key])
            self.reporting_samples.append(row)


def f3_trace(assets, rho):
    profile = read_json(PROJECT/"configs/gate_f3_traffic_hotspot_migration_v1.json")
    ids = tuple(row["commodity_id"] for row in assets.commodity_rows)
    segments = []
    for row in profile["segments"]:
        rates = {key: float(rho)*float(profile["alpha_star_bit_s"])
                      *float(row["g"][key]) for key in ids}
        segments.append(TrafficSegment(float(row["start_s"]),
                                       float(row["end_s"]), rates,
                                       str(row["label"])))
    return PiecewiseConstantTrafficTrace(ids, segments)


def f3_trace_identity(rho):
    contract = read_json(PROJECT/"configs/gate_f3_experiment_human_freeze_v1.json")
    profile = read_json(PROJECT/"configs/gate_f3_traffic_hotspot_migration_v1.json")
    od = read_json(PROJECT/"configs/gate_d0_od_manifest_16.json")
    ids = [row["commodity_id"] for row in od["commodities"]]
    document = {
        "schema": "gate_f3_exogenous_trace_identity_v1",
        "od_manifest_sha256": contract["od_manifest"]["sha256"],
        "alpha_star_bit_s": contract["normalization"]["alpha_star_bit_s"],
        "profile_id": profile["profile_id"],
        "profile_canonical_sha256": profile["canonical_sha256"],
        "rho": float(rho),
        "segments": [{
            "start_s": row["start_s"], "end_s": row["end_s"],
            "rates_bit_s": {
                key: float(rho)*contract["normalization"]["alpha_star_bit_s"]
                     *row["g"][key] for key in ids},
        } for row in profile["segments"]],
        "after_240_s": "ALL_RATES_ZERO",
    }
    return canonical_hash(document), document


def moderate_engine(assets, rho):
    topology = read_json(PROJECT/"configs/z_moderate_v1.json")
    executor = TerminalExecutor(assets.nodes)
    for binding in topology["bindings"]:
        executor.submit((Connect(tuple(binding["a"]), tuple(binding["b"]),
                                 float(binding["end_s"]), 0.0, 0.0, 0.0),))
    engine = ObservationalE2Engine(
        assets.nodes, assets.fixed,
        assets.contract["link_capacity_bit_s_per_direction"],
        assets.commodities, f3_trace(assets, rho),
        E2Sgp4EdgeDelayProvider(assets.model, assets.nodes), executor, (),
        assets.router("shortest_propagation"),
        conservation_abs_tolerance_bits=
            assets.contract["conservation_abs_tolerance_bits"],
        conservation_relative_tolerance=
            assets.contract["conservation_relative_tolerance"],
        state_tolerance_bits=assets.contract["state_tolerance_bits"])
    # Same natural-geometry convention as Gate E2: refresh at the decision
    # origin, then recompute on real topology events.
    engine.geometry_refresh_s = 1e9
    engine.next_refresh = 0.0
    return engine


def _public_proposal_set(proposal_set):
    return {key: value for key, value in proposal_set.items()
            if key != "candidate_specs"}


def _empty_proposal_set(epoch):
    document = {
        "schema": "gate_f1_proposal_set_v1", "time_s": float(epoch),
        "regime": "Z_MODERATE", "candidate_top_k": 16,
        "quota": {"MBB_STRUCTURALLY_FEASIBLE": 8, "BBM_REQUIRED": 8},
        "proposals": [],
    }
    return {**document, "proposal_set_sha256": canonical_sha256(document),
            "pruned": [], "candidate_specs": {}}


def _binding_json(binding):
    return [list(endpoint) for endpoint in binding]


def _snapshot_result(engine, runtime_s):
    """Read the current frozen-engine state without advancing simulation time."""
    total_arrived = math.fsum(engine.arrived.values())
    raw_delivered = math.fsum(engine.delivered.values())
    excess = max(0.0, raw_delivered-total_arrived)
    total_delivered = min(total_arrived, raw_delivered)
    residual = engine.queues.total()+engine.in_flight.total()
    drained = residual <= max(engine.state_tol, engine.abs_tol)
    evaluation_time = engine.now
    utilization = {
        edge[0]+"->"+edge[1]: amount/(engine.capacity_bit_s*evaluation_time)
        for edge, amount in sorted(engine.transmitted.items())
        if amount > 0.0 and evaluation_time > 0.0}
    clearances = [x["clearance_time_s"] for x in engine.transition_episodes
                  if x["clearance_time_s"] is not None]
    metrics = {
        "schema": "gate_d2_transition_service_metrics_v1",
        "evaluation_end_s": evaluation_time,
        "arrival_horizon_s": engine.trace.arrival_horizon_s,
        "censored": not drained,
        "mean_bit_delay_s": (math.fsum(engine.objective_by_commodity.values())
                             /total_arrived if drained and total_arrived else None),
        "J_bit_s": math.fsum(engine.objective_by_commodity.values()),
        "objective_J_bit_s": math.fsum(engine.objective_by_commodity.values()),
        "arrived_bits": total_arrived, "delivered_bits": total_delivered,
        "numerical_raw_delivered_bits": raw_delivered,
        "numerical_delivery_excess_bits": excess,
        "delivery_ratio": total_delivered/total_arrived if total_arrived else 1.0,
        "residual_backlog_bits": residual,
        "queued_bits_at_end": engine.queues.total(),
        "in_flight_bits_at_end": engine.in_flight.total(),
        "mean_queue_bits": engine.queue_area/evaluation_time if evaluation_time else 0.0,
        "max_queue_bits": engine.max_queue,
        "link_utilization": utilization,
        "traffic_weighted_hop_count": (
            math.fsum(engine.transmitted.values())/total_delivered
            if total_delivered > 0.0 else None),
        "route_change_count": sum(
            row["node"] == engine.by_id[row["commodity_id"]].source
            for row in engine.route_changes),
        "node_commodity_route_change_count": len(engine.route_changes),
        "active_dynamic_link_count": sum(
            not link.draining for link in engine.executor.links.values()),
        "switch_count": engine.switch_count, "BBM_count": engine.BBM_count,
        "MBB_count": engine.MBB_count,
        "no_route_duration_s": engine.outage_duration_s,
        "no_route_duration_by_commodity_s": dict(
            sorted(engine.no_route_duration_by_commodity.items())),
        "outage_duration_s": engine.outage_duration_s,
        "partition_duration_s": engine.partition_duration_s,
        "partition_node_time_s": engine.partition_node_time_s,
        "backlog_added_during_transition_bits":
            engine.backlog_added_during_transition_bits,
        "peak_transition_backlog_bits": engine.peak_transition_backlog_bits,
        "backlog_clearance_time_s": max(clearances) if clearances else None,
        "max_abs_conservation_error_bits": engine.max_abs_conservation,
        "max_relative_conservation_error": engine.max_relative_conservation,
        "conservation_samples": engine.conservation_samples,
        "max_capacity_violation_bit_s": engine.max_capacity_violation,
        "negative_queue_count": sum(v < 0.0 for v in engine.queues.bits.values()),
        "trace_sha256": engine.trace.sha256(), "runtime": runtime_s,
    }
    return {
        "metrics": metrics, "timeline": engine.timeline,
        "queues": engine.queues.snapshot(), "in_flight": engine.in_flight.snapshot(),
        "arrived_by_commodity": dict(sorted(engine.arrived.items())),
        "delivered_by_commodity": dict(sorted(engine.delivered.items())),
        "transmitted_by_edge_commodity": {
            edge[0]+"->"+edge[1]+"|"+key: value
            for (edge, key), value in sorted(engine.transmitted_by_commodity.items())},
        "routes": {node+"|"+key: (list(route) if route is not None else None)
                   for (node, key), route in sorted(engine.routes.items())},
        "route_changes": engine.route_changes,
        "route_state_events": engine.route_state_events,
        "action_results": engine.action_results,
        "terminal_event_sequence": engine.terminal_event_sequence,
        "graph_event_sequence": engine.graph_event_sequence,
        "transition_episodes": engine.transition_episodes,
        "final_state": engine.canonical_state(),
    }


def _decision_record(controller, state, proposal_set, action, elapsed_s):
    proposals = {row["proposal_id"]: row for row in proposal_set["proposals"]}
    if action.kind == "REPLACE" and action.proposal_id not in proposals:
        raise AssertionError("CONTROLLER_SELECTED_OUTSIDE_COMMON_PROPOSAL_SET")
    record = {
        "controller_id": controller.controller_id,
        "decision_time_s": float(state["time_s"]),
        "canonical_state_sha256": state["current_state_sha256"],
        "proposal_set_sha256": proposal_set["proposal_set_sha256"],
        "selected_action": action.kind,
        "selected_proposal_id": action.proposal_id,
        "decision_metadata": dict(action.decision_metadata),
        "controller_decision_runtime_s": float(elapsed_s),
        "old_physical_binding": None, "new_terminal_pair": None,
        "release_after": [], "execution_status": "ACCEPTED_HOLD",
        "accepted": action.kind == "HOLD", "rejection_reason": None,
        "actual_gate_b_transition_type": None,
    }
    return record


def _source_audit(epoch, state, source_report, proposal_set, action):
    if source_report is None:
        uncapped = {"BBM_RAW": 0, "MBB_RAW": 0}
        selected = {"BBM_RAW": 0, "MBB_RAW": 0}
        source_sha = "B0_CANDIDATE_BUDGET_NOT_USED_BY_DESIGN"
    else:
        uncapped = source_report["uncapped_counts"]
        selected = source_report["selected_counts"]
        source_sha = source_report["source_sha256"]
    proposals = proposal_set["proposals"]
    return {
        "time_s": float(epoch),
        "canonical_state_sha256": state["current_state_sha256"],
        "raw_BBM_count_before_cap": int(uncapped.get("BBM_RAW", 0)),
        "raw_MBB_count_before_cap": int(uncapped.get("MBB_RAW", 0)),
        "raw_BBM_count_after_cap": int(selected.get("BBM_RAW", 0)),
        "raw_MBB_count_after_cap": int(selected.get("MBB_RAW", 0)),
        "raw_source_sha256": source_sha,
        "proposal_set_sha256": proposal_set["proposal_set_sha256"],
        "final_proposal_count": len(proposals),
        "final_BBM_count": sum(x["stratum"] == "BBM_REQUIRED" for x in proposals),
        "final_MBB_count": sum(
            x["stratum"] == "MBB_STRUCTURALLY_FEASIBLE" for x in proposals),
        "selected_action": action.kind,
        "selected_proposal_id": action.proposal_id,
    }


def _decorate_timeseries(engine, actions):
    fixed_count = len(engine.fixed_edges)
    graph_events = sorted(engine.graph_event_sequence,
                          key=lambda row: float(row["time_s"]))
    initial_dynamic = 4
    episodes = list(engine.transition_episodes)
    if engine._transition_open is not None:
        episodes.append({**engine._transition_open, "end_s": engine.now})
    terminal_by_time = defaultdict(list)
    for row in engine.terminal_event_sequence:
        terminal_by_time[round(float(row["time"]), 9)].append(row["event"])
    action_by_time = defaultdict(list)
    for row in actions:
        action_by_time[round(float(row["decision_time_s"]), 9)].append(
            row["selected_action"])
    result = []
    index = 0
    dynamic_count = initial_dynamic
    for sample in sorted(engine.reporting_samples, key=lambda row: row["time_s"]):
        t = float(sample["time_s"])
        while index < len(graph_events) and float(graph_events[index]["time_s"]) <= t+1e-12:
            dynamic_count = max(0, len(graph_events[index]["active_edges"])-fixed_count)
            index += 1
        result.append({
            **sample,
            "active_dynamic_link_count": dynamic_count,
            "transition_active": any(
                float(x["start_s"]) <= t < float(x["end_s"])-1e-12
                for x in episodes if x.get("end_s") is not None),
            "controller_markers": action_by_time.get(round(t, 9), []),
            "physical_transition_markers": terminal_by_time.get(round(t, 9), []),
        })
    return result


class P1RunExecutor:
    def __init__(self, assets, row, progress_recorder=None,
                 *, b4_parallel_workers=0, checkpoint_sink=None):
        self.assets = assets
        self.row = row
        self.engine = moderate_engine(assets, row["rho"])
        self.source = ProductionCandidateSource.from_project(
            assets.catalog, PROJECT)
        self.proposer = FrozenTerminalPairProposer()
        controller_id = row["controller"]
        if controller_id == "B0":
            self.controller = StaticHoldController()
            self.candidate_source = None
        elif controller_id == "B1":
            self.controller = IgnoreSetupDynamicController(self.engine)
            self.candidate_source = self.source
        elif controller_id == "B3":
            self.controller = SetupAwareGreedyController(self.engine)
            self.candidate_source = self.source
        elif controller_id == "B4":
            self.controller = RootActionRolloutMPCController(
                self.engine, assets.physical, assets.fixed, "Z_MODERATE",
                parallel_workers=b4_parallel_workers)
            self.candidate_source = self.controller.candidate_source(self.source)
        else:
            raise ValueError("P1_UNREGISTERED_CONTROLLER")
        self.policy = DrainDecisionPolicy()
        self.drain_adapter = F3DrainContinuationAdapter()
        self.drain_continuation_audit = []
        self.actions = []
        self.audits = []
        self.decision_runtime_total = 0.0
        self.b4_branch_count_total = 0
        self.b4_valid_branch_count_total = 0
        self.b4_invalid_branch_count_total = 0
        self.progress_recorder = progress_recorder
        self.epoch_runtime_records = []
        self._pending_network_advance_wall_s = 0.0
        self._checkpoint_sink = checkpoint_sink

    def _checkpoint(self, name, epoch):
        sink = getattr(self, "_checkpoint_sink", None)
        if sink is not None:
            sink({
                "checkpoint": name,
                "decision_epoch_s": float(epoch),
                "time_s": float(self.engine.now),
                "canonical_state_sha256": self.engine.canonical_state_sha256(),
            })

    def _decision(self, epoch, index):
        self._checkpoint("H_pre_call", epoch)
        epoch_wall_start = time.perf_counter()
        advance_start = time.perf_counter()
        self.engine.advance_to(epoch)
        network_advance_wall_s = (
            self._pending_network_advance_wall_s
            + time.perf_counter()-advance_start)
        self._pending_network_advance_wall_s = 0.0
        if abs(self.engine.now-epoch) > 1e-12:
            raise AssertionError("DECISION_EPOCH_NOT_EXACT")
        if self.progress_recorder is not None:
            self.progress_recorder.epoch_start(
                sim_time_s=self.engine.now, decision_epoch_index=index)
        if abs(epoch-240.0) <= 1e-12:
            self.policy.assert_arrival_cutoff_state(
                epoch, self.engine.trace.rate_at(epoch))
        state = controller_visible_state(self.engine)
        self._checkpoint("H_decision_root", epoch)
        decision_start = time.perf_counter()
        candidate_source_wall_s = 0.0
        proposer_wall_s = 0.0
        if self.candidate_source is None:
            proposal_set = _empty_proposal_set(epoch)
            source_report = None
        else:
            source_start = time.perf_counter()
            specs = tuple(self.candidate_source(state, {
                "epoch_index": index, "regime": "Z_MODERATE",
                "terminal_executor": self.engine.executor,
            }))
            candidate_source_wall_s = time.perf_counter()-source_start
            proposer_start = time.perf_counter()
            proposal_set = self.proposer.propose(
                self.engine.executor, specs, self.assets.physical,
                self.assets.fixed, "Z_MODERATE")
            proposer_wall_s = time.perf_counter()-proposer_start
            source_report = deepcopy(self.source.last_report)
        observe_start = time.perf_counter()
        action = self.controller.observe(
            state, _public_proposal_set(proposal_set), {
                "regime": "Z_MODERATE", "epoch_index": index,
                "information_class": self.controller.information_class,
            })
        controller_observe_wall_s = time.perf_counter()-observe_start
        self._checkpoint("H_post_observe", epoch)
        elapsed = time.perf_counter()-decision_start
        self.decision_runtime_total += elapsed
        record = _decision_record(self.controller, state, proposal_set,
                                  action, elapsed)
        if self.row["controller"] == "B4" and self.controller.last_decision:
            decision = self.controller.last_decision
            self.b4_branch_count_total += int(decision["branch_count"])
            self.b4_valid_branch_count_total += int(decision["valid_branch_count"])
            self.b4_invalid_branch_count_total += int(decision["invalid_branch_count"])
        gate_b_execution_wall_s = 0.0
        if action.kind == "REPLACE":
            spec = proposal_set["candidate_specs"][action.proposal_id]
            record["old_physical_binding"] = _binding_json(spec.old_binding)
            record["new_terminal_pair"] = [list(spec.proposal["a"]),
                                           list(spec.proposal["b"])]
            record["release_after"] = [
                _binding_json(binding)
                for binding in spec.proposal.get("release_after", ())]
            selected = next(x for x in proposal_set["proposals"]
                            if x["proposal_id"] == action.proposal_id)
            safety = RegimeSafetyAdapter("Z_MODERATE")
            scheduled = ScriptedProposal(
                epoch, f"F3P1-{self.row['run_id']}-{index:04d}-{action.proposal_id}",
                spec.proposal, self.assets.physical, safety.policy,
                max(epoch+1e-7, float(selected["ready_time_s"])+1e-7), None)
            before = len(self.engine.action_results)
            gate_b_start = time.perf_counter()
            self.engine.schedule_action(scheduled)
            self.engine.settle_current_time()
            gate_b_execution_wall_s = time.perf_counter()-gate_b_start
            if len(self.engine.action_results) != before+1:
                raise AssertionError("P1_CONTROLLER_ACTION_NOT_EXECUTED")
            outcome = self.engine.action_results[-1]
            record["accepted"] = bool(outcome["accepted"])
            record["actual_gate_b_transition_type"] = outcome.get("transition_mode")
            if not outcome["accepted"]:
                record["execution_status"] = "REJECTED"
                record["rejection_reason"] = (outcome.get("policy_reason")
                                               or outcome.get("physical_reason"))
                raise AssertionError("P1_LEGAL_PROPOSAL_REJECTED_AT_EXECUTION:"
                                     +str(record["rejection_reason"]))
            record["execution_status"] = "ACCEPTED_REPLACE"
        record["action_canonical_sha256"] = canonical_hash(record)
        self.controller.on_action_result(record)
        self.actions.append(record)
        audit = _source_audit(epoch, state, source_report, proposal_set, action)
        self.audits.append(audit)
        epoch_total_wall_s = time.perf_counter()-epoch_wall_start
        timing = {
            "sim_time_s": float(self.engine.now),
            "decision_epoch_index": int(index),
            "candidate_source_wall_s": candidate_source_wall_s,
            "proposer_wall_s": proposer_wall_s,
            "controller_observe_wall_s": controller_observe_wall_s,
            "network_advance_wall_s": network_advance_wall_s,
            "gate_b_execution_wall_s": gate_b_execution_wall_s,
            "epoch_total_wall_s": epoch_total_wall_s,
            "final_proposal_count": int(audit["final_proposal_count"]),
        }
        self.epoch_runtime_records.append(timing)
        self._checkpoint("H_post_decision", epoch)
        if self.progress_recorder is not None:
            queue_bits = float(self.engine.queues.total())
            inflight_bits = float(self.engine.in_flight.total())
            self.progress_recorder.epoch_end(
                sim_time_s=self.engine.now,
                decision_epoch_index=index,
                total_unfinished_bits=queue_bits+inflight_bits,
                total_queue_bits=queue_bits,
                total_inflight_bits=inflight_bits,
                raw_bbm_count=audit["raw_BBM_count_after_cap"],
                raw_mbb_count=audit["raw_MBB_count_after_cap"],
                final_proposal_count=audit["final_proposal_count"],
                selected_action_kind=action.kind,
                selected_proposal_id=action.proposal_id,
                candidate_source_wall_s=candidate_source_wall_s,
                proposer_wall_s=proposer_wall_s,
                controller_observe_wall_s=controller_observe_wall_s,
                network_advance_wall_s=network_advance_wall_s,
                gate_b_execution_wall_s=gate_b_execution_wall_s,
                epoch_total_wall_s=epoch_total_wall_s,
            )

    def _continue_drain_to(self, boundary_s):
        outcome = self.drain_adapter.advance_to_boundary(
            self.engine, float(boundary_s))
        self.drain_continuation_audit.append({
            "boundary_s": float(boundary_s),
            "status": outcome.status,
            "continuation_iterations": outcome.continuation_iterations,
            "start_time_s": outcome.start_time_s,
            "final_time_s": outcome.final_time_s,
            "final_unfinished_bits": outcome.final_unfinished_bits,
            "d2_early_returns_ignored": outcome.d2_early_returns_ignored,
        })
        return outcome

    def close(self):
        if self.row["controller"] == "B4":
            self.controller.close()

    def run(self):
        try:
            return self._run_impl()
        finally:
            self.close()

    def _run_impl(self):
        wall_start = time.perf_counter()
        final = None
        epochs = self.policy.possible_epochs()
        for index, epoch in enumerate(epochs):
            network_advance_start = time.perf_counter()
            if self.engine.now < epoch-1e-12:
                if epoch <= self.policy.arrival_horizon_s+1e-12:
                    self.engine.advance_to(epoch)
                else:
                    outcome = self._continue_drain_to(epoch)
                    if outcome.status in (F3_COMPLETE, F3_CENSORED):
                        final = (outcome.result if outcome.result is not None
                                 else _snapshot_result(
                                     self.engine,
                                     time.perf_counter()-wall_start))
                        break
                    if outcome.status != F3_BOUNDARY_REACHED:
                        raise AssertionError(
                            "UNKNOWN_F3_DRAIN_CONTINUATION_STATUS")
            self._pending_network_advance_wall_s = (
                time.perf_counter()-network_advance_start)
            self.engine.settle_current_time()
            residual = self.engine.queues.total()+self.engine.in_flight.total()
            if not self.policy.decision_due(epoch, residual):
                if epoch >= self.policy.arrival_horizon_s-1e-12:
                    final = _snapshot_result(
                        self.engine, time.perf_counter()-wall_start)
                    break
                continue
            self._decision(epoch, index)
        if final is None:
            if self.engine.now < self.policy.drain_limit_s-1e-12:
                outcome = self._continue_drain_to(self.policy.drain_limit_s)
                if outcome.status not in (F3_COMPLETE, F3_CENSORED):
                    raise AssertionError(
                        "F3_DRAIN_LIMIT_REACHED_WITHOUT_FINAL_CLASSIFICATION")
                final = (outcome.result if outcome.result is not None
                         else _snapshot_result(
                             self.engine, time.perf_counter()-wall_start))
            else:
                final = _snapshot_result(
                    self.engine, time.perf_counter()-wall_start)
        runtime = time.perf_counter()-wall_start
        final["metrics"]["runtime"] = runtime
        return {
            "engine_result": final,
            "actions": self.actions,
            "candidate_audits": self.audits,
            "timeseries": _decorate_timeseries(self.engine, self.actions),
            "drain_continuation_audit": self.drain_continuation_audit,
            "epoch_runtime_records": self.epoch_runtime_records,
            "decision_runtime_total_s": self.decision_runtime_total,
            "decision_runtime_mean_s": (
                self.decision_runtime_total/len(self.actions)
                if self.actions else 0.0),
            "b4_branch_count_total": self.b4_branch_count_total,
            "b4_valid_branch_count_total": self.b4_valid_branch_count_total,
            "b4_invalid_branch_count_total": self.b4_invalid_branch_count_total,
        }


    def run_engineering_prefix(self, sim_end_s):
        try:
            return self._run_engineering_prefix_impl(sim_end_s)
        finally:
            self.close()

    def _run_engineering_prefix_impl(self, sim_end_s):
        """Profile-only prefix; forbidden for any registered P1 run id."""
        if not str(self.row["run_id"]).startswith("ENGINEERING_PROFILE_ONLY"):
            raise ValueError("ENGINEERING_PREFIX_REQUIRES_NONREGISTERED_RUN_ID")
        sim_end_s = float(sim_end_s)
        if sim_end_s < 0.0 or sim_end_s > self.policy.drain_limit_s:
            raise ValueError("INVALID_ENGINEERING_PROFILE_SIM_END")
        for index, epoch in enumerate(self.policy.possible_epochs()):
            if epoch > sim_end_s+1e-12:
                break
            advance_start = time.perf_counter()
            self.engine.advance_to(epoch)
            self._pending_network_advance_wall_s = time.perf_counter()-advance_start
            self.engine.settle_current_time()
            residual = self.engine.queues.total()+self.engine.in_flight.total()
            if self.policy.decision_due(epoch, residual):
                self._decision(epoch, index)
        if self.engine.now < sim_end_s-1e-12:
            self.engine.advance_to(sim_end_s)
        return {
            "schema": "gate_f3_b1_engineering_profile_prefix_v1",
            "run_id": self.row["run_id"],
            "sim_end_s": sim_end_s,
            "actual_sim_time_s": float(self.engine.now),
            "action_count": len(self.actions),
            "actions": self.actions,
            "candidate_audits": self.audits,
            "epoch_runtime_records": self.epoch_runtime_records,
            "canonical_state_sha256": self.engine.canonical_state_sha256(),
            "total_queue_bits": float(self.engine.queues.total()),
            "total_inflight_bits": float(self.engine.in_flight.total()),
        }


def summarize_run(row, run):
    result = run["engine_result"]
    metrics = result["metrics"]
    outage = derive_separated_outage_metrics(result)
    status = ("COMPLETE" if metrics["residual_backlog_bits"] <= 0.01
              else "CENSORED")
    final = {
        "schema": "gate_f3_p1_final_metrics_v1",
        "run_id": row["run_id"], "controller": row["controller"],
        "rho": row["rho"], "topology": row["topology_regime"],
        "router": row["router"], "traffic_profile": row["traffic_profile"],
        "traffic_trace_sha256": row["traffic_trace_sha256"],
        "engine_trace_sha256": metrics["trace_sha256"],
        "status": status,
        "completion_time_s": (metrics["evaluation_end_s"]
                              if status == "COMPLETE" else None),
        "final_time_s": metrics["evaluation_end_s"],
        "J_bit_s": metrics["J_bit_s"],
        "mean_bit_delay_s": (metrics["J_bit_s"]/metrics["arrived_bits"]
                             if status == "COMPLETE" and metrics["arrived_bits"] > 0.0
                             else None),
        "total_arrived_bits": metrics["arrived_bits"],
        "delivered_bits": metrics["delivered_bits"],
        "delivery_ratio": metrics["delivery_ratio"],
        "residual_backlog_bits": metrics["residual_backlog_bits"],
        "mean_queue_bits": metrics["mean_queue_bits"],
        "max_queue_bits": metrics["max_queue_bits"],
        "route_change_count": metrics["route_change_count"],
        "active_dynamic_link_count": metrics["active_dynamic_link_count"],
        "switch_count": metrics["switch_count"],
        "BBM_count": metrics["BBM_count"], "MBB_count": metrics["MBB_count"],
        **outage,
        "runtime_s": metrics["runtime"],
        "controller_decision_count": len(run["actions"]),
        "controller_decision_runtime_total_s": run["decision_runtime_total_s"],
        "controller_decision_runtime_mean_s": run["decision_runtime_mean_s"],
        "B4_branch_count_total": (run["b4_branch_count_total"]
                                  if row["controller"] == "B4"
                                  else "NOT_APPLICABLE"),
        "B4_valid_branch_count_total": (run["b4_valid_branch_count_total"]
                                        if row["controller"] == "B4"
                                        else "NOT_APPLICABLE"),
        "B4_invalid_branch_count_total": (run["b4_invalid_branch_count_total"]
                                          if row["controller"] == "B4"
                                          else "NOT_APPLICABLE"),
    }
    return final


def invariant_report(row, run, final_metrics):
    metrics = run["engine_result"]["metrics"]
    trace_hash, _ = f3_trace_identity(row["rho"])
    checks = {
        "manifest_traffic_trace_match": trace_hash == row["traffic_trace_sha256"],
        "work_conservation_pass": metrics["max_abs_conservation_error_bits"]
            <= (run["engine_result"]["metrics"]["arrived_bits"]*1e-12+1e-3),
        "nonnegative_queue_pass": metrics["negative_queue_count"] == 0,
        "capacity_pass": metrics["max_capacity_violation_bit_s"] <= 0.01,
        "drain_limit_respected": metrics["evaluation_end_s"] <= 600.0+1e-12,
        "no_decision_at_600": all(
            row_["decision_time_s"] < 600.0-1e-12 for row_ in run["actions"]),
        "candidate_cap_pass": all(
            x["raw_BBM_count_after_cap"] <= 32
            and x["raw_MBB_count_after_cap"] <= 32
            and x["final_proposal_count"] <= 16
            for x in run["candidate_audits"]),
        "status_semantics_pass": (
            (final_metrics["status"] == "COMPLETE"
             and final_metrics["residual_backlog_bits"] <= 0.01)
            or (final_metrics["status"] == "CENSORED"
                and abs(final_metrics["final_time_s"]-600.0) <= 1e-12
                and final_metrics["residual_backlog_bits"] > 0.01)),
    }
    return {
        "schema": "gate_f3_p1_invariant_report_v1", "checks": checks,
        "max_abs_conservation_error_bits": metrics["max_abs_conservation_error_bits"],
        "max_relative_conservation_error": metrics["max_relative_conservation_error"],
        "max_capacity_violation_bit_s": metrics["max_capacity_violation_bit_s"],
        "negative_queue_count": metrics["negative_queue_count"],
        "pass": all(checks.values()),
    }
