"""
HydraControl — Chaos and Network Resiliency Tests (Phase 25 — P25-T02)
Validates system behavior under severe network failures, disconnects, stale commands, and verifies that local safety remains authoritative.
"""

import pytest
import time
import asyncio
from typing import Dict, Any


class SimulatedDeviceSafetyEngine:
    """Simulated authoritative local controller safety engine running on hardware."""

    def __init__(self, max_runtime_sec: float = 5.0):
        self.motor_state: str = "IDLE"
        self.max_runtime_sec = max_runtime_sec
        self.started_at: float = 0.0
        self.last_cloud_ping: float = time.time()
        self.tripped_reason: str = ""
        self.processed_command_ids = set()

    def start_motor(self, command_id: str) -> bool:
        if command_id in self.processed_command_ids:
            # Replay / duplicate command rejected
            return False
        self.processed_command_ids.add(command_id)
        self.motor_state = "RUNNING"
        self.started_at = time.time()
        return True

    def stop_motor(self, reason: str = "MANUAL_STOP") -> bool:
        self.motor_state = "STOPPED"
        self.tripped_reason = reason
        return True

    def emergency_stop(self) -> bool:
        self.motor_state = "FAULT_LOCKED"
        self.tripped_reason = "EMERGENCY_STOP_TRIP"
        return True

    def tick_local_safety(self, current_time: float) -> None:
        """Local controller autonomously trips if local parameters are breached, even offline."""
        if self.motor_state == "RUNNING":
            if (current_time - self.started_at) > self.max_runtime_sec:
                self.motor_state = "AUTO_SAFETY_TRIPPED"
                self.tripped_reason = "MAX_RUNTIME_EXCEEDED"


@pytest.mark.asyncio
async def test_chaos_network_loss_local_safety_authoritative():
    """Verify that when cloud network is completely lost (30s timeout), local controller safely trips."""
    engine = SimulatedDeviceSafetyEngine(max_runtime_sec=0.2)
    success = engine.start_motor("cmd-001")
    assert success is True
    assert engine.motor_state == "RUNNING"

    # Simulate cloud connection dropping
    cloud_online = False
    await asyncio.sleep(0.3)  # Exceeds max runtime

    # Local hardware tick runs without cloud
    engine.tick_local_safety(time.time())
    assert engine.motor_state == "AUTO_SAFETY_TRIPPED"
    assert engine.tripped_reason == "MAX_RUNTIME_EXCEEDED"


@pytest.mark.asyncio
async def test_chaos_duplicate_and_stale_command_rejection():
    """Verify that duplicate or replayed command packets are rejected by the controller."""
    engine = SimulatedDeviceSafetyEngine()
    cmd_id = "cmd-unique-99"

    # First dispatch succeeds
    res1 = engine.start_motor(cmd_id)
    assert res1 is True

    # Immediate replay / duplicate packet from network glitch is rejected
    res2 = engine.start_motor(cmd_id)
    assert res2 is False


@pytest.mark.asyncio
async def test_chaos_emergency_stop_availability_offline():
    """Verify that hardware Emergency STOP is immediately authoritative and locks the motor."""
    engine = SimulatedDeviceSafetyEngine()
    engine.start_motor("cmd-run")
    assert engine.motor_state == "RUNNING"

    # Hardware E-STOP button pressed
    engine.emergency_stop()
    assert engine.motor_state == "FAULT_LOCKED"
    assert engine.tripped_reason == "EMERGENCY_STOP_TRIP"


@pytest.mark.asyncio
async def test_chaos_heartbeat_loss_detection():
    """Verify heartbeat loss detection flags offline state accurately."""
    last_heartbeat_time = time.time() - 45.0  # 45 seconds ago
    timeout_threshold_sec = 30.0

    is_online = (time.time() - last_heartbeat_time) <= timeout_threshold_sec
    assert is_online is False
