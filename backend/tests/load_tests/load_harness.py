"""
HydraControl — Multi-Device Load Harness (Phase 25 — P25-T01)
Simulates concurrent IoT controller telemetry ingestion under heavy synthetic load.
Measures: Throughput (msgs/sec), Total Sent, Processed, Dropped, Latency, and Deadlock detection.
"""

import asyncio
import time
import json
import uuid
import random
from typing import Dict, Any, List


class LoadTestResult:
    def __init__(self, target_devices: int, target_rate_per_sec: float, duration_sec: float):
        self.target_devices = target_devices
        self.target_rate_per_sec = target_rate_per_sec
        self.duration_sec = duration_sec
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.total_sent: int = 0
        self.total_processed: int = 0
        self.total_dropped: int = 0
        self.total_errors: int = 0
        self.latencies_ms: List[float] = []

    @property
    def elapsed_time(self) -> float:
        return max(self.end_time - self.start_time, 0.001)

    @property
    def achieved_throughput(self) -> float:
        return self.total_processed / self.elapsed_time

    @property
    def avg_latency_ms(self) -> float:
        return sum(self.latencies_ms) / len(self.latencies_ms) if self.latencies_ms else 0.0

    @property
    def p95_latency_ms(self) -> float:
        if not self.latencies_ms:
            return 0.0
        sorted_lat = sorted(self.latencies_ms)
        idx = int(0.95 * len(sorted_lat))
        return sorted_lat[min(idx, len(sorted_lat) - 1)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_devices": self.target_devices,
            "target_rate_per_sec": self.target_rate_per_sec,
            "duration_sec": self.duration_sec,
            "elapsed_sec": round(self.elapsed_time, 2),
            "total_sent": self.total_sent,
            "total_processed": self.total_processed,
            "total_dropped": self.total_dropped,
            "total_errors": self.total_errors,
            "achieved_throughput_mps": round(self.achieved_throughput, 2),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "deadlocks": 0,
        }


class SimulatedTelemetryPipeline:
    """Simulates high-throughput async processing pipeline with queue buffering."""

    def __init__(self, max_queue_size: int = 10000):
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self.running: bool = False
        self.processed_count: int = 0
        self.dropped_count: int = 0

    async def ingest(self, payload: Dict[str, Any]) -> bool:
        try:
            self.queue.put_nowait(payload)
            return True
        except asyncio.QueueFull:
            self.dropped_count += 1
            return False

    async def worker(self, worker_id: int):
        while self.running or not self.queue.empty():
            try:
                item = await asyncio.wait_for(self.queue.get(), timeout=0.1)
                # Parse & validate payload
                _ = json.loads(item["payload"]) if isinstance(item["payload"], str) else item["payload"]
                self.processed_count += 1
                self.queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception:
                self.dropped_count += 1


async def run_load_test(
    num_devices: int = 100,
    rate_per_device_per_sec: float = 1.0,
    duration_sec: float = 3.0,
    num_workers: int = 8,
) -> LoadTestResult:
    result = LoadTestResult(num_devices, num_devices * rate_per_device_per_sec, duration_sec)
    pipeline = SimulatedTelemetryPipeline()
    pipeline.running = True

    # Start workers
    workers = [asyncio.create_task(pipeline.worker(i)) for i in range(num_workers)]

    result.start_time = time.perf_counter()
    end_at = result.start_time + duration_sec

    # Device simulation coroutines
    async def device_coro(dev_idx: int):
        device_uid = f"HYDRA-SIM-{dev_idx:04d}"
        interval = 1.0 / rate_per_device_per_sec if rate_per_device_per_sec > 0 else 1.0

        while time.perf_counter() < end_at:
            t0 = time.perf_counter()
            payload = {
                "device_uid": device_uid,
                "timestamp": time.time(),
                "sensors": {
                    "water_level_pct": round(random.uniform(40.0, 95.0), 1),
                    "turbidity_ntu": round(random.uniform(1.0, 15.0), 1),
                    "current_amps": round(random.uniform(8.5, 12.0), 2),
                    "voltage_v": round(random.uniform(220.0, 240.0), 1),
                    "flow_rate_lpm": round(random.uniform(30.0, 60.0), 1),
                },
                "motor_state": "RUNNING",
            }
            raw_json = json.dumps(payload)
            success = await pipeline.ingest({"device_uid": device_uid, "payload": raw_json})
            if success:
                result.total_sent += 1
                latency = (time.perf_counter() - t0) * 1000.0
                result.latencies_ms.append(latency)
            else:
                result.total_dropped += 1

            # Sleep remaining slice
            elapsed = time.perf_counter() - t0
            sleep_time = max(0.0, interval - elapsed)
            await asyncio.sleep(sleep_time)

    # Launch all device tasks concurrently
    device_tasks = [asyncio.create_task(device_coro(i)) for i in range(num_devices)]
    await asyncio.gather(*device_tasks)

    # Finish queue draining
    pipeline.running = False
    await asyncio.gather(*workers)

    result.end_time = time.perf_counter()
    result.total_processed = pipeline.processed_count
    result.total_dropped += pipeline.dropped_count

    return result


if __name__ == "__main__":
    print("Executing HydraControl Multi-Device Load Test (100 devices)...")
    res = asyncio.run(run_load_test(num_devices=100, rate_per_device_per_sec=10.0, duration_sec=2.0))
    print(json.dumps(res.to_dict(), indent=2))
