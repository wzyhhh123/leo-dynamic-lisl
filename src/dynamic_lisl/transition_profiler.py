"""Gate C3: dry-run Gate B events and profile active/admit connectivity."""
from __future__ import annotations

from copy import deepcopy


def _edge(a, b):
    return tuple(sorted((a, b)))


def graph_components(nodes, edges):
    adjacency = {node: set() for node in nodes}
    for a, b in edges:
        if a not in adjacency or b not in adjacency:
            raise ValueError("Graph edge outside scenario")
        adjacency[a].add(b)
        adjacency[b].add(a)
    components = []
    unseen = set(nodes)
    while unseen:
        seed = min(unseen)
        stack = [seed]
        component = set()
        while stack:
            node = stack.pop()
            if node in component:
                continue
            component.add(node)
            unseen.discard(node)
            stack.extend(adjacency[node] - component)
        components.append(tuple(sorted(component)))
    return tuple(sorted(components, key=lambda x: (-len(x), x)))


def graph_state(executor, fixed_edges):
    fixed = {_edge(*x) for x in fixed_edges}
    active = set(fixed)
    admit = set(fixed)
    for link in executor.links.values():
        edge = _edge(link.endpoints[0][0], link.endpoints[1][0])
        active.add(edge)
        if not link.draining:
            admit.add(edge)
    nodes = tuple(sorted(executor.satellite_ids))
    active_components = graph_components(nodes, active)
    admit_components = graph_components(nodes, admit)
    return dict(active_edges=sorted(active), admit_edges=sorted(admit),
                active_components=active_components, admit_components=admit_components,
                active_connected=len(active_components) == 1,
                admit_connected=len(admit_components) == 1)


def _profile_transition(executor, commands, fixed_edges, horizon_s,
                        clone_factory):
    """Run the real Gate B executor clone and observe only atomic event groups."""
    trial = clone_factory(executor)
    log_start = len(trial.log)
    try:
        trial.submit(commands)
    except (ValueError, AssertionError) as error:
        return dict(executable=False, reason="PHYSICAL_INFEASIBLE", detail=str(error))

    if horizon_s is None:
        # Caller should normally supply the next decision/prediction horizon.
        # Default covers all currently scheduled events, including known expiries.
        horizon_s = max([trial.now, *(event[0] for event in trial.events)])
    if horizon_s < trial.now:
        raise ValueError("Profiler horizon precedes current time")

    samples = []
    def sample(time_s, event_names):
        state = graph_state(trial, fixed_edges)
        samples.append(dict(time_s=time_s, events=event_names, **state))
    sample(trial.now, [x["event"] for x in trial.log[log_start:]])
    while trial.events and trial.events[0][0] <= horizon_s:
        event_time = trial.events[0][0]
        before = len(trial.log)
        trial.advance(event_time)
        sample(event_time, [x["event"] for x in trial.log[before:]])
    if samples[-1]["time_s"] < horizon_s:
        trial.advance(horizon_s)
        sample(horizon_s, [])

    # Collapse duplicate states at t=now created by zero-time events.
    collapsed = []
    for item in samples:
        if collapsed and item["time_s"] == collapsed[-1]["time_s"]:
            item["events"] = collapsed[-1]["events"] + item["events"]
            collapsed[-1] = item
        else:
            collapsed.append(item)
    samples = collapsed

    episodes = []
    open_episode = None
    affected = set()
    max_components = 1
    active_disconnect = admit_disconnect = False
    for index, state in enumerate(samples):
        disconnected = not state["active_connected"] or not state["admit_connected"]
        active_disconnect |= not state["active_connected"]
        admit_disconnect |= not state["admit_connected"]
        max_components = max(max_components, len(state["active_components"]),
                             len(state["admit_components"]))
        if disconnected:
            for components in (state["active_components"], state["admit_components"]):
                for component in components[1:]:
                    affected.update(component)
            if open_episode is None:
                open_episode = dict(start_s=state["time_s"],
                                    active_disconnected=not state["active_connected"],
                                    admit_disconnected=not state["admit_connected"])
            else:
                open_episode["active_disconnected"] |= not state["active_connected"]
                open_episode["admit_disconnected"] |= not state["admit_connected"]
        elif open_episode is not None:
            open_episode.update(end_s=state["time_s"], duration_s=state["time_s"]-open_episode["start_s"],
                                recovery_event=state["events"], recovery_plan_exists=True)
            episodes.append(open_episode)
            open_episode = None
    if open_episode is not None:
        open_episode.update(end_s=None, duration_s=None, recovery_event=None,
                            recovery_plan_exists=False)
        episodes.append(open_episode)

    partition = bool(episodes)
    recoverable = partition and all(x["recovery_plan_exists"] for x in episodes)
    if not partition:
        classification = "no_partition"
    elif recoverable:
        classification = "temporary_recoverable_partition"
    else:
        classification = "unrecoverable_partition"
    completed = [x["duration_s"] for x in episodes if x["duration_s"] is not None]
    return dict(
        executable=True, partition_occurs=partition,
        first_partition_time=(episodes[0]["start_s"] if episodes else None),
        recovery_time=(episodes[-1]["end_s"] if recoverable else None),
        outage_duration=(max(completed) if recoverable and completed else (0.0 if not partition else None)),
        max_component_count=max_components, affected_node_count=len(affected),
        affected_node_ids=sorted(affected), active_graph_disconnect=active_disconnect,
        admit_graph_disconnect=admit_disconnect,
        recovery_event=(episodes[-1]["recovery_event"] if recoverable else None),
        recovery_plan_exists=(not partition or recoverable), classification=classification,
        episodes=episodes, timeline=samples, horizon_s=horizon_s,
        natural_expiry_disconnect=any(x["event"] == "LINK_DOWN" and x["details"].get("reason") == "LINK_EXPIRE" for x in trial.log[log_start:]),
        final_executor=trial, transition_log=trial.log[log_start:])


def profile_transition(executor, commands, fixed_edges=(), horizon_s=None):
    """Profile from an exact live-state clone without historical audit records."""
    return _profile_transition(
        executor, commands, fixed_edges, horizon_s,
        lambda value: value.clone_for_counterfactual())


def profile_transition_legacy_reference(executor, commands, fixed_edges=(),
                                        horizon_s=None):
    """Test-only pre-Phase-1 recursive-copy reference path."""
    return _profile_transition(
        executor, commands, fixed_edges, horizon_s, deepcopy)


def validate_reference_initialization(nodes, fixed_edges, dynamic_terminal_pairs):
    dynamic_edges = {_edge(a[0], b[0]) for a, b in dynamic_terminal_pairs}
    components = graph_components(tuple(nodes), set(map(lambda x: _edge(*x), fixed_edges)) | dynamic_edges)
    return dict(connected=len(components) == 1, components=components)

