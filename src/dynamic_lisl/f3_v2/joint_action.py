"""Immutable concrete terminal-level replacement and batch identity."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math

from ..terminal_executor import pair


def canonical_sha256(value):
    body = json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def terminal_state_hash(executor):
    return canonical_sha256(executor.snapshot())


@dataclass(frozen=True)
class BatchReplaceMember:
    member_id: str
    canonical_index: int
    old_binding: tuple
    new_terminal_pair: tuple
    retarget_a_s: float
    retarget_b_s: float
    acquisition_s: float
    orientation_a: tuple = (0.0, 1.0, 0.0)
    orientation_b: tuple = (0.0, 1.0, 0.0)

    def __post_init__(self):
        if not self.member_id or type(self.canonical_index) is not int or self.canonical_index < 0:
            raise ValueError("INVALID_MEMBER_ID_OR_INDEX")
        old = pair(*self.old_binding)
        original_new = tuple(tuple(x) for x in self.new_terminal_pair)
        new = pair(*original_new)
        # Endpoint-specific durations/orientations follow the canonical endpoints.
        if original_new != new:
            raise ValueError("NEW_PAIR_MUST_BE_CANONICAL_FOR_ENDPOINT_PARAMETERS")
        object.__setattr__(self, "old_binding", old)
        object.__setattr__(self, "new_terminal_pair", new)
        for name in ("orientation_a", "orientation_b"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if any(not math.isfinite(x) or x < 0 for x in
               (self.retarget_a_s, self.retarget_b_s, self.acquisition_s)):
            raise ValueError("INVALID_SETUP_DURATION")

    @property
    def footprint(self):
        return frozenset(self.old_binding + self.new_terminal_pair)

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class JointAction:
    decision_time_s: float
    absolute_time_frame_id: str
    decision_root_sha256: str
    joint_proposal_set_sha256: str
    members: tuple

    def __post_init__(self):
        object.__setattr__(self, "members", tuple(self.members))
        if not math.isfinite(self.decision_time_s) or self.decision_time_s < 0:
            raise ValueError("INVALID_DECISION_TIME")
        if not self.absolute_time_frame_id:
            raise ValueError("MISSING_ABSOLUTE_TIME_FRAME_ID")
        for digest in (self.decision_root_sha256, self.joint_proposal_set_sha256):
            if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise ValueError("INVALID_CANONICAL_SHA256")
        if not all(isinstance(m, BatchReplaceMember) for m in self.members):
            raise TypeError("BATCH_REPLACE_MEMBER_REQUIRED")
        indices = tuple(m.canonical_index for m in self.members)
        if indices != tuple(sorted(set(indices))):
            raise ValueError("MEMBERS_MUST_HAVE_STRICTLY_INCREASING_CANONICAL_INDICES")
        if len({m.member_id for m in self.members}) != len(self.members):
            raise ValueError("DUPLICATE_MEMBER_ID")

    @property
    def kind(self):
        return "BATCH_REPLACE" if self.members else "HOLD"

    @property
    def batch_id(self):
        return "V2-" + canonical_sha256(self.identity_document())

    def identity_document(self):
        return {"schema": "f3_v2_joint_action_v1", "kind": self.kind,
                "decision_time_s": self.decision_time_s,
                "absolute_time_frame_id": self.absolute_time_frame_id,
                "decision_root_sha256": self.decision_root_sha256,
                "members": [m.to_dict() for m in self.members]}

    def to_dict(self):
        return {**self.identity_document(), "batch_id": self.batch_id,
                "joint_proposal_set_sha256": self.joint_proposal_set_sha256,
                "ordered_member_ids": [m.member_id for m in self.members]}
