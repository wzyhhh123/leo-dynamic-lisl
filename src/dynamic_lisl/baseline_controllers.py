"""Gate F1 deterministic B0-B3 controller interfaces and scaffolds.

B1 and B3 accept injected fixture-only scoring functions because no scientific
scalar scoring rule is frozen yet.  Construction without that explicit test
flag fails, preventing accidental use as a scientific baseline.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ControllerAction:
    kind: str
    proposal_id: str | None = None
    decision_metadata: tuple = ()

    def __post_init__(self):
        if self.kind not in ("HOLD", "REPLACE"):
            raise ValueError("CONTROLLER_ACTION_MUST_BE_HOLD_OR_REPLACE")
        if (self.kind == "REPLACE") != (self.proposal_id is not None):
            raise ValueError("REPLACE_REQUIRES_EXACT_PROPOSAL_ID")

    def to_dict(self):
        return {"kind": self.kind, "proposal_id": self.proposal_id,
                "decision_metadata": dict(self.decision_metadata)}


class StaticHoldController:
    controller_id = "B0_STATIC_HOLD"
    information_class = "CURRENT_STATE_ONLY"
    candidate_budget_not_used_by_design = True

    def observe(self, current_state, proposal_set, context):
        return ControllerAction("HOLD", decision_metadata=(
            ("candidate_budget_not_used_by_design", True),))

    def on_action_result(self, record):
        return None


class _InjectedScoreController:
    """Shared correctness-only scoring harness, never a scientific formula."""

    information_class = "CURRENT_STATE_ONLY"

    def __init__(self, controller_id, score_provider, *, test_only=False):
        if not test_only:
            raise RuntimeError("SCORING_CONTRACT_UNRESOLVED_REQUIRES_HUMAN_FREEZE")
        if not callable(score_provider):
            raise TypeError("FIXTURE_SCORE_PROVIDER_REQUIRED")
        self.controller_id = controller_id
        self.score_provider = score_provider
        self.test_only_not_frozen_for_f3 = True

    def _scores(self, current_state, proposal_set, context):
        values = dict(self.score_provider(current_state, proposal_set, context))
        if "HOLD" not in values:
            raise ValueError("FIXTURE_SCORES_REQUIRE_HOLD")
        missing = [row["proposal_id"] for row in proposal_set["proposals"]
                   if row["proposal_id"] not in values]
        if missing:
            raise ValueError("FIXTURE_SCORE_MISSING_PROPOSAL")
        return values

    @staticmethod
    def _select(scores):
        # HOLD wins exact ties; candidate tie-break is proposal ID.
        hold = float(scores["HOLD"])
        candidates = sorted((float(value), key) for key, value in scores.items()
                            if key != "HOLD")
        if not candidates:
            return "HOLD", None, 0.0
        best_value = max(value for value, _ in candidates)
        best_id = min(key for value, key in candidates if value == best_value)
        improvement = best_value-hold
        return (("REPLACE", best_id, improvement) if improvement > 0.0
                else ("HOLD", None, improvement))


class IgnoreSetupDynamicScaffold(_InjectedScoreController):
    """B1 interface semantics with fixture scores; scientific score unresolved."""

    def __init__(self, score_provider, *, test_only=False):
        super().__init__("B1_IGNORE_SETUP_DYNAMIC", score_provider,
                         test_only=test_only)

    def observe(self, current_state, proposal_set, context):
        scores = self._scores(current_state, proposal_set, context)
        kind, proposal_id, improvement = self._select(scores)
        metadata = (("decision_assumed_setup_s", 0.0),
                    ("fixture_score_injection", True),
                    ("improvement", improvement))
        return ControllerAction(kind, proposal_id, metadata)

    def on_action_result(self, record):
        return None


class HysteresisMinimumHoldController:
    """B2 parameterized wrapper; parameters are not frozen for F3."""

    information_class = "CURRENT_STATE_ONLY"

    def __init__(self, base_controller, minimum_hold_s, improvement_threshold):
        self.base = base_controller
        self.controller_id = "B2_HYSTERESIS_MINIMUM_HOLD"
        self.minimum_hold_s = float(minimum_hold_s)
        self.improvement_threshold = float(improvement_threshold)
        if self.minimum_hold_s < 0.0 or self.improvement_threshold < 0.0:
            raise ValueError("NONNEGATIVE_B2_PARAMETERS_REQUIRED")
        self.last_accepted_switch_time = None
        self.test_only_not_frozen_for_f3 = True

    def observe(self, current_state, proposal_set, context):
        base = self.base.observe(current_state, proposal_set, context)
        if base.kind == "HOLD":
            return base
        now = float(current_state["time_s"])
        if (self.last_accepted_switch_time is not None
                and now-self.last_accepted_switch_time < self.minimum_hold_s):
            return ControllerAction("HOLD", decision_metadata=(
                ("blocked_by", "MINIMUM_HOLD"),))
        improvement = float(dict(base.decision_metadata).get("improvement", 0.0))
        # Exact equality is accepted; this is deterministic and fixture-tested.
        if improvement < self.improvement_threshold:
            return ControllerAction("HOLD", decision_metadata=(
                ("blocked_by", "IMPROVEMENT_THRESHOLD"),
                ("improvement", improvement)))
        return ControllerAction("REPLACE", base.proposal_id,
                                base.decision_metadata+(
                                    ("b2_minimum_hold_s", self.minimum_hold_s),
                                    ("b2_improvement_threshold",
                                     self.improvement_threshold)))

    def on_action_result(self, record):
        if record.get("selected_action", {}).get("kind") == "REPLACE" and record.get("accepted"):
            self.last_accepted_switch_time = float(record["decision_epoch_s"])
        if hasattr(self.base, "on_action_result"):
            self.base.on_action_result(record)


class SetupAwareGreedyScaffold(_InjectedScoreController):
    """B3 CURRENT_STATE_ONLY firewall with unresolved scientific scoring."""

    def __init__(self, score_provider, *, test_only=False):
        super().__init__("B3_SETUP_AWARE_GREEDY", score_provider,
                         test_only=test_only)

    def observe(self, current_state, proposal_set, context):
        forbidden = {"future_trace", "future_trace_sha256", "future_action_ids",
                     "realized_future_traffic", "final_J", "forecast"}
        if forbidden & set(current_state):
            raise AssertionError("B3_CURRENT_STATE_FIREWALL_VIOLATION")
        scores = self._scores(current_state, proposal_set, context)
        kind, proposal_id, improvement = self._select(scores)
        return ControllerAction(kind, proposal_id, (
            ("uses_actual_setup_metadata", True),
            ("fixture_score_injection", True),
            ("improvement", improvement)))

    def on_action_result(self, record):
        return None
