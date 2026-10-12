"""Engineering-only exact B4 root-branch scheduling in Windows spawn workers.

No production controller imports this module. Each task decodes a separate
decision-root engine. The only process-global object is the frozen TLE model;
all mutable network/terminal/queue/route/delay-cache state is task-local.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import hashlib
import os
import pickle
import queue
import time

from .sgp4_model import Sgp4Model
from .rollout_evaluator import ExactRootActionRolloutEvaluator


_WORKER_MODEL = None
_ASSET_TOKEN = None
_LIVENESS_READY = None
_LIVENESS_RELEASE = None


def _asset_token(folder):
    folder = Path(folder)
    digest = hashlib.sha256()
    for name in ("manifest.json", "hashes.json", "constellation.tle"):
        digest.update((folder / name).read_bytes())
    return digest.hexdigest()


def init_worker(folder, expected_token, ready_queue, release_event):
    global _WORKER_MODEL, _ASSET_TOKEN, _LIVENESS_READY, _LIVENESS_RELEASE
    if _asset_token(folder) != expected_token:
        raise AssertionError("B4_WORKER_TLE_ASSET_HASH_MISMATCH")
    _WORKER_MODEL = Sgp4Model.load(folder)
    _ASSET_TOKEN = expected_token
    _LIVENESS_READY = ready_queue
    _LIVENESS_RELEASE = release_event


class _RootPickler(pickle.Pickler):
    def __init__(self, stream, token):
        super().__init__(stream, protocol=pickle.HIGHEST_PROTOCOL)
        self.token = token

    def persistent_id(self, obj):
        if isinstance(obj, Sgp4Model):
            return ("FROZEN_TLE_MODEL", self.token)
        return None


class _RootUnpickler(pickle.Unpickler):
    def persistent_load(self, pid):
        if pid != ("FROZEN_TLE_MODEL", _ASSET_TOKEN) or _WORKER_MODEL is None:
            raise pickle.UnpicklingError("B4_WORKER_TLE_TOKEN_MISMATCH")
        return _WORKER_MODEL


def encode_root(engine, token):
    stream = BytesIO()
    _RootPickler(stream, token).dump(engine)
    return stream.getvalue()


def decode_root(payload):
    return _RootUnpickler(BytesIO(payload)).load()


def branch_evidence(branch):
    return {
        "canonical_state": branch.canonical_state(),
        "terminal": branch.executor.snapshot(),
        "G_active": branch.graph["active_edges"],
        "G_admit": branch.graph["admit_edges"],
        "Q": branch.queues.snapshot(),
        "I": branch.in_flight.snapshot(),
        "D": dict(branch.delivered),
        "objective_by_commodity": dict(branch.objective_by_commodity),
        "terminal_event_sequence": list(branch.terminal_event_sequence),
        "transition_episodes": list(branch.transition_episodes),
        "action_results": list(branch.action_results),
    }


@dataclass(frozen=True)
class BranchTask:
    index: int
    root_blob: bytes
    physical_blob: bytes
    fixed_edges: tuple
    regime: str
    forecast: object
    proposal_record: object
    candidate_spec: object
    root_hash: str
    forecast_hash: str


def _worker_liveness(_):
    """Occupy a worker until the parent has observed every worker READY."""
    import psutil
    pid = os.getpid()
    ready = {"pid": pid, "rss_bytes": psutil.Process().memory_info().rss}
    _LIVENESS_READY.put(ready)
    if not _LIVENESS_RELEASE.wait(timeout=120):
        raise TimeoutError("B4_WORKER_LIVENESS_RELEASE_TIMEOUT")
    return ready


def _worker_engineering_error():
    """Test that a worker exception reaches the parent unchanged."""
    raise RuntimeError("B4_ENGINEERING_EXCEPTION_PROPAGATION_PROBE")


def execute_task(task):
    """Return a transport blob so result deserialize time is separately timed."""
    import os
    import psutil
    start = time.perf_counter()
    root = decode_root(task.root_blob)
    physical = pickle.loads(task.physical_blob)
    decoded = time.perf_counter()
    before_hash = root.canonical_state_sha256()
    if before_hash != task.root_hash:
        raise AssertionError("B4_WORKER_ROOT_STATE_MISMATCH")
    evaluator = ExactRootActionRolloutEvaluator(
        root, physical, task.fixed_edges, task.regime)
    captured = []
    finish = evaluator._finish

    def capture(*args, **kwargs):
        result = finish(*args, **kwargs)
        captured.append(branch_evidence(args[0]))
        return result

    evaluator._finish = capture
    if task.proposal_record is None:
        result = evaluator.evaluate_hold(
            task.forecast, root_hash=task.root_hash,
            forecast_hash=task.forecast_hash)
    else:
        result = evaluator.evaluate_candidate(
            task.forecast, task.proposal_record, task.candidate_spec,
            root_hash=task.root_hash, forecast_hash=task.forecast_hash)
    completed = time.perf_counter()
    if root.canonical_state_sha256() != before_hash:
        raise AssertionError("B4_WORKER_ROOT_MUTATED")
    assert len(captured) == 1
    rss = psutil.Process().memory_info().rss
    value = {
        "index": task.index,
        "result": result,
        "evidence": captured[0],
        "worker_pid": os.getpid(),
        "worker_decode_s": decoded-start,
        "worker_compute_s": completed-decoded,
        "worker_rss_bytes": rss,
    }
    encoded_start = time.perf_counter()
    payload = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
    return payload, time.perf_counter()-encoded_start, len(payload)


class ParallelB4BranchPool:
    """Persistent pool; independent full root bytes supplied for every task."""

    def __init__(self, workers, tle_folder):
        if workers not in (1, 2, 4, 8):
            raise ValueError("B4_ENGINEERING_WORKER_GRID_ONLY")
        self.workers = workers
        self.tle_folder = Path(tle_folder)
        self.token = _asset_token(tle_folder)
        self.pool = None

    def __enter__(self):
        from multiprocessing import get_context
        context = get_context("spawn")
        self._ready_queue = context.Queue()
        self._release_event = context.Event()
        self.pool = ProcessPoolExecutor(
            max_workers=self.workers,
            mp_context=context,
            initializer=init_worker,
            initargs=(str(self.tle_folder), self.token,
                      self._ready_queue, self._release_event),
        )
        return self

    def __exit__(self, *_):
        self._release_event.set()
        try:
            self.pool.shutdown(wait=True, cancel_futures=False)
        finally:
            self.pool = None
            self._ready_queue.close()
            self._ready_queue.join_thread()

    def warm(self):
        futures = [self.pool.submit(_worker_liveness, i)
                   for i in range(self.workers)]
        ready = []
        deadline = time.monotonic() + 60
        try:
            while len(ready) < self.workers:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("B4_WORKER_LIVENESS_READY_TIMEOUT")
                try:
                    ready.append(self._ready_queue.get(timeout=min(1, remaining)))
                except queue.Empty:
                    for future in futures:
                        if future.done():
                            future.result()  # Surface worker startup exceptions.
            if len({row["pid"] for row in ready}) != self.workers:
                raise AssertionError("WORKER_CONCURRENT_OCCUPANCY_PID_MISMATCH")
        finally:
            self._release_event.set()
        completed = [future.result(timeout=60) for future in futures]
        if sorted(row["pid"] for row in completed) != sorted(row["pid"] for row in ready):
            raise AssertionError("WORKER_LIVENESS_COMPLETION_MISMATCH")
        return ready

    def submit(self, task):
        return self.pool.submit(execute_task, task)
