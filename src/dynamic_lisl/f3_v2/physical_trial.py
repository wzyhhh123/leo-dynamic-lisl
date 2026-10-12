"""Exact history-free Gate C input, restricted to the audited original types."""
from ..terminal_executor import TerminalExecutor
from ..terminal_pair_intervals import TerminalPairCatalog
from ..gate_c_simplified_feasibility import TerminalPairPhysicalFeasibility


def physical_trial_executor(physical_layer,executor,*,enabled):
    if (enabled and type(executor) is TerminalExecutor and
        type(physical_layer) is TerminalPairPhysicalFeasibility and physical_layer.hardware is None and
        type(physical_layer.catalog) is TerminalPairCatalog and
        getattr(physical_layer.evaluate,'__func__',None) is TerminalPairPhysicalFeasibility.evaluate and
        getattr(physical_layer.catalog.connect_command,'__func__',None) is TerminalPairCatalog.connect_command):
        return executor.clone_for_counterfactual()
    # Unproved extensions may read executor.log. Never shortcut their contract.
    return executor
