"""Reuse the existing E2 current-state routing adapter and D2 service kernel."""
from ..gate_e2_experiments import E2TransitionEngine
from .service_adapter import BatchNetworkServiceEngine


class NaturalGeometryBatchEngine(BatchNetworkServiceEngine,E2TransitionEngine):
    """MRO reuses E2 load-aware update, without reimplementing routing/service."""
    pass
