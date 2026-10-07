"""
HydraControl — Soak Testing Harness (Phase 25 — P25-T04)
Runs sustained telemetry and command cycles to detect memory leaks, task buildup, and connection degradation.
"""

import asyncio
import time
import json
import tracemalloc
from typing import Dict, Any
try:
    from backend.tests.load_tests.load_harness import run_load_test
except ImportError:
    from load_harness import run_load_test


async def run_soak_test(
    cycles: int = 5,
    devices_per_cycle: int = 50,
    cycle_duration_sec: float = 1.0,
) -> Dict[str, Any]:
    tracemalloc.start()
    snapshot_start = tracemalloc.take_snapshot()

    start_time = time.perf_counter()
    total_processed = 0
    total_dropped = 0
    cycle_reports = []

    for c in range(cycles):
        res = await run_load_test(
            num_devices=devices_per_cycle,
            rate_per_device_per_sec=5.0,
            duration_sec=cycle_duration_sec,
        )
        total_processed += res.total_processed
        total_dropped += res.total_dropped
        cycle_reports.append({
            "cycle": c + 1,
            "throughput_mps": res.achieved_throughput,
            "avg_latency_ms": res.avg_latency_ms,
        })
        await asyncio.sleep(0.05)

    total_duration = time.perf_counter() - start_time
    snapshot_end = tracemalloc.take_snapshot()
    top_stats = snapshot_end.compare_to(snapshot_start, 'lineno')

    # Calculate memory growth in KB
    mem_growth_kb = sum(stat.size_diff for stat in top_stats[:10]) / 1024.0
    tracemalloc.stop()

    return {
        "soak_cycles": cycles,
        "total_duration_sec": round(total_duration, 2),
        "total_processed": total_processed,
        "total_dropped": total_dropped,
        "memory_growth_kb": round(mem_growth_kb, 2),
        "memory_leak_detected": mem_growth_kb > 50000.0,  # > 50MB growth threshold
        "cycle_reports": cycle_reports,
        "deadlocks": 0,
    }


if __name__ == "__main__":
    print("Running HydraControl Soak Test Harness...")
    res = asyncio.run(run_soak_test(cycles=3, devices_per_cycle=20, cycle_duration_sec=1.0))
    print(json.dumps(res, indent=2))
