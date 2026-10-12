"""Exact B4 clones sharing only audited, append-only historical records.

History containers remain independent. Existing records are read-only by
convention, just like TerminalExecutor's transaction-clone log prefix. Do not
edit old records through a branch. Live state and unrecognized fields retain
ordinary deepcopy semantics, including alias relationships between episodes.
"""
from copy import deepcopy


APPEND_ONLY_HISTORY_FIELDS = (
    "timeline", "route_changes", "route_state_events",
    "terminal_event_sequence", "propagation_closure_events",
)


def clone_rollout_engine(engine):
    """Preserve full history without recursively copying historical payloads.

Do not share transition_episodes: pending-clearance entries are subsequently
mutated. Do not share action_results or graph_event_sequence: their nested
objects may alias proposal/graph state. No geometry/router/provider sharing is
introduced here. One memo preserves all remaining deepcopy relationships.
    """
    memo = {}
    for name in APPEND_ONLY_HISTORY_FIELDS:
        for record in getattr(engine, name):
            memo[id(record)] = record
    for record in engine.executor.log:
        memo[id(record)] = record
    return deepcopy(engine, memo)
