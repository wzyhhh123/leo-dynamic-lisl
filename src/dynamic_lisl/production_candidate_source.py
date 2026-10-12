"""Frozen Gate F3 production CandidateSpec materializer and drain policy.

This module is deliberately upstream of ``FrozenTerminalPairProposer``.  It
materializes a bounded, traffic-blind one-for-one replacement universe from the
current Gate B state and the existing Gate C interval catalog.  It does not
score or select controller actions.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from .candidate_proposer import CandidateSpec, canonical_json, canonical_sha256
from .terminal_executor import ACTIVE, IDLE, pair


SOURCE_NAME = "DETERMINISTIC_ONE_FOR_ONE_PHYSICAL_REPLACEMENT_V1"
RAW_BBM_CAP = 32
RAW_MBB_CAP = 32
TOTAL_RAW_CAP = 64
FROZEN_SETUP_FILE_SHA256 = (
    "66ca6881b739aad87ccd850a89f0dcddb9bb35684f48fcdee2e0aece33fadd19"
)


def _file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _canonical_binding(binding):
    return pair(*binding)


def _binding_json(binding):
    return [list(endpoint) for endpoint in _canonical_binding(binding)]


def _satellite_pair(binding):
    binding = _canonical_binding(binding)
    return tuple(sorted((binding[0][0], binding[1][0])))


@dataclass(frozen=True)
class FrozenSetupParameters:
    retarget_a_s: float
    retarget_b_s: float
    acquisition_s: float
    source_file: str
    source_file_sha256: str
    source_status: str

    @property
    def ready_offset_s(self):
        return max(self.retarget_a_s, self.retarget_b_s) + self.acquisition_s

    @classmethod
    def load(cls, project):
        project = Path(project)
        relative = Path("configs/hardware_gate_c_simplified_v1.json")
        path = project / relative
        digest = _file_sha256(path)
        if digest != FROZEN_SETUP_FILE_SHA256:
            raise ValueError("FROZEN_SETUP_PARAMETER_SOURCE_HASH_MISMATCH")
        document = json.loads(path.read_text(encoding="utf-8-sig"))
        fixture = document.get("audit_setup_fixture")
        if not isinstance(fixture, dict):
            raise ValueError(
                "GATE_F3_CANDIDATE_SOURCE_BLOCKED_BY_SETUP_PARAMETER_SOURCE_AMBIGUITY"
            )
        expected = {
            "retarget_a_s": 1.0,
            "retarget_b_s": 1.0,
            "acquisition_s": 1.0,
            "status": "synthetic_sensitivity_only",
        }
        if fixture != expected:
            raise ValueError(
                "GATE_F3_CANDIDATE_SOURCE_BLOCKED_BY_SETUP_PARAMETER_SOURCE_AMBIGUITY"
            )
        return cls(
            float(fixture["retarget_a_s"]),
            float(fixture["retarget_b_s"]),
            float(fixture["acquisition_s"]),
            relative.as_posix(),
            digest,
            str(fixture["status"]),
        )


@dataclass(frozen=True)
class _RawAction:
    stratum: str
    remaining_lifetime_s: float
    plane_gap: int
    old_binding: tuple
    new_pair: tuple
    release_after: tuple
    identity: dict
    candidate_spec: CandidateSpec

    @property
    def order_key(self):
        return (
            -self.remaining_lifetime_s,
            self.plane_gap,
            self.old_binding,
            self.new_pair,
        )


class ProductionCandidateSource:
    """Bounded deterministic current-state CandidateSpec materializer."""

    source_name = SOURCE_NAME
    raw_BBM_source_cap = RAW_BBM_CAP
    raw_MBB_source_cap = RAW_MBB_CAP
    total_raw_source_cap = TOTAL_RAW_CAP

    def __init__(self, catalog, setup_parameters):
        self.catalog = catalog
        self.setup = setup_parameters
        self.last_report = None

    @classmethod
    def from_project(cls, catalog, project):
        return cls(catalog, FrozenSetupParameters.load(project))

    @staticmethod
    def _eligible_old_links(executor):
        rows = []
        for link in executor.links.values():
            endpoints = _canonical_binding(link.endpoints)
            terminals = [executor.terminals[endpoint] for endpoint in endpoints]
            if link.draining or link.release_owner is not None:
                continue
            if not executor.now < float(link.visibility_end):
                continue
            if any(terminal.phase != ACTIVE for terminal in terminals):
                continue
            if any(terminal.reservation_id is not None for terminal in terminals):
                continue
            rows.append((endpoints, link))
        return tuple(sorted(rows, key=lambda row: row[0]))

    @staticmethod
    def _identity(decision_time_s, state_sha, old_binding, new_pair,
                  release_after):
        return {
            "decision_time_s": float(decision_time_s),
            "canonical_state_sha256": str(state_sha),
            "canonical_old_binding": _binding_json(old_binding),
            "canonical_new_terminal_pair": _binding_json(new_pair),
            "canonical_release_after": [
                _binding_json(binding) for binding in release_after
            ],
        }

    def _raw_action(self, executor, state_sha, old_binding, window, stratum,
                    release_after):
        new_pair = _canonical_binding((window.endpoint_a, window.endpoint_b))
        releases = tuple(_canonical_binding(value) for value in release_after)
        identity = self._identity(
            executor.now, state_sha, old_binding, new_pair, releases)
        digest = canonical_sha256(identity)
        proposal = {
            "a": new_pair[0],
            "b": new_pair[1],
            "retarget_a": self.setup.retarget_a_s,
            "retarget_b": self.setup.retarget_b_s,
            "acquisition": self.setup.acquisition_s,
        }
        if releases:
            proposal["release_after"] = releases
        return _RawAction(
            stratum=stratum,
            remaining_lifetime_s=float(window.end_s)-float(executor.now),
            plane_gap=int(window.plane_gap),
            old_binding=_canonical_binding(old_binding),
            new_pair=new_pair,
            release_after=releases,
            identity=identity,
            candidate_spec=CandidateSpec(
                "F3SRC-" + digest[:24], proposal,
                _canonical_binding(old_binding)),
        )

    def materialize(self, executor, canonical_state_sha256):
        now = float(executor.now)
        old_rows = self._eligible_old_links(executor)
        windows = tuple(self.catalog.terminal_pair_candidates(
            now, executor.satellite_ids))
        active_terminal_owner = {}
        active_by_pair = {}
        for link in executor.links.values():
            endpoints = _canonical_binding(link.endpoints)
            for endpoint in endpoints:
                active_terminal_owner[endpoint] = endpoints
            active_by_pair[_satellite_pair(endpoints)] = endpoints
        reserved = {
            endpoint
            for reservation in executor.reservations.values()
            for endpoint in reservation.endpoints
        }
        pending_satellite_pairs = {
            _satellite_pair(reservation.endpoints)
            for reservation in executor.reservations.values()
        }

        rejected = []
        raw = {"BBM_RAW": {}, "MBB_RAW": {}}
        for old_binding, _link in old_rows:
            old_endpoints = set(old_binding)
            old_satellite_pair = _satellite_pair(old_binding)
            for window in windows:
                new_pair = _canonical_binding(
                    (window.endpoint_a, window.endpoint_b))
                new_endpoints = set(new_pair)
                rejection = None
                if new_pair == old_binding:
                    rejection = "NO_OP_CURRENT_BINDING"
                elif new_endpoints & reserved:
                    rejection = "RESERVED_TERMINAL_CONFLICT"
                else:
                    occupied_other = {
                        endpoint for endpoint in new_endpoints
                        if endpoint in active_terminal_owner
                        and active_terminal_owner[endpoint] != old_binding
                    }
                    if occupied_other:
                        rejection = "MULTI_OLD_BINDING_CONFLICT"
                new_satellite_pair = _satellite_pair(new_pair)
                existing = active_by_pair.get(new_satellite_pair)
                if rejection is None and existing is not None:
                    if existing != old_binding:
                        rejection = "PARALLEL_SATELLITE_PAIR_CONFLICT"
                    elif not (new_endpoints & old_endpoints):
                        rejection = "PARALLEL_SATELLITE_PAIR_CONFLICT"
                if (rejection is None
                        and new_satellite_pair in pending_satellite_pairs):
                    rejection = "PARALLEL_SATELLITE_PAIR_CONFLICT"
                if rejection is not None:
                    rejected.append({
                        "old_binding": _binding_json(old_binding),
                        "new_terminal_pair": _binding_json(new_pair),
                        "reason": rejection,
                    })
                    continue

                touches_old = bool(new_endpoints & old_endpoints)
                if touches_old:
                    # Any non-old endpoint must be truly idle and unreserved.
                    other = new_endpoints-old_endpoints
                    if any(executor.terminals[e].phase != IDLE
                           or executor.terminals[e].current_peer is not None
                           or executor.terminals[e].reservation_id is not None
                           for e in other):
                        rejected.append({
                            "old_binding": _binding_json(old_binding),
                            "new_terminal_pair": _binding_json(new_pair),
                            "reason": "MULTI_OLD_BINDING_CONFLICT",
                        })
                        continue
                    stratum = "BBM_RAW"
                    releases = ()
                else:
                    if any(executor.terminals[e].phase != IDLE
                           or executor.terminals[e].current_peer is not None
                           or executor.terminals[e].reservation_id is not None
                           for e in new_pair):
                        rejected.append({
                            "old_binding": _binding_json(old_binding),
                            "new_terminal_pair": _binding_json(new_pair),
                            "reason": "MULTI_OLD_BINDING_CONFLICT",
                        })
                        continue
                    if new_satellite_pair == old_satellite_pair:
                        rejected.append({
                            "old_binding": _binding_json(old_binding),
                            "new_terminal_pair": _binding_json(new_pair),
                            "reason": "PARALLEL_SATELLITE_PAIR_CONFLICT",
                        })
                        continue
                    stratum = "MBB_RAW"
                    releases = (old_binding,)

                action = self._raw_action(
                    executor, canonical_state_sha256, old_binding, window,
                    stratum, releases)
                identity_key = canonical_json(action.identity)
                raw[stratum].setdefault(identity_key, action)

        ordered = {
            key: tuple(sorted(values.values(), key=lambda row: row.order_key))
            for key, values in raw.items()
        }
        selected = {
            "BBM_RAW": ordered["BBM_RAW"][:RAW_BBM_CAP],
            "MBB_RAW": ordered["MBB_RAW"][:RAW_MBB_CAP],
        }
        specs = tuple(
            row.candidate_spec
            for stratum in ("BBM_RAW", "MBB_RAW")
            for row in selected[stratum]
        )
        if len(specs) > TOTAL_RAW_CAP:
            raise AssertionError("F3_RAW_SOURCE_TOTAL_CAP_EXCEEDED")
        if len({spec.proposal_id for spec in specs}) != len(specs):
            raise AssertionError("F3_SOURCE_ID_COLLISION")
        source_document = {
            "schema": "gate_f3_production_candidate_source_result_v1",
            "source_name": SOURCE_NAME,
            "time_s": now,
            "canonical_state_sha256": str(canonical_state_sha256),
            "eligible_old_bindings": [
                _binding_json(binding) for binding, _link in old_rows],
            "current_catalog_window_count": len(windows),
            "uncapped_counts": {
                key: len(ordered[key]) for key in sorted(ordered)},
            "selected_counts": {
                key: len(selected[key]) for key in sorted(selected)},
            "selected_order": [
                {
                    "proposal_id": row.candidate_spec.proposal_id,
                    "stratum": row.stratum,
                    "identity": row.identity,
                    "remaining_lifetime_s": row.remaining_lifetime_s,
                    "plane_gap": row.plane_gap,
                }
                for stratum in ("BBM_RAW", "MBB_RAW")
                for row in selected[stratum]
            ],
            "rejection_counts": dict(sorted(Counter(
                row["reason"] for row in rejected).items())),
            "raw_caps": {"BBM_RAW": RAW_BBM_CAP,
                         "MBB_RAW": RAW_MBB_CAP,
                         "total": TOTAL_RAW_CAP},
            "setup_source": {
                "file": self.setup.source_file,
                "sha256": self.setup.source_file_sha256,
                "status": self.setup.source_status,
            },
        }
        source_document["source_sha256"] = canonical_sha256(source_document)
        self.last_report = {**source_document, "rejections": rejected}
        return specs

    def __call__(self, state, context):
        executor = context["terminal_executor"]
        if abs(float(state["time_s"])-float(executor.now)) > 1e-12:
            raise AssertionError("F3_SOURCE_STATE_TIME_MISMATCH")
        return self.materialize(executor, state["current_state_sha256"])


@dataclass(frozen=True)
class DrainDecisionPolicy:
    """Pure scheduling policy consumed by the future manifest-driven runner."""

    arrival_horizon_s: float = 240.0
    drain_limit_s: float = 600.0
    cadence_s: float = 2.0
    zero_threshold_bits: float = 0.01

    def __post_init__(self):
        if (self.arrival_horizon_s != 240.0
                or self.drain_limit_s != 600.0
                or self.cadence_s != 2.0):
            raise ValueError("FROZEN_F3_DRAIN_POLICY_VALUES_REQUIRED")

    def is_periodic_epoch(self, time_s, t0_s=0.0):
        time_s = float(time_s)
        if time_s < float(t0_s)-1e-12 or time_s >= self.drain_limit_s-1e-12:
            return False
        quotient = (time_s-float(t0_s))/self.cadence_s
        return abs(quotient-round(quotient)) <= 1e-12

    def decision_due(self, time_s, unfinished_work_bits, t0_s=0.0):
        if not self.is_periodic_epoch(time_s, t0_s):
            return False
        if float(time_s) < self.arrival_horizon_s-1e-12:
            return True
        return float(unfinished_work_bits) > self.zero_threshold_bits

    def possible_epochs(self, t0_s=0.0):
        result = []
        value = float(t0_s)
        while value < self.drain_limit_s-1e-12:
            result.append(value)
            value += self.cadence_s
        return tuple(result)

    def assert_arrival_cutoff_state(self, time_s, current_rates):
        if abs(float(time_s)-self.arrival_horizon_s) > 1e-12:
            raise ValueError("NOT_ARRIVAL_CUTOFF_EPOCH")
        if any(abs(float(value)) > 0.0 for value in current_rates.values()):
            raise AssertionError("F3_T240_MUST_OBSERVE_ZERO_ARRIVAL_RATE")
        return True

