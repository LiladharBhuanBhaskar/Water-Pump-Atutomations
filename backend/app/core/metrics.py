"""
HydraControl — Pure Python Prometheus Metrics & System Observability Service (Phase 24.2 & Phase 24.4).
Exposes standardized Prometheus text metrics for HTTP requests, WebSocket connections,
MQTT throughput, motor commands, safety trips, and database connection pool status.
"""

import time
from typing import Dict, Tuple, List, Optional
from fastapi import Response

CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"


class Counter:
    def __init__(self, name: str, documentation: str, labelnames: Optional[List[str]] = None):
        self.name = name
        self.documentation = documentation
        self.labelnames = labelnames or []
        self._values: Dict[Tuple[str, ...], float] = {}

    def labels(self, **kwargs) -> "Counter":
        key = tuple(str(kwargs.get(k, "")) for k in self.labelnames)
        if key not in self._values:
            self._values[key] = 0.0
        return _BoundMetric(self, key)

    def inc(self, amount: float = 1.0):
        key = ()
        self._values[key] = self._values.get(key, 0.0) + amount


class Gauge:
    def __init__(self, name: str, documentation: str, labelnames: Optional[List[str]] = None):
        self.name = name
        self.documentation = documentation
        self.labelnames = labelnames or []
        self._values: Dict[Tuple[str, ...], float] = {}

    def labels(self, **kwargs) -> "Gauge":
        key = tuple(str(kwargs.get(k, "")) for k in self.labelnames)
        if key not in self._values:
            self._values[key] = 0.0
        return _BoundMetric(self, key)

    def set(self, value: float):
        key = ()
        self._values[key] = float(value)

    def inc(self, amount: float = 1.0):
        key = ()
        self._values[key] = self._values.get(key, 0.0) + amount

    def dec(self, amount: float = 1.0):
        key = ()
        self._values[key] = self._values.get(key, 0.0) - amount


class Histogram:
    def __init__(self, name: str, documentation: str, labelnames: Optional[List[str]] = None, buckets=None):
        self.name = name
        self.documentation = documentation
        self.labelnames = labelnames or []
        self.buckets = buckets or (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
        self._counts: Dict[Tuple[str, ...], float] = {}
        self._sums: Dict[Tuple[str, ...], float] = {}

    def labels(self, **kwargs) -> "Histogram":
        key = tuple(str(kwargs.get(k, "")) for k in self.labelnames)
        if key not in self._counts:
            self._counts[key] = 0.0
            self._sums[key] = 0.0
        return _BoundMetric(self, key)

    def observe(self, amount: float):
        key = ()
        self._counts[key] = self._counts.get(key, 0.0) + 1.0
        self._sums[key] = self._sums.get(key, 0.0) + amount


class _BoundMetric:
    def __init__(self, parent, key: Tuple[str, ...]):
        self.parent = parent
        self.key = key

    def inc(self, amount: float = 1.0):
        self.parent._values[self.key] = self.parent._values.get(self.key, 0.0) + amount

    def dec(self, amount: float = 1.0):
        self.parent._values[self.key] = self.parent._values.get(self.key, 0.0) - amount

    def set(self, value: float):
        self.parent._values[self.key] = float(value)

    def observe(self, amount: float):
        self.parent._counts[self.key] = self.parent._counts.get(self.key, 0.0) + 1.0
        self.parent._sums[self.key] = self.parent._sums.get(self.key, 0.0) + amount


# 1. HTTP Metrics
http_requests_total = Counter(
    "hydracontrol_http_requests_total",
    "Total HTTP requests received by endpoint and status code",
    ["method", "endpoint", "status_code"],
)

http_request_duration_seconds = Histogram(
    "hydracontrol_http_request_duration_seconds",
    "HTTP request latency histogram in seconds",
    ["method", "endpoint"],
)

# 2. WebSocket Metrics
active_websocket_connections = Gauge(
    "hydracontrol_active_websocket_connections",
    "Current active WebSocket client connections",
)

websocket_events_broadcast_total = Counter(
    "hydracontrol_websocket_events_broadcast_total",
    "Total WebSocket events broadcast across channels",
    ["event_type"],
)

# 3. MQTT & Device Metrics
mqtt_messages_processed_total = Counter(
    "hydracontrol_mqtt_messages_processed_total",
    "Total inbound MQTT messages processed",
    ["topic_type", "status"],
)

mqtt_connection_status = Gauge(
    "hydracontrol_mqtt_connection_status",
    "Current MQTT broker connection status (1=Connected, 0=Disconnected)",
)

# 4. Motor & Safety Metrics
motor_commands_dispatched_total = Counter(
    "hydracontrol_motor_commands_dispatched_total",
    "Total motor commands dispatched",
    ["command_type", "status"],
)

safety_trips_total = Counter(
    "hydracontrol_safety_trips_total",
    "Total safety trips triggered by type",
    ["trip_type"],
)

# 5. Database Connection Pool Metrics
db_pool_size = Gauge(
    "hydracontrol_db_pool_size",
    "Configured SQLAlchemy connection pool size",
)

db_pool_checked_out = Gauge(
    "hydracontrol_db_pool_checked_out",
    "Currently checked-out database connections",
)

_ALL_METRICS = [
    http_requests_total,
    http_request_duration_seconds,
    active_websocket_connections,
    websocket_events_broadcast_total,
    mqtt_messages_processed_total,
    mqtt_connection_status,
    motor_commands_dispatched_total,
    safety_trips_total,
    db_pool_size,
    db_pool_checked_out,
]


def generate_latest() -> bytes:
    """Renders all registered metrics into Prometheus exposition text format."""
    lines = []
    for m in _ALL_METRICS:
        metric_type = "counter" if isinstance(m, Counter) else "gauge" if isinstance(m, Gauge) else "histogram"
        lines.append(f"# HELP {m.name} {m.documentation}")
        lines.append(f"# TYPE {m.name} {metric_type}")

        if isinstance(m, (Counter, Gauge)):
            if not m._values:
                lines.append(f"{m.name} 0.0")
            else:
                for labels, val in m._values.items():
                    if labels and m.labelnames:
                        label_str = ",".join(f'{k}="{v}"' for k, v in zip(m.labelnames, labels))
                        lines.append(f"{m.name}{{{label_str}}} {val}")
                    else:
                        lines.append(f"{m.name} {val}")
        elif isinstance(m, Histogram):
            if not m._counts:
                lines.append(f"{m.name}_count 0.0")
                lines.append(f"{m.name}_sum 0.0")
            else:
                for labels, count in m._counts.items():
                    total_sum = m._sums.get(labels, 0.0)
                    if labels and m.labelnames:
                        label_str = ",".join(f'{k}="{v}"' for k, v in zip(m.labelnames, labels))
                        lines.append(f"{m.name}_count{{{label_str}}} {count}")
                        lines.append(f"{m.name}_sum{{{label_str}}} {total_sum}")
                    else:
                        lines.append(f"{m.name}_count {count}")
                        lines.append(f"{m.name}_sum {total_sum}")

    return ("\n".join(lines) + "\n").encode("utf-8")


def get_prometheus_metrics_response() -> Response:
    """Renders Prometheus formatted metric scrape output."""
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
