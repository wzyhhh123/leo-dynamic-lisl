"""Gate C4: apply operational policy after profiling; never modify proposals."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OperationalPolicy:
    mode: str
    max_outage_s: float | None = None

    def __post_init__(self):
        if self.mode not in ("STRICT_CONNECTED", "BOUNDED_OUTAGE"):
            raise ValueError("Unknown operational policy")
        if self.mode == "STRICT_CONNECTED" and self.max_outage_s is not None:
            raise ValueError("STRICT_CONNECTED has no outage parameter")
        if self.mode == "BOUNDED_OUTAGE" and (self.max_outage_s is None or self.max_outage_s < 0):
            raise ValueError("BOUNDED_OUTAGE requires nonnegative T_max")

    def apply(self, profile):
        if not profile.get("executable"):
            return dict(accepted=False, reason="PHYSICAL_INFEASIBLE", profile=profile)
        if not profile["partition_occurs"]:
            return dict(accepted=True, reason=None, profile=profile)
        if self.mode == "STRICT_CONNECTED":
            return dict(accepted=False, reason="STRICT_CONNECTIVITY_VIOLATION", profile=profile)
        if not profile["recovery_plan_exists"]:
            reason = ("NATURAL_EXPIRY_UNSAFE" if profile.get("natural_expiry_disconnect")
                      else "UNRECOVERABLE_PARTITION")
            return dict(accepted=False, reason=reason, profile=profile)
        if profile["recovery_time"] is None:
            return dict(accepted=False, reason="NO_KNOWN_RECOVERY", profile=profile)
        # Equality is accepted by contract and tested.
        if profile["outage_duration"] <= self.max_outage_s:
            return dict(accepted=True, reason=None, profile=profile)
        return dict(accepted=False, reason="OUTAGE_BOUND_EXCEEDED", profile=profile,
                    classification="bounded_but_long_partition")


def legal_action_interface(executor, proposals, physical_layer, fixed_edges, policy, horizon_s):
    """ACCEPT/REJECT only. No proposal repair, reranking, or topology optimization."""
    decisions = []
    for proposal in proposals:
        physical = physical_layer.evaluate(executor, **proposal)
        if not physical["accepted"]:
            decisions.append(dict(accepted=False, reason=physical["reason"], proposal=proposal))
            continue
        profile = __import__("dynamic_lisl.transition_profiler", fromlist=["profile_transition"]).profile_transition(
            executor, [physical["command"]], fixed_edges, horizon_s)
        decision = policy.apply(profile)
        decisions.append(dict(accepted=decision["accepted"], reason=decision["reason"],
                              proposal=proposal, profile=profile))
    return dict(decisions=decisions,
                accepted_count=sum(x["accepted"] for x in decisions),
                hold_only=not any(x["accepted"] for x in decisions),
                fallback="HOLD" if not any(x["accepted"] for x in decisions) else None)

