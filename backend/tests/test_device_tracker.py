import pytest
import uuid
from datetime import datetime, timezone, timedelta

from app.db.base import Base
from app.db.session import sync_engine, get_sync_session
from app.models.organization import Organization, OrganizationStatus
from app.models.site import Site, SiteStatus, SiteType
from app.models.station import Station, StationStatus, StationType
from app.models.controller import Controller, ControllerStatus, ControllerType
from app.schemas.device import (
    DeviceRegistrationRequest,
    DeviceHeartbeatRequest,
    LivenessState
)
from app.services.device_tracker import (
    calculate_liveness_state,
    register_device,
    record_heartbeat,
    get_device_liveness,
    sync_device_liveness,
    DeviceNotProvisionedException,
    DeviceSiteSuspendedException,
    DeviceDecommissionedException
)


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


def test_calculate_liveness_state_unit():
    now = datetime.now(timezone.utc)

    # Controller without last_seen_at
    c_none = Controller(
        id=uuid.uuid4(),
        station_id=uuid.uuid4(),
        name="Test",
        controller_code="T1",
        device_uid="D1",
        controller_type=ControllerType.ESP32,
        status=ControllerStatus.ACTIVE,
        last_seen_at=None
    )
    state, diff = calculate_liveness_state(c_none, now=now)
    assert state == LivenessState.OFFLINE
    assert diff is None

    # Decommissioned controller
    c_decom = Controller(
        id=uuid.uuid4(),
        station_id=uuid.uuid4(),
        name="Test Decom",
        controller_code="T_DEC",
        device_uid="D_DEC",
        controller_type=ControllerType.ESP32,
        status=ControllerStatus.DECOMMISSIONED,
        last_seen_at=now
    )
    state, diff = calculate_liveness_state(c_decom, now=now)
    assert state == LivenessState.DECOMMISSIONED

    # Online controller (seen 30s ago, threshold 60)
    c_online = Controller(
        id=uuid.uuid4(),
        station_id=uuid.uuid4(),
        name="Test Online",
        controller_code="T_ON",
        device_uid="D_ON",
        controller_type=ControllerType.ESP32,
        status=ControllerStatus.ACTIVE,
        last_seen_at=now - timedelta(seconds=30)
    )
    state, diff = calculate_liveness_state(c_online, now=now, stale_threshold_seconds=60, offline_threshold_seconds=180)
    assert state == LivenessState.ONLINE
    assert 29 <= diff <= 31

    # Stale controller (seen 120s ago, stale=60, offline=180)
    c_stale = Controller(
        id=uuid.uuid4(),
        station_id=uuid.uuid4(),
        name="Test Stale",
        controller_code="T_ST",
        device_uid="D_ST",
        controller_type=ControllerType.ESP32,
        status=ControllerStatus.ACTIVE,
        last_seen_at=now - timedelta(seconds=120)
    )
    state, diff = calculate_liveness_state(c_stale, now=now, stale_threshold_seconds=60, offline_threshold_seconds=180)
    assert state == LivenessState.STALE
    assert 119 <= diff <= 121

    # Offline controller (seen 240s ago, offline=180)
    c_offline = Controller(
        id=uuid.uuid4(),
        station_id=uuid.uuid4(),
        name="Test Offline",
        controller_code="T_OFF",
        device_uid="D_OFF",
        controller_type=ControllerType.ESP32,
        status=ControllerStatus.ACTIVE,
        last_seen_at=now - timedelta(seconds=240)
    )
    state, diff = calculate_liveness_state(c_offline, now=now, stale_threshold_seconds=60, offline_threshold_seconds=180)
    assert state == LivenessState.OFFLINE
    assert 239 <= diff <= 241
