"""Read-only Gate C/B joint validation and a single atomic Gate B commit.

Scientific limits/policy/time frame are mandatory caller-supplied parameters.
Engineering validation of a draft is not human scientific freezing.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math

from ..terminal_executor import ACTIVE, IDLE
from ..transition_profiler import profile_transition
from .joint_action import JointAction, canonical_sha256, terminal_state_hash
from .physical_trial import physical_trial_executor


@dataclass(frozen=True)
class BatchValidationResult:
    action: JointAction
    accepted: bool
    reason: str | None
    root_terminal_sha256: str
    commands: tuple = ()
    member_results: tuple = ()
    profile: dict | None = None
    safety_completion_s: float | None = None

    def to_dict(self):
        profile = None if self.profile is None else {
            k: v for k, v in self.profile.items() if k != "final_executor"}
        return {"schema": "f3_v2_batch_validation_v1", "action": self.action.to_dict(),
                "accepted": self.accepted, "reason": self.reason,
                "root_terminal_sha256": self.root_terminal_sha256,
                "commands": [asdict(c) for c in self.commands],
                "member_results": list(self.member_results), "profile": profile,
                "safety_completion_s": self.safety_completion_s}

    @property
    def seal_sha256(self):
        return canonical_sha256(self.to_dict())


class BatchPhysicalValidator:
    def __init__(self, physical_layer, *, max_batch_replace, observation_end_s,
                 absolute_time_frame_id, counterfactual_physical_clone=True):
        if type(max_batch_replace) is not int or not 1 <= max_batch_replace <= 4:
            raise ValueError("EXPLICIT_MAX_BATCH_IN_1_TO_4_REQUIRED")
        if type(counterfactual_physical_clone) is not bool:
            raise ValueError("EXPLICIT_BOOLEAN_PHYSICAL_CLONE_REQUIRED")
        if not math.isfinite(observation_end_s) or observation_end_s <= 0:
            raise ValueError("INVALID_OBSERVATION_END")
        if not absolute_time_frame_id:
            raise ValueError("MISSING_TIME_FRAME")
        self.physical_layer = physical_layer
        self.max_batch_replace = max_batch_replace
        self.observation_end_s = float(observation_end_s)
        self.absolute_time_frame_id = absolute_time_frame_id
        self.counterfactual_physical_clone = counterfactual_physical_clone

    def evaluate(self, executor, action, *, decision_root_sha256=None):
        if not isinstance(action, JointAction):
            raise TypeError("JOINT_ACTION_REQUIRED")
        root = terminal_state_hash(executor)

        def reject(reason, rows=()):
            if terminal_state_hash(executor) != root:
                raise AssertionError("VALIDATOR_CHANGED_LIVE_EXECUTOR")
            return BatchValidationResult(action, False, reason, root, member_results=tuple(rows))

        expected = root if decision_root_sha256 is None else decision_root_sha256
        if action.decision_root_sha256 != expected:
            return reject("DECISION_ROOT_MISMATCH")
        if action.absolute_time_frame_id != self.absolute_time_frame_id:
            return reject("ABSOLUTE_TIME_FRAME_MISMATCH")
        if action.decision_time_s != executor.now:
            return reject("DECISION_TIME_MISMATCH")
        if executor.now >= self.observation_end_s:
            return reject("DECISION_AT_OR_AFTER_OBSERVATION_END")
        if len(action.members) > self.max_batch_replace:
            return reject("MAX_BATCH_REPLACE_EXCEEDED")
        if not action.members:
            return BatchValidationResult(action, True, None, root,
                                         safety_completion_s=executor.now)
        used, old_used, target_pairs = set(), set(), set()
        old_links, modes = [], []
        # All checks refer to the same live root, never a partially committed trial.
        for m in action.members:
            if m.old_binding in old_used:
                return reject("DUPLICATE_OLD_BINDING")
            old_used.add(m.old_binding)
            if m.footprint & used:
                return reject("TERMINAL_FOOTPRINT_CONFLICT")
            used.update(m.footprint)
            if m.old_binding == m.new_terminal_pair:
                return reject("EXACT_PHYSICAL_NOOP")
            if any(e not in executor.terminals for e in m.footprint):
                return reject("UNKNOWN_DYNAMIC_TERMINAL")
            old = executor._link(m.old_binding)
            if old is None or old.draining or old.release_owner:
                return reject("OLD_BINDING_UNAVAILABLE")
            if any(executor.terminals[e].reservation_id for e in m.footprint):
                return reject("RESERVATION_CONFLICT")
            sp = tuple(e[0] for e in m.new_terminal_pair)
            if sp in target_pairs:
                return reject("ILLEGAL_PARALLEL_TARGET_PAIR")
            target_pairs.add(sp)
            if any(tuple(e[0] for e in r.endpoints) == sp for r in executor.reservations.values()):
                return reject("PARALLEL_PENDING_PAIR")
            if any(tuple(e[0] for e in l.endpoints) == sp and l.endpoints != m.old_binding
                   for l in executor.links.values()):
                return reject("ILLEGAL_PARALLEL_ACTIVE_PAIR")
            terminals = [executor.terminals[e] for e in m.new_terminal_pair]
            if any(t.phase not in (IDLE, ACTIVE) for t in terminals):
                return reject("TARGET_TERMINAL_BUSY")
            if any(t.current_peer is not None and t.terminal_id not in m.old_binding for t in terminals):
                return reject("CROSS_ACTION_RELEASE_OR_OTHER_OLD_BINDING")
            same_satpair = tuple(e[0] for e in m.old_binding) == sp
            idle = all(t.phase == IDLE and t.current_peer is None for t in terminals)
            if not idle and not (m.footprint & set(m.old_binding) & set(m.new_terminal_pair)):
                return reject("REPLACE_DOES_NOT_RELEASE_ITS_OLD_BINDING")
            # Same satellite pair on another terminal is a new BBM physical link.
            modes.append("MBB" if idle and not same_satpair else "BBM")
            old_links.append(old)

        commands, rows = [], []
        for m, old, mode in zip(action.members, old_links, modes):
            trial_input = physical_trial_executor(self.physical_layer, executor,
                enabled=self.counterfactual_physical_clone)
            result = self.physical_layer.evaluate(
                trial_input, *m.new_terminal_pair,
                retarget_a=m.retarget_a_s, retarget_b=m.retarget_b_s,
                acquisition=m.acquisition_s, orientation_a=m.orientation_a,
                orientation_b=m.orientation_b,
                release_after=(m.old_binding,) if mode == "MBB" else ())
            if not result["accepted"]:
                return reject(result["reason"], rows + [{"member_id": m.member_id, "accepted": False,
                                                        "reason": result["reason"]}])
            g = result["geometry"]
            ready, window_end = float(g["ready_time"]), float(g["window"]["end_s"])
            if window_end > self.observation_end_s:
                return reject("WINDOW_OUTSIDE_OBSERVATION_COVERAGE", rows)
            if not ready < window_end:
                return reject("INSUFFICIENT_LIFETIME", rows)
            commands.append(result["command"])
            # Include MBB old non-preemptive TX/drain and earlier natural expiry.
            release_time = (max([ready, *old.tx_end.values()]) if mode == "MBB"
                            else max([executor.now, *old.tx_end.values()]))
            old_down = min(old.visibility_end, release_time)
            rows.append({"member_id": m.member_id, "accepted": True, "reason": None,
                         "transition_mode": mode, "ready_time_s": ready,
                         "remaining_lifetime_s": float(g["remaining_lifetime_s"]),
                         "usable_lifetime_s": float(g["usable_lifetime_s"]),
                         "old_release_complete_bound_s": old_down,
                         "window": g["window"], "end_semantics": g["end_semantics"]})
        trial = executor.clone_for_counterfactual()
        try:
            trial.submit(commands)
        except (ValueError, AssertionError) as error:
            return reject("JOINT_GATE_B_TRANSACTION_REJECTED:" + str(error), rows)
        completion = max([executor.now] + [max(r["ready_time_s"], r["old_release_complete_bound_s"]) for r in rows])
        if completion > self.observation_end_s:
            return reject("TRANSITION_COMPLETION_OUTSIDE_OBSERVATION", rows)
        if terminal_state_hash(executor) != root:
            raise AssertionError("VALIDATOR_CHANGED_LIVE_EXECUTOR")
        return BatchValidationResult(action, True, None, root, tuple(commands), tuple(rows),
                                     safety_completion_s=completion)


class BatchSafetyValidator:
    def __init__(self, physical_validator, fixed_edges, policy):
        self.physical_validator = physical_validator
        self.fixed_edges = tuple(tuple(e) for e in fixed_edges)
        self.policy = policy

    def evaluate(self, executor, action, *, decision_root_sha256=None):
        result = self.physical_validator.evaluate(executor, action,
                                                 decision_root_sha256=decision_root_sha256)
        if not result.accepted or not action.members:
            return result
        profile = profile_transition(executor, result.commands, self.fixed_edges,
                                     result.safety_completion_s)
        decision = self.policy.apply(profile)
        if profile.get("executable"):
            final = profile["final_executor"]
            if any(final._link(m.old_binding) is not None for m in action.members):
                raise AssertionError("SAFETY_PROFILE_ENDED_BEFORE_OLD_RELEASE")
            # Completion can include unexpected natural events; no fake successes.
            if final.reservations.keys() - executor.reservations.keys():
                raise AssertionError("SAFETY_PROFILE_ENDED_DURING_SELECTED_SETUP")
        if terminal_state_hash(executor) != result.root_terminal_sha256:
            raise AssertionError("SAFETY_CHANGED_LIVE_EXECUTOR")
        return BatchValidationResult(action, bool(decision["accepted"]), decision["reason"],
                                     result.root_terminal_sha256, result.commands,
                                     result.member_results, profile, result.safety_completion_s)


class AtomicBatchExecutor:
    def __init__(self, validator):
        self.validator = validator

    def commit(self, executor, plan, *, decision_root_sha256=None):
        if not plan.accepted:
            raise ValueError("CANNOT_COMMIT_REJECTED_BATCH")
        if terminal_state_hash(executor) != plan.root_terminal_sha256:
            raise ValueError("STALE_VALIDATION_ROOT")
        # Revalidate the complete batch; cannot trust mutable evidence or stale catalog.
        check = self.validator.evaluate(executor, plan.action,
                                        decision_root_sha256=decision_root_sha256)
        if not check.accepted or check.seal_sha256 != plan.seal_sha256:
            raise ValueError("VALIDATION_COMMIT_MISMATCH")
        before = terminal_state_hash(executor)
        if plan.commands:
            try:
                executor.submit(plan.commands)
            except Exception:
                if terminal_state_hash(executor) != before:
                    raise AssertionError("ATOMIC_GATE_B_ROLLBACK_FAILURE")
                raise
        return {"schema": "f3_v2_batch_commit_v1", "accepted": True,
                "batch_id": plan.action.batch_id, "kind": plan.action.kind,
                "validation_sha256": plan.seal_sha256,
                "member_results": list(plan.member_results),
                "before_terminal_sha256": before,
                "after_terminal_sha256": terminal_state_hash(executor)}
