"""Gate F2 canonical B4 root-action rollout/MPC controller."""
from __future__ import annotations

import math
import pickle
from pathlib import Path

from .baseline_controllers import ControllerAction
from .candidate_proposer import canonical_sha256
from .forecast import CurrentRatePersistenceForecast
from .rollout_evaluator import ExactRootActionRolloutEvaluator
from .b4_branch_multiprocessing import BranchTask, ParallelB4BranchPool, encode_root


class BoundRolloutCandidateSource:
    """Bind concrete specs while preserving the runner's common proposer path."""

    def __init__(self, controller, source):
        self.controller = controller
        self.source = source

    def __call__(self, state, context):
        specs = tuple(self.source(state, context))
        self.controller.bind_candidate_specs(specs, float(state["time_s"]))
        return specs


class RootActionRolloutMPCController:
    controller_id = "B4_ROOT_ACTION_ROLLOUT_MPC"
    information_class = "SHORT_HORIZON_FORECAST"
    horizon_s = 10.0
    root_action_only = True
    multi_step_future_controller_actions = False
    requires_scientific_snapshot = False

    def __init__(self, engine, physical_layer, fixed_edges, regime,
                 *, reuse_decision_hashes=True, parallel_workers=0,
                 tle_folder=None):
        self.engine = engine
        self.evaluator = ExactRootActionRolloutEvaluator(
            engine, physical_layer, fixed_edges, regime)
        self._candidate_specs = {}
        self._bound_time_s = None
        self.last_decision = None
        self.reuse_decision_hashes = bool(reuse_decision_hashes)
        if parallel_workers not in (0, 8):
            raise ValueError("B4_PRODUCTION_PARALLEL_WORKERS_MUST_BE_8")
        self.parallel_workers = parallel_workers
        self._tle_folder = (Path(tle_folder) if tle_folder is not None else
                            Path(__file__).resolve().parents[2]/"data/raw/sgp4_x720")
        self._branch_pool = None
        self.last_parallel_branch_results = None
        self.last_parallel_branch_evidence = None
        self.last_parallel_worker_pids = None
        self.parallel_pool_start_count = 0
        self.parallel_pool_pids = ()

    def close(self):
        if self._branch_pool is not None:
            try:
                self._branch_pool.__exit__(None, None, None)
            finally:
                self._branch_pool = None

    def _evaluate_parallel_branches(self, forecast, forecast_hash, root_hash,
                                    records, order):
        if self._branch_pool is None:
            pool = ParallelB4BranchPool(self.parallel_workers, self._tle_folder)
            pool.__enter__()
            try:
                ready = pool.warm()
            except BaseException:
                pool.__exit__(None, None, None)
                raise
            self._branch_pool = pool
            self.parallel_pool_start_count += 1
            self.parallel_pool_pids = tuple(sorted(row["pid"] for row in ready))
        pool = self._branch_pool
        root = encode_root(self.engine, pool.token)
        physical = pickle.dumps(self.evaluator.physical_layer,
                                protocol=pickle.HIGHEST_PROTOCOL)
        entries = [(None, None)] + [
            (records[proposal_id], self._candidate_specs[proposal_id])
            for proposal_id in order]
        tasks = [BranchTask(index, root, physical,
                            tuple(self.evaluator.fixed_edges),
                            self.evaluator.regime, forecast, record, spec,
                            root_hash, forecast_hash)
                 for index, (record, spec) in enumerate(entries)]
        futures = [pool.submit(task) for task in tasks]
        received = []
        for index, future in enumerate(futures):
            payload, _, length = future.result()
            if len(payload) != length:
                raise AssertionError("B4_PRODUCTION_BRANCH_TRANSPORT_LENGTH_MISMATCH")
            item = pickle.loads(payload)
            if item["index"] != index:
                raise AssertionError("B4_PRODUCTION_BRANCH_INDEX_MISMATCH")
            received.append(item)
        expected_ids = [None] + order
        if [item["result"].proposal_id for item in received] != expected_ids:
            raise AssertionError("B4_PRODUCTION_BRANCH_ORDER_MISMATCH")
        self.last_parallel_branch_results = [item["result"] for item in received]
        self.last_parallel_branch_evidence = [item["evidence"] for item in received]
        self.last_parallel_worker_pids = [item["worker_pid"] for item in received]
        return received[0]["result"], {
            proposal_id: received[index+1]["result"]
            for index, proposal_id in enumerate(order)}

    def candidate_source(self, source):
        return BoundRolloutCandidateSource(self, source)

    def bind_candidate_specs(self, specs, time_s):
        specs = tuple(specs)
        if len({row.proposal_id for row in specs}) != len(specs):
            raise ValueError("DUPLICATE_PROPOSAL_ID")
        self._candidate_specs = {row.proposal_id: row for row in specs}
        self._bound_time_s = float(time_s)

    def _forecast(self, current_state):
        now = float(current_state["time_s"])
        if abs(now-self.engine.now) > 1e-12:
            raise AssertionError("B4_LIVE_ENGINE_TIME_MISMATCH")
        rates = self.engine.trace.rate_at(now)
        return CurrentRatePersistenceForecast(now, self.horizon_s, rates)

    def evaluate_root_actions(self, current_state, proposal_set, context,
                              evaluation_order=None):
        if len(proposal_set["proposals"]) > 16:
            raise AssertionError("B4_COMMON_PROPOSAL_BUDGET_EXCEEDED")
        now = float(current_state["time_s"])
        if self._bound_time_s is None and proposal_set["proposals"]:
            raise AssertionError("B4_CONCRETE_CANDIDATE_SPECS_NOT_BOUND")
        if self._bound_time_s is not None and abs(self._bound_time_s-now) > 1e-12:
            raise AssertionError("B4_CANDIDATE_BINDING_TIME_MISMATCH")
        canonical_ids = [row["proposal_id"] for row in proposal_set["proposals"]]
        if any(key not in self._candidate_specs for key in canonical_ids):
            raise AssertionError("B4_MISSING_CONCRETE_CANDIDATE_SPEC")
        records = {row["proposal_id"]: row for row in proposal_set["proposals"]}
        order = list(canonical_ids if evaluation_order is None else evaluation_order)
        if set(order) != set(canonical_ids) or len(order) != len(canonical_ids):
            raise ValueError("B4_EVALUATION_ORDER_MUST_BE_EXACT_PROPOSAL_PERMUTATION")

        live_hash_before = self.engine.canonical_state_sha256()
        forecast = self._forecast(current_state)
        # Local to this call: never reuse a root/forecast across decisions.
        forecast_hash = forecast.sha256() if self.reuse_decision_hashes else None
        hash_context = ({"root_hash": live_hash_before,
                         "forecast_hash": forecast_hash}
                        if self.reuse_decision_hashes else {})
        if self.parallel_workers:
            hold, by_id = self._evaluate_parallel_branches(
                forecast, forecast_hash, live_hash_before, records, order)
        else:
            hold = self.evaluator.evaluate_hold(forecast, **hash_context)
            by_id = {}
            for proposal_id in order:
                by_id[proposal_id] = self.evaluator.evaluate_candidate(
                    forecast, records[proposal_id], self._candidate_specs[proposal_id],
                    **hash_context)
        live_hash_after = self.engine.canonical_state_sha256()
        if live_hash_after != live_hash_before:
            raise AssertionError("B4_HYPOTHETICAL_BRANCH_MUTATED_LIVE_ENGINE")

        selected_id = None
        selected_score = hold.J_H_bit_s
        for proposal_id in canonical_ids:
            branch = by_id[proposal_id]
            if branch.J_H_bit_s < selected_score:
                selected_id = proposal_id
                selected_score = branch.J_H_bit_s
        ordered = [hold]+[by_id[key] for key in canonical_ids]
        forecast_hashes = {row.forecast_sha256 for row in ordered}
        start_hashes = {row.start_state_sha256 for row in ordered}
        if len(forecast_hashes) != 1:
            raise AssertionError("B4_BRANCH_FORECAST_HASH_MISMATCH")
        if start_hashes != {live_hash_before}:
            raise AssertionError("B4_BRANCH_START_STATE_MISMATCH")
        decision = {
            "schema": "gate_f2_b4_root_decision_v1",
            "selected_action": "HOLD" if selected_id is None else "REPLACE",
            "selected_proposal_id": selected_id,
            "selected_J_H_bit_s": selected_score,
            "HOLD_J_H_bit_s": hold.J_H_bit_s,
            "branch_count": len(ordered),
            "valid_branch_count": sum(row.valid for row in ordered),
            "invalid_branch_count": sum(not row.valid for row in ordered),
            "branches": [row.public_record() for row in ordered],
            "forecast_start_time_s": forecast.start_time_s,
            "current_lambda_bit_s": dict(sorted(forecast.rates_bit_s.items())),
            "forecast_horizon_s": forecast.horizon_s,
            "forecast_type": forecast.forecast_type,
            "forecast_sha256": (forecast.sha256() if forecast_hash is None else forecast_hash),
            "same_forecast_all_branches": len(forecast_hashes) == 1,
            "same_start_state_all_branches": len(start_hashes) == 1,
            "horizon_s": self.horizon_s,
            "information_class": self.information_class,
            "root_action_only": True,
            "multi_step_future_controller_actions": False,
            "live_state_sha256_before": live_hash_before,
            "live_state_sha256_after": live_hash_after,
            "live_engine_mutated": False,
            "evaluation_order": order,
            "canonical_proposer_order": canonical_ids,
            "objective": "exact incremental unfinished-work area J(t+10)-J(t)",
            "terminal_penalty": False,
            "post_horizon_drain": False,
        }
        decision["decision_sha256"] = canonical_sha256(decision)
        self.last_decision = decision
        return decision

    def observe(self, current_state, proposal_set, context):
        decision = self.evaluate_root_actions(current_state, proposal_set, context)
        selected = decision["selected_proposal_id"]
        metadata = (
            ("scientific_score", "J_H"),
            ("selected_J_H_bit_s", decision["selected_J_H_bit_s"]),
            ("HOLD_J_H_bit_s", decision["HOLD_J_H_bit_s"]),
            ("branch_count", decision["branch_count"]),
            ("valid_branch_count", decision["valid_branch_count"]),
            ("invalid_branch_count", decision["invalid_branch_count"]),
            ("forecast_sha256", decision["forecast_sha256"]),
            ("horizon_s", self.horizon_s),
            ("information_class", self.information_class),
            ("root_action_only", True),
            ("multi_step_future_controller_actions", False),
            ("decision_sha256", decision["decision_sha256"]),
        )
        return (ControllerAction("HOLD", decision_metadata=metadata)
                if selected is None
                else ControllerAction("REPLACE", selected, metadata))

    def on_action_result(self, record):
        return None
