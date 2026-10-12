"""Gate F1 deterministic terminal-pair proposal and reject-only safety adapter.

The proposer has no queue, objective, traffic-future, or controller input.  It
only applies the hard physical/safety filters frozen by Gate F0 Human Freeze v1
and then enforces the 8/8 structural quota within the top-16 budget.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from .operational_policy import OperationalPolicy
from .terminal_executor import pair
from .transition_profiler import profile_transition


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def canonical_sha256(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CandidateSpec:
    """Concrete terminal-level REPLACE proposal before hard filtering."""

    proposal_id: str
    proposal: dict
    old_binding: tuple = ()

    def __post_init__(self):
        if not self.proposal_id:
            raise ValueError("EMPTY_PROPOSAL_ID")
        if "a" not in self.proposal or "b" not in self.proposal:
            raise ValueError("CANDIDATE_REQUIRES_CONCRETE_TERMINAL_PAIR")


class RegimeSafetyAdapter:
    """Apply the frozen regime policy without repair, substitution, or rerank."""

    def __init__(self, regime, transition_profiler=profile_transition):
        self.regime = str(regime)
        self.transition_profiler = transition_profiler
        if self.regime == "Z_SPARSE_REFERENCE":
            self.policy = OperationalPolicy("BOUNDED_OUTAGE", 2.0)
        elif self.regime == "Z_MODERATE":
            self.policy = OperationalPolicy("STRICT_CONNECTED")
        else:
            raise ValueError("UNKNOWN_TOPOLOGY_REGIME")

    def evaluate(self, executor, command, fixed_edges, horizon_s):
        profile = self.transition_profiler(
            executor, [command], fixed_edges, float(horizon_s))
        decision = self.policy.apply(profile)
        return {
            "accepted": bool(decision["accepted"]),
            "reason": decision["reason"],
            "profile": profile,
            "policy": self.policy.mode,
            "max_transition_outage_s": self.policy.max_outage_s,
            "reject_only": True,
        }


def _binding_document(binding):
    if not binding:
        return []
    endpoints = pair(*binding)
    return [list(endpoints[0]), list(endpoints[1])]


def _rank_key(record):
    return (
        -float(record["usable_lifetime_s"]),
        int(record["plane_gap"]),
        canonical_json(record["old_edge"]),
        canonical_json(record["old_terminal_ids"]),
        canonical_json(record["new_edge"]),
        canonical_json(record["new_terminal_ids"]),
        record["proposal_id"],
    )


def allocate_structural_quota(records, top_k=16, per_stratum=8):
    """Pure deterministic 8/8 allocation with one-sided spillover."""
    if top_k != 16 or per_stratum != 8:
        raise ValueError("FROZEN_GATE_F1_BUDGET_IS_16_WITH_8_PER_STRATUM")
    groups = {
        name: sorted((row for row in records if row["stratum"] == name),
                     key=_rank_key)
        for name in ("MBB_STRUCTURALLY_FEASIBLE", "BBM_REQUIRED")
    }
    chosen = groups["MBB_STRUCTURALLY_FEASIBLE"][:per_stratum]
    chosen += groups["BBM_REQUIRED"][:per_stratum]
    if len(groups["MBB_STRUCTURALLY_FEASIBLE"]) < per_stratum:
        need = per_stratum-len(groups["MBB_STRUCTURALLY_FEASIBLE"])
        chosen += groups["BBM_REQUIRED"][per_stratum:per_stratum+need]
    if len(groups["BBM_REQUIRED"]) < per_stratum:
        need = per_stratum-len(groups["BBM_REQUIRED"])
        chosen += groups["MBB_STRUCTURALLY_FEASIBLE"][per_stratum:per_stratum+need]
    return tuple(sorted(chosen, key=lambda row: (
        0 if row["stratum"] == "MBB_STRUCTURALLY_FEASIBLE" else 1,
        _rank_key(row))))


class FrozenTerminalPairProposer:
    """Common result-blind proposer used by B1/B2/B3 and future B4."""

    top_k = 16
    per_stratum = 8

    def __init__(self, transition_profiler=profile_transition):
        self.transition_profiler = transition_profiler

    def propose(self, executor, candidates, physical_layer, fixed_edges, regime):
        candidates = tuple(candidates)
        if len({row.proposal_id for row in candidates}) != len(candidates):
            raise ValueError("DUPLICATE_PROPOSAL_ID")
        safety = RegimeSafetyAdapter(regime, self.transition_profiler)
        legal = []
        pruned = []
        specs = {}
        for spec in sorted(candidates, key=lambda row: row.proposal_id):
            a, b = tuple(spec.proposal["a"]), tuple(spec.proposal["b"])
            ends = pair(a, b)
            exact = next((link for link in executor.links.values()
                          if link.endpoints == ends and not link.draining), None)
            if exact is not None:
                pruned.append({"proposal_id": spec.proposal_id,
                               "reason": "EXACT_PHYSICAL_NOOP"})
                continue
            physical = physical_layer.evaluate(executor, **spec.proposal)
            if not physical["accepted"]:
                pruned.append({"proposal_id": spec.proposal_id,
                               "reason": physical["reason"]})
                continue
            command = physical["command"]
            geometry = physical["geometry"]
            # Profile through completion of this transition only.  Natural
            # expiry after completion is reported separately by the runner.
            horizon = float(geometry["ready_time"])+1e-7
            safety_result = safety.evaluate(executor, command, fixed_edges, horizon)
            if not safety_result["accepted"]:
                pruned.append({"proposal_id": spec.proposal_id,
                               "reason": safety_result["reason"]})
                continue
            old_doc = _binding_document(spec.old_binding)
            old_edge = (sorted([old_doc[0][0], old_doc[1][0]])
                        if old_doc else [])
            new_terminals = [list(ends[0]), list(ends[1])]
            window = geometry["window"]
            stratum = ("MBB_STRUCTURALLY_FEASIBLE"
                        if command.release_after else "BBM_REQUIRED")
            record = {
                "proposal_id": spec.proposal_id,
                "stratum": stratum,
                "old_edge": old_edge,
                "old_terminal_ids": old_doc,
                "new_edge": sorted([ends[0][0], ends[1][0]]),
                "new_terminal_ids": new_terminals,
                "ready_time_s": float(geometry["ready_time"]),
                "setup_duration_s": float(geometry["ready_time"])-executor.now,
                "remaining_lifetime_s": float(geometry["remaining_lifetime_s"]),
                "usable_lifetime_s": float(geometry["usable_lifetime_s"]),
                "plane_gap": int(window["plane_gap"]),
                "physical_reason": None,
                "safety_policy": safety_result["policy"],
                "transition_profile_classification":
                    safety_result["profile"].get("classification"),
            }
            legal.append(record)
            specs[spec.proposal_id] = spec
        selected = allocate_structural_quota(legal, self.top_k, self.per_stratum)
        document = {
            "schema": "gate_f1_proposal_set_v1",
            "time_s": executor.now,
            "regime": regime,
            "candidate_top_k": self.top_k,
            "quota": {"MBB_STRUCTURALLY_FEASIBLE": self.per_stratum,
                      "BBM_REQUIRED": self.per_stratum},
            "proposals": list(selected),
        }
        return {
            **document,
            "proposal_set_sha256": canonical_sha256(document),
            "pruned": pruned,
            "candidate_specs": {row["proposal_id"]: specs[row["proposal_id"]]
                                for row in selected},
        }
