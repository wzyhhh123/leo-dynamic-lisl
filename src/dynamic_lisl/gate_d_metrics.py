"""Stable Gate D machine-readable metric names and helpers."""

METRIC_FIELDS = (
    "mean_bit_delay_s", "delivered_bits", "delivery_ratio",
    "residual_backlog_bits", "mean_queue_bits", "max_queue_bits",
    "link_utilization", "traffic_weighted_hop_count", "route_change_count",
    "active_dynamic_link_count", "switch_count", "BBM_count", "MBB_count",
    "outage_duration", "partition_node_time", "runtime",
)


def empty_transition_metrics(active_dynamic_link_count=0):
    return {
        "route_change_count": 0,
        "active_dynamic_link_count": int(active_dynamic_link_count),
        "switch_count": 0,
        "BBM_count": 0,
        "MBB_count": 0,
        "outage_duration": 0.0,
        "partition_node_time": 0.0,
    }
