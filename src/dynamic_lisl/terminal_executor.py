"""Gate B only: deterministic bilateral dynamic-terminal lifecycle.

No traffic, routing, geometry propagation, hardware slew or network safety policy.
Synthetic TX completion includes reception of the last signal at the peer.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict, field
from copy import copy, deepcopy
import heapq
import math

IDLE, DRAINING, RETARGETING, ACQUIRING, ACTIVE = (
    'IDLE', 'DRAINING', 'RETARGETING', 'ACQUIRING', 'ACTIVE')


def pair(a, b):
    a, b = tuple(a), tuple(b)
    if a == b or a[0] == b[0]:
        raise ValueError('A dynamic link requires two different satellites')
    return tuple(sorted((a, b)))


@dataclass
class Terminal:
    terminal_id: tuple
    phase: str = IDLE
    current_peer: tuple | None = None
    target_peer: tuple | None = None
    reservation_id: str | None = None
    event_version: int = 0
    orientation: tuple = (1.0, 0.0, 0.0)
    orientation_frame: str = 'SYNTHETIC_TERMINAL_LOCAL'
    terminal_free_time: float = 0.0
    retarget_start: float | None = None
    retarget_end: float | None = None
    acquisition_start: float | None = None
    acquisition_end: float | None = None
    active_link_start: float | None = None
    visibility_end: float | None = None


@dataclass(frozen=True)
class Connect:
    a: tuple
    b: tuple
    visibility_end: float
    retarget_a: float = 1.0
    retarget_b: float = 1.0
    acquisition: float = 1.0
    orientation_a: tuple = (0.0, 1.0, 0.0)
    orientation_b: tuple = (0.0, 1.0, 0.0)
    # MBB: release these exact old physical bindings only AFTER new LINK_UP.
    release_after: tuple = ()


@dataclass(frozen=True)
class Keep:
    a: tuple
    b: tuple


@dataclass(frozen=True)
class Disconnect:
    a: tuple
    b: tuple


@dataclass
class Link:
    link_id: str
    endpoints: tuple
    start: float
    visibility_end: float
    draining: bool = False
    tx_end: dict = field(default_factory=dict)
    release_owner: str | None = None


@dataclass
class Reservation:
    reservation_id: str
    endpoints: tuple
    versions: tuple
    durations: tuple
    orientations: tuple
    acquisition: float
    visibility_end: float
    release_after: tuple
    acquiring: bool = False


class TerminalExecutor:
    """Two D terminals per satellite; immutable fixed-port inventory is separate.

    Public mutators run due events and assert invariants. submit() is all-or-none,
    including command rejection: live state, events, counters and log do not change.
    Events at equal times: expiry, TX completion, LINK_DOWN, retarget, LINK_READY.
    """
    def __init__(self, satellite_ids):
        sats = tuple(satellite_ids)
        if not sats or len(set(sats)) != len(sats) or not all(isinstance(x, str) for x in sats):
            raise ValueError('Unique nonempty satellite IDs required')
        self.satellite_ids = sats
        self.terminals = {(s, d): Terminal((s, d)) for s in sats for d in ('D1', 'D2')}
        self.fixed_ports = frozenset((s, d) for s in sats for d in ('FWD_INTRA', 'BWD_INTRA'))
        self.now = 0.0
        self.links = {}
        self.reservations = {}
        self.events = []
        self.log = []
        self._sequence = 0
        self._reservation_sequence = 0
        self.invariant_checks = 0
        self.assert_invariants()

    _CLONE_AUDITED_FIELDS = frozenset({
        "satellite_ids", "terminals", "fixed_ports", "now", "links",
        "reservations", "events", "log", "_sequence",
        "_reservation_sequence", "invariant_checks",
    })

    def _exact_structural_clone(self, include_history):
        """Clone all transition-live state without recursively copying history.

        Terminal-log records are append-only after creation. Transaction clones
        keep an independent list containing the same immutable-by-convention
        historical records; counterfactual profiler clones start with no history.
        Any future executor field requires an explicit clone audit.
        """
        observed = frozenset(self.__dict__)
        if observed != self._CLONE_AUDITED_FIELDS:
            missing = sorted(self._CLONE_AUDITED_FIELDS-observed)
            extra = sorted(observed-self._CLONE_AUDITED_FIELDS)
            raise AssertionError(
                f"TERMINAL_EXECUTOR_CLONE_AUDIT_REQUIRED:"
                f"missing={missing}:extra={extra}")
        clone = type(self).__new__(type(self))
        clone.satellite_ids = self.satellite_ids
        clone.terminals = {key: copy(value)
                           for key, value in self.terminals.items()}
        clone.fixed_ports = self.fixed_ports
        clone.now = self.now
        clone.links = {}
        for key, value in self.links.items():
            cloned_link = copy(value)
            cloned_link.tx_end = dict(value.tx_end)
            clone.links[key] = cloned_link
        clone.reservations = {key: copy(value)
                              for key, value in self.reservations.items()}
        # Event tuples and every scheduled payload are immutable value objects.
        clone.events = list(self.events)
        # Existing log records are append-only; only the list itself is mutated.
        clone.log = list(self.log) if include_history else []
        clone._sequence = self._sequence
        clone._reservation_sequence = self._reservation_sequence
        clone.invariant_checks = self.invariant_checks
        return clone

    def clone_for_transaction(self):
        """Exact atomic-submit clone retaining the full append-only history."""
        return self._exact_structural_clone(include_history=True)

    def clone_for_counterfactual(self):
        """Exact live-state clone whose log contains only new dry-run events."""
        return self._exact_structural_clone(include_history=False)

    def snapshot(self):
        return dict(time=self.now,
                    terminals=[asdict(t) for _, t in sorted(self.terminals.items())],
                    links=[dict(link_id=l.link_id, endpoints=l.endpoints, start=l.start,
                                visibility_end=l.visibility_end, draining=l.draining,
                                tx_end=sorted(l.tx_end.items()), release_owner=l.release_owner)
                           for _, l in sorted(self.links.items())],
                    reservations=[asdict(r) for _, r in sorted(self.reservations.items())],
                    fixed_ports=sorted(self.fixed_ports), events=sorted(self.events),
                    sequence=self._sequence, reservation_sequence=self._reservation_sequence)

    def _log(self, event_name, **details):
        self.log.append(dict(time=self.now, event=event_name, details=details,
                             terminals=[asdict(t) for _, t in sorted(self.terminals.items())]))

    def _schedule(self, time, priority, kind, payload):
        if not math.isfinite(time) or time < self.now:
            raise ValueError('Invalid event time')
        self._sequence += 1
        heapq.heappush(self.events, (time, priority, self._sequence, kind, payload))

    def _ends(self, a, b):
        ends = pair(a, b)
        if any(e not in self.terminals for e in ends):
            raise ValueError('Unknown dynamic terminal (fixed ports cannot be borrowed)')
        return ends

    def _link(self, ends):
        return next((l for l in self.links.values() if l.endpoints == ends), None)

    def _commit_commands_on_trial(self, commands, trial):
        commands = tuple(commands)
        for cmd in commands:
            if isinstance(cmd, Connect):
                trial._connect(cmd)
            elif isinstance(cmd, Keep):
                l = trial._link(trial._ends(cmd.a, cmd.b))
                if l is None or l.draining:
                    raise ValueError('KEEP requires the exact active terminal pair')
                trial._log('KEEP', link_id=l.link_id)
            elif isinstance(cmd, Disconnect):
                l = trial._link(trial._ends(cmd.a, cmd.b))
                if l is None or l.draining or l.release_owner:
                    raise ValueError('DISCONNECT requires an unlocked active link')
                trial._drain(l)
            else:
                raise ValueError('Unknown command')
            trial.assert_invariants()
        trial.advance(trial.now)
        trial._log('BATCH_COMMIT', command_count=len(commands), commands=[
            dict(type=type(c).__name__, **asdict(c)) for c in commands])
        self.__dict__.update(trial.__dict__)

    def submit(self, commands):
        self._commit_commands_on_trial(commands, self.clone_for_transaction())

    def submit_legacy_reference(self, commands):
        """Test-only reference for pre-Phase-1 recursive-copy semantics."""
        self._commit_commands_on_trial(commands, deepcopy(self))

    def _connect(self, cmd):
        ends = self._ends(cmd.a, cmd.b)
        ts = [self.terminals[e] for e in ends]
        if any(t.phase not in (IDLE, ACTIVE) or t.reservation_id for t in ts):
            raise ValueError('Terminal busy or reserved; no setup retargeting')
        if self._link(ends):
            raise ValueError('Use KEEP for an existing terminal pair')
        durations = {tuple(cmd.a): cmd.retarget_a, tuple(cmd.b): cmd.retarget_b}
        orientations = {tuple(cmd.a): tuple(cmd.orientation_a), tuple(cmd.b): tuple(cmd.orientation_b)}
        if any(not math.isfinite(x) or x < 0 for x in (*durations.values(), cmd.acquisition)):
            raise ValueError('Invalid synthetic setup duration')
        for v in orientations.values():
            if len(v) != 3 or any(not math.isfinite(x) for x in v) or abs(sum(x*x for x in v)-1) > 1e-9:
                raise ValueError('Orientation must be a finite synthetic unit vector')
        if not math.isfinite(cmd.visibility_end):
            raise ValueError('Finite visibility end required')
        satpair = {ends[0][0], ends[1][0]}
        if any({r.endpoints[0][0], r.endpoints[1][0]} == satpair for r in self.reservations.values()):
            raise ValueError('Parallel pending satellite-pair links prohibited')
        same_sat = [l for l in self.links.values() if {e[0] for e in l.endpoints} == satpair]
        releases = tuple(self._ends(*x) for x in cmd.release_after)
        if len(set(releases)) != len(releases):
            raise ValueError('Duplicate MBB release dependency')
        if releases and any(t.phase != IDLE or t.current_peer is not None for t in ts):
            raise ValueError('MBB requires both selected terminals truly idle')
        release_links = [self._link(x) for x in releases]
        if any(l is None or l.draining or l.release_owner for l in release_links):
            raise ValueError('MBB release dependency unavailable')
        if any(l in same_sat for l in release_links):
            raise ValueError('MBB cannot create parallel links to the same satellite')
        # Same peer / different terminals is new setup; drain old pair first.
        old = {l.link_id: l for l in self.links.values()
               if any(e in ends for e in l.endpoints) or l in same_sat}
        if any(l.draining or l.release_owner for l in old.values()):
            raise ValueError('Old binding is already committed')
        if releases and old:
            raise ValueError('MBB cannot hide an occupied or duplicate old binding')
        frees = {e: self.now for e in ends}
        for l in old.values():
            free = max([self.now, *l.tx_end.values()])
            for e in ends:
                # A same-peer replacement must wait for the entire old link.
                if e in l.endpoints or l in same_sat:
                    frees[e] = max(frees[e], free)
        ready = max(frees[e] + durations[e] for e in ends) + cmd.acquisition
        if not ready < cmd.visibility_end:
            raise ValueError('LINK_READY must strictly precede visibility end')
        self._reservation_sequence += 1
        rid = f'R{self._reservation_sequence}'
        for t, other in zip(ts, reversed(ends)):
            t.event_version += 1
            t.target_peer = other
            t.reservation_id = rid
            t.terminal_free_time = frees[t.terminal_id]
            t.visibility_end = cmd.visibility_end
            t.retarget_start = t.retarget_end = None
            t.acquisition_start = t.acquisition_end = None
        r = Reservation(rid, ends, tuple(t.event_version for t in ts),
                        tuple(durations[e] for e in ends), tuple(orientations[e] for e in ends),
                        cmd.acquisition, cmd.visibility_end, releases)
        self.reservations[rid] = r
        for l in release_links:
            l.release_owner = rid
        self._log('RESERVE_BOTH', reservation_id=rid, endpoints=ends, predicted_ready=ready)
        for l in old.values():
            self._drain(l)
        # Idle same-peer replacement endpoints must not overtake old LINK_DOWN.
        for e in ends:
            if self.terminals[e].current_peer is None:
                if same_sat:
                    self._schedule(frees[e], 3, 'START_RETARGET', (rid, r.versions, e))
                else:
                    self._start_retarget(r, e)
        self._schedule(cmd.visibility_end, 0, 'SETUP_EXPIRE', (rid, r.versions))

    def _drain(self, l):
        if l.draining:
            return
        l.draining = True
        free = max([self.now, *l.tx_end.values()])
        for e in l.endpoints:
            self.terminals[e].phase = DRAINING
            self.terminals[e].terminal_free_time = free
        self._log('DRAINING', link_id=l.link_id, drain_end=free)
        self._schedule(free, 2, 'LINK_DOWN', l.link_id)

    def _start_retarget(self, r, e):
        t = self.terminals[e]
        if t.current_peer is not None or t.phase != IDLE:
            return
        k = r.endpoints.index(e)
        t.phase = RETARGETING
        t.terminal_free_time = self.now
        t.retarget_start = self.now
        t.retarget_end = self.now + r.durations[k]
        self._schedule(t.retarget_end, 3, 'RETARGET_DONE', (r.reservation_id, r.versions, e))
        self._log('RETARGET_START', terminal=e, reservation_id=r.reservation_id)

    def _down(self, lid, reason):
        l = self.links.pop(lid, None)
        if l is None:
            self._log('STALE_EVENT', kind='LINK_DOWN', link_id=lid)
            return
        for e in l.endpoints:
            t = self.terminals[e]
            t.current_peer = None
            t.active_link_start = None
            t.phase = IDLE
            t.terminal_free_time = self.now
            if t.reservation_id is None:
                t.event_version += 1
                t.visibility_end = None
        self._log('LINK_DOWN', link_id=lid, reason=reason,
                  interrupted_tx=sum(end > self.now for end in l.tx_end.values()))
        for e in l.endpoints:
            t = self.terminals[e]
            if t.reservation_id:
                self._start_retarget(self.reservations[t.reservation_id], e)

    def _abort(self, r, reason):
        del self.reservations[r.reservation_id]
        for e in r.endpoints:
            t = self.terminals[e]
            t.event_version += 1
            t.reservation_id = t.target_peer = None
            if t.current_peer is None:
                t.phase = IDLE
                t.terminal_free_time = self.now
                t.visibility_end = None
            else:
                t.visibility_end = self._link(pair(e, t.current_peer)).visibility_end
        for l in self.links.values():
            if l.release_owner == r.reservation_id:
                l.release_owner = None
        self._log('ABORT', reservation_id=r.reservation_id, reason=reason)

    def expire_visibility(self, a, b):
        """Synthetic unexpected visibility loss now; no target cancellation API."""
        ends = self._ends(a, b)
        r = next((r for r in self.reservations.values() if r.endpoints == ends), None)
        l = self._link(ends)
        if r is None and l is None:
            raise ValueError('No binding or reservation to expire')
        if r:
            self._abort(r, 'VISIBILITY_LOST')
        if l:
            self._down(l.link_id, 'VISIBILITY_LOST')
        self.advance(self.now)

    def start_tx(self, source, completion_time):
        """Synthetic per-direction nonpreemptive TX, including last-bit reception."""
        source = tuple(source)
        if source not in self.terminals:
            raise ValueError('Not a dynamic terminal')
        t = self.terminals[source]
        if t.phase != ACTIVE:
            raise ValueError('New TX allowed only on ACTIVE, never DRAINING/setup')
        l = self._link(pair(source, t.current_peer))
        if not math.isfinite(completion_time) or not self.now < completion_time <= l.visibility_end:
            raise ValueError('TX completion outside visibility')
        if l.tx_end.get(source, self.now) > self.now:
            raise ValueError('This direction already has a nonpreemptive TX')
        l.tx_end[source] = completion_time
        for e in l.endpoints:
            self.terminals[e].terminal_free_time = max(l.tx_end.values())
        self._schedule(completion_time, 1, 'TX_DONE', (l.link_id, source, completion_time))
        self._log('TX_START', source=source, completion_time=completion_time)
        self.assert_invariants()

    def _valid_reservation(self, rid, versions):
        r = self.reservations.get(rid)
        return r if r and r.versions == versions and all(
            self.terminals[e].event_version == v and self.terminals[e].reservation_id == rid
            for e, v in zip(r.endpoints, versions)) else None

    def advance(self, until):
        if not math.isfinite(until) or until < self.now:
            raise ValueError('Time must be finite and monotonic')
        while self.events and self.events[0][0] <= until:
            time, _, _, kind, payload = heapq.heappop(self.events)
            self.now = time
            self._event(kind, payload)
            self.assert_invariants()
        self.now = until
        self.assert_invariants()

    def _event(self, kind, payload):
        if kind in ('LINK_DOWN', 'LINK_EXPIRE'):
            if payload not in self.links:
                self._log('STALE_EVENT', kind=kind)
            else:
                self._down(payload, kind)
            return
        if kind == 'TX_DONE':
            lid, source, end = payload
            l = self.links.get(lid)
            if l and l.tx_end.get(source) == end:
                del l.tx_end[source]
                self._log('TX_DONE', link_id=lid, source=source)
            else:
                self._log('STALE_EVENT', kind=kind)
            return
        rid, versions = payload[:2]
        r = self._valid_reservation(rid, versions)
        if not r:
            self._log('STALE_EVENT', kind=kind, reservation_id=rid)
            return
        if kind == 'SETUP_EXPIRE':
            self._abort(r, 'VISIBILITY_EXPIRED_BEFORE_READY')
        elif kind == 'START_RETARGET':
            self._start_retarget(r, payload[2])
        elif kind == 'RETARGET_DONE':
            e = payload[2]
            self.terminals[e].orientation = r.orientations[r.endpoints.index(e)]
            self._log('RETARGET_DONE', terminal=e, reservation_id=rid)
            ts = [self.terminals[e] for e in r.endpoints]
            if not r.acquiring and all(t.phase == RETARGETING and t.retarget_end <= self.now for t in ts):
                r.acquiring = True
                for t in ts:
                    t.phase = ACQUIRING
                    t.acquisition_start = self.now
                    t.acquisition_end = self.now + r.acquisition
                self._schedule(self.now + r.acquisition, 4, 'LINK_READY', (rid, r.versions))
                self._log('ACQUISITION_START', reservation_id=rid)
        elif kind == 'LINK_READY':
            if not r.acquiring or not self.now < r.visibility_end:
                self._abort(r, 'NOT_READY_OR_VISIBILITY_EXPIRED')
                return
            ts = [self.terminals[e] for e in r.endpoints]
            if not all(t.phase == ACQUIRING and t.acquisition_end <= self.now for t in ts):
                raise AssertionError('Non-bilateral LINK_READY')
            del self.reservations[rid]
            lid = 'L' + rid[1:]
            self.links[lid] = Link(lid, r.endpoints, self.now, r.visibility_end)
            for t, other in zip(ts, reversed(r.endpoints)):
                t.phase = ACTIVE
                t.current_peer = other
                t.target_peer = t.reservation_id = None
                t.active_link_start = self.now
                t.event_version += 1
                t.terminal_free_time = self.now
            self._log('LINK_UP', link_id=lid, endpoints=r.endpoints)
            self._schedule(r.visibility_end, 0, 'LINK_EXPIRE', lid)
            for oldpair in r.release_after:
                old = self._link(oldpair)
                # Old visibility may have ended naturally while setting up.
                if old:
                    if old.release_owner != rid:
                        raise AssertionError('Lost MBB release ownership')
                    old.release_owner = None
                    self._drain(old)
        else:
            raise AssertionError('Unknown event')

    def assert_invariants(self):
        expected = {(s, d) for s in self.satellite_ids for d in ('D1', 'D2')}
        assert set(self.terminals) == expected, 'Dynamic inventory changed'
        assert self.fixed_ports == frozenset((s, d) for s in self.satellite_ids for d in ('FWD_INTRA', 'BWD_INTRA'))
        used = set()
        satellite_pairs = set()
        for l in self.links.values():
            assert l.endpoints == pair(*l.endpoints)
            sp = tuple(sorted(e[0] for e in l.endpoints))
            assert sp not in satellite_pairs, 'Parallel physical satellite links'
            satellite_pairs.add(sp)
            for e, other in zip(l.endpoints, reversed(l.endpoints)):
                assert e not in used, 'Double terminal occupancy'
                used.add(e)
                t = self.terminals[e]
                assert t.current_peer == other
                assert t.phase == (DRAINING if l.draining else ACTIVE), 'Unilateral link phase'
                assert t.active_link_start == l.start
            assert l.release_owner is None or l.release_owner in self.reservations
        reserved = set()
        pending_pairs = set()
        for rid, r in self.reservations.items():
            sp = tuple(sorted(e[0] for e in r.endpoints))
            assert sp not in pending_pairs
            pending_pairs.add(sp)
            for e, other, version in zip(r.endpoints, reversed(r.endpoints), r.versions):
                t = self.terminals[e]
                assert e not in reserved, 'Double reservation'
                reserved.add(e)
                assert t.reservation_id == rid and t.target_peer == other
                assert t.event_version == version
                assert t.phase in (IDLE, DRAINING, RETARGETING, ACQUIRING)
            terminals = [self.terminals[e] for e in r.endpoints]
            assert r.acquiring == any(t.phase == ACQUIRING for t in terminals)
            if r.acquiring:
                assert all(t.phase == ACQUIRING for t in terminals), 'Unilateral acquisition'
                assert terminals[0].acquisition_start == terminals[1].acquisition_start
                assert terminals[0].acquisition_end == terminals[1].acquisition_end
            for l in self.links.values():
                if tuple(sorted(e[0] for e in l.endpoints)) == sp:
                    assert l.draining, 'Pending parallel satellite link'
        for e, t in self.terminals.items():
            assert t.phase in (IDLE, DRAINING, RETARGETING, ACQUIRING, ACTIVE)
            assert (t.current_peer is not None) == (e in used)
            assert (t.reservation_id is not None) == (e in reserved)
            assert (t.target_peer is not None) == (e in reserved)
            if t.phase in (RETARGETING, ACQUIRING):
                assert e in reserved and e not in used
            if t.phase == ACTIVE:
                assert e in used and e not in reserved
            if t.phase == DRAINING:
                assert e in used
            if t.phase == IDLE:
                assert e not in used
        self.invariant_checks += 1
