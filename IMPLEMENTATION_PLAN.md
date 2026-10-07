# HydraControl — Implementation Plan & Task Roadmap

This document serves as the single source of truth for all tasks, dependencies, statuses, and acceptance criteria across all development phases.

Statuses: `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, `COMPLETED`, `VERIFIED`.

---

## Phase 0 — Project Foundation

| Task ID | Description | Status | Dependencies | Files Affected | Acceptance Criteria |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **P0-T01** | Repository Inspection & Setup | VERIFIED | None | Root files | Workspace confirmed empty, initial status recorded. |
| **P0-T02** | Folder structure creation | VERIFIED | P0-T01 | `backend/`, `frontend/`, `firmware/`, `device_simulator/`, `infra/`, `docs/`, `scripts/` | Standard directory structure created. |
| **P0-T03** | Backend FastAPI app bootstrap | VERIFIED | P0-T02 | `backend/app/main.py`, `backend/requirements.txt` | FastAPI app with health endpoints `/health`, `/health/db`, `/health/mqtt`. |
| **P0-T04** | Frontend application bootstrap | VERIFIED | P0-T02 | `frontend/` | React + TypeScript + Vite + Tailwind CSS frontend shell. |
| **P0-T05** | Docker Compose setup | VERIFIED | P0-T03, P0-T04 | `docker-compose.yml`, `infra/docker/` | Docker Compose orchestrating PostgreSQL, Mosquitto MQTT, Backend, Frontend. |
| **P0-T06** | PostgreSQL configuration | VERIFIED | P0-T05 | `infra/docker/postgres/` | PostgreSQL service container definition & healthcheck. |
| **P0-T07** | Mosquitto MQTT broker setup | VERIFIED | P0-T05 | `infra/mqtt/mosquitto.conf` | Mosquitto config with anonymous local development / authentication support. |
| **P0-T08** | Environment configuration | VERIFIED | P0-T03 | `backend/app/core/config.py`, `.env` | Pydantic Settings reading environment variables. |
| **P0-T09** | Add `.env.example` | VERIFIED | P0-T08 | `.env.example` | Example environment file with complete defaults. |
| **P0-T10** | Create README.md | VERIFIED | P0-T01 | `README.md` | Architecture, run instructions, and system overview. |
| **P0-T11** | Create PROJECT_STATUS.md | VERIFIED | P0-T01 | `PROJECT_STATUS.md` | Tracking system initialized. |
| **P0-T12** | Create IMPLEMENTATION_PLAN.md | VERIFIED | P0-T01 | `IMPLEMENTATION_PLAN.md` | Roadmap defined. |
| **P0-T13** | Create DECISIONS.md | VERIFIED | P0-T01 | `DECISIONS.md` | Architectural decision records. |

---

## Phase 1 — Database Foundation & Models

| Task ID | Description | Status | Dependencies | Files Affected | Acceptance Criteria |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **P1-T01** | SQLAlchemy setup | VERIFIED | P0-T03 | `backend/app/db/session.py` | Async/Sync SQLAlchemy engine and session factory, health probe and lifecycle tests. |
| **P1-T02** | Base model & Auditing Mixins | VERIFIED | P1-T01 | `backend/app/db/base.py`, `backend/app/models/base.py` | DeclarativeBase, UUID primary key, timezone-aware TimestampMixin, tested sync & async. |
| **P1-T03** | User model | VERIFIED | P1-T02 | `backend/app/models/user.py` | Multi-tenant user model with RBAC role, hashed password, and organization link. |
| **P1-T04** | Organization model | VERIFIED | P1-T03 | `backend/app/models/organization.py` | Multi-tenant root organization entity with code, status enum, and User relationship. |
| **P1-T05** | Site model | VERIFIED | P1-T04 | `backend/app/models/site.py` | Site entity linked to Organization with composite unique code, type, status, and timezone. |
| **P1-T06** | Station model | VERIFIED | P1-T05 | `backend/app/models/station.py` | Station entity linked to Site. |
| **P1-T08** | Controller model | VERIFIED | P1-T07 | `backend/app/models/controller.py` | Controller entity linked to Station/Site with device UID & secret. |
| **P1-T09** | Motor model | VERIFIED | P1-T08 | `backend/app/models/motor.py` | Motor entity linked to Controller with command/actual states. |
| **P1-T10** | Sensor model | VERIFIED | P1-T09 | `backend/app/models/sensor.py` | Sensor entity linked to Controller with measurement category and lifecycle. |
| **P1-T11** | Motor Command model | VERIFIED | P1-T09 | `backend/app/models/motor_command.py` | Command lifecycle: PENDING, SENT, ACKNOWLEDGED, EXECUTED, FAILED, TIMEOUT. |
| **P1-T12** | Motor Event model | VERIFIED | P1-T09 | `backend/app/models/motor_event.py` | State change events, fault records. |
| **P1-T13** | Telemetry model | VERIFIED | P1-T10 | `backend/app/models/telemetry.py` | High-frequency time-series telemetry for sensors. |
| **P1-T14** | Automation Rule model | VERIFIED | P1-T09, P1-T10 | `backend/app/models/automation_rule.py` | Configurable rules (tank full, turbidity threshold, runtime). |
| **P1-T15** | Notification model | VERIFIED | P1-T04 | `backend/app/models/settings.py` | User notifications & delivery status. |
| **P1-T16** | Audit Log model | VERIFIED | P1-T04 | `backend/app/models/audit_log.py` | Tamper-evident audit logs (Who, What, Where, When, Result). |
| **P1-T17** | Alembic migrations setup | VERIFIED | P1-T04..16 | `backend/alembic/` | Migrations run cleanly from empty database. |
| **P1-T18** | Seed & Demo data script | VERIFIED | P1-T17 | `backend/scripts/seed_demo.py` | Demo organization, sites, stations, controllers, motors & sensors created. |

---

## Phase 2 — Authentication & Authorization

| Task ID | Description | Status | Dependencies | Files Affected | Acceptance Criteria |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **P2-T01** | User Registration & Login | VERIFIED | Phase 1 | `backend/app/api/v1/auth.py` | Password hashing (bcrypt), login returning JWT. |
| **P2-T02** | JWT Token Management | VERIFIED | P2-T01 | `backend/app/core/security.py` | Access token generation and verification. |
| **P2-T03** | Current User dependency (Implemented in P2-T01) | VERIFIED | P2-T02 | `backend/app/api/deps.py` | FastAPI dependency retrieving authenticated user. |
| **P2-T04** | Role & Permission RBAC (Implemented in P2-T02) | VERIFIED | P2-T03 | `backend/app/api/deps.py` | Roles: SUPER_ADMIN, ORG_ADMIN, SITE_MANAGER, OPERATOR, TECHNICIAN, VIEWER, OWNER, FAMILY. |
| **P2-T05** | Organization Isolation | VERIFIED | P2-T04 | `backend/app/services/tenant.py`, `backend/app/api/deps.py` | Tenant data isolation enforced across full domain hierarchy. |
| **P2-T06** | Site-level Authorization | VERIFIED | P2-T05 | `backend/app/services/site_auth.py`, `backend/app/api/deps.py` | Site authorization and query scoping enforced across domain hierarchy. |
| **P2-T07** | Auth Tests | VERIFIED | P2-T06 | `backend/tests/test_auth.py` | Automated tests verify unauthorized access blocked. |


---

## Phase 3 — Org / Site / Station / Device Management APIs

| Task ID | Description | Status | Dependencies | Files Affected | Acceptance Criteria |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **P3-T01** | Organization CRUD APIs | VERIFIED | Phase 2 | `backend/app/api/v1/organizations.py` | Full CRUD with validation & RBAC. |
| **P3-T02** | Site CRUD APIs | VERIFIED | P3-T01 | `backend/app/api/v1/sites.py` | Sites scoped to organization. |
| **P3-T03** | Station CRUD APIs | VERIFIED | P3-T02 | `backend/app/api/v1/stations.py` | Stations scoped to site. |
| **P3-T04** | Controller CRUD APIs | VERIFIED | P3-T03 | `backend/app/api/v1/controllers.py` | Controller provisioning & metadata. |
| **P3-T05** | Motor CRUD APIs | VERIFIED | P3-T04 | `backend/app/api/v1/motors.py` | Motor configuration & operational parameters. |
| **P3-T06** | Sensor CRUD APIs | VERIFIED | P3-T04 | `backend/app/api/v1/sensors.py` | Sensor registration, units, thresholds. |

---

## Phase 4 — Device Registration & Heartbeat

| Task ID | Description | Status | Dependencies | Files Affected | Acceptance Criteria |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **P4-T01** | Device Registration Endpoint | COMPLETED | Phase 3 | `backend/app/api/v1/devices.py` | Secure provisioning with UID and hardware tokens. |
| **P4-T02** | Device Heartbeat & Liveness Tracker | COMPLETED | P4-T01 | `backend/app/services/device_tracker.py` | Heartbeat updates `last_seen_at`, transitions ONLINE -> STALE -> OFFLINE. |

---

## Phase 5 — MQTT Foundation

| Task ID | Description | Status | Dependencies | Files Affected | Acceptance Criteria |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **P5-T01** | MQTT Client Service | COMPLETED | Phase 0 | `backend/app/mqtt/client.py` | Robust asynchronous MQTT service with auto-reconnect. |
| **P5-T02** | MQTT Topic Hierarchy & Routing | COMPLETED | P5-T01 | `backend/app/mqtt/router.py` | Standardized topic handling (`devices/{id}/...`). |
| **P5-T03** | Inbound MQTT Message Handlers | COMPLETED | P5-T02 | `backend/app/mqtt/handlers/` | Handlers for telemetry, ACK, status, fault, heartbeat. |

---

## Phase 6 — Motor Command Lifecycle

| Task ID | Description | Status | Dependencies | Files Affected | Acceptance Criteria |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **P6-T01** | Command Service & DB Dispatch | VERIFIED | Phase 1, Phase 5 | `backend/app/services/command_service.py` | Creates UUID command, records PENDING in DB, publishes MQTT. |
| **P6-T02** | Motor Start/Stop API Endpoints | VERIFIED | P6-T01 | `backend/app/api/v1/motor_control.py` | `POST /motors/{id}/start`, `POST /motors/{id}/stop`. |
| **P6-T03** | ACK & Status Ingestion | VERIFIED | P6-T02 | `backend/app/mqtt/handlers/ack_handler.py`, `backend/app/mqtt/handlers/status_handler.py` | Updates command to ACKNOWLEDGED/EXECUTED/FAILED, updates motor state, generates MotorEvent. |
| **P6-T04** | Command Timeout Watchdog | VERIFIED | P6-T03 | `backend/app/services/command_watchdog.py` | Flags unacknowledged commands as TIMEOUT, preserves terminal states, idempotent. |

---

## Phase 7 — ESP32 Hardware Simulator

| Task ID | Description | Status | Dependencies | Files Affected | Acceptance Criteria |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **P7-T01** | Python ESP32 Device Simulator Core & Protocol Alignment | VERIFIED | Phase 5, Phase 6 | `device_simulator/esp32_simulator.py` | Subscribes to commands, executes realistic state transitions, publishes ACK, status, heartbeats, telemetry, faults. |
| **P7-T02** | Local Safety Interlocks & Offline Autonomous Protection | VERIFIED | P7-T01 | `device_simulator/esp32_simulator.py` | Local turbidity >25 NTU cutoff, tank >=95% auto-stop, E-stop latching, offline safe state, reconnect event flushing. |

---

## Phase 8 — Real-Time WebSocket Service

| Task ID | Description | Status | Dependencies | Files Affected | Acceptance Criteria |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **P8-T01** | WebSocket Broadcast Hub | VERIFIED | Phase 2 | `backend/app/websocket/hub.py`, `backend/app/api/v1/websocket.py` | Connection manager with authenticated user channels, tenant isolation, and topic filtering. |
| **P8-T02** | Event & Telemetry Streamer | VERIFIED | P8-T01, Phase 6 | `backend/app/websocket/streamer.py`, MQTT handlers, Command service | Broadcasts motor state, telemetry, command lifecycle, and alerts in real-time. |

---

## Phase 9 — Frontend Integration & Milestone 1 Verification

| Task ID | Description | Status | Dependencies | Files Affected | Acceptance Criteria |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **P9-T01** | Frontend Design System & Theme | VERIFIED | Phase 0 | `frontend/src/index.css`, `frontend/src/types/index.ts`, `frontend/src/components/common/` | Premium UI with dark mode, glassmorphism, responsive dashboard. |
| **P9-T02** | Auth, Dashboard & Device Views | VERIFIED | P9-T01, Phase 3 | `frontend/src/services/api.ts`, `frontend/src/context/AuthContext.tsx`, `frontend/src/pages/`, `frontend/src/components/` | Auth flow, Organization/Site/Station navigation, Motor controls. |
| **P9-T03** | WebSocket Client Integration | VERIFIED | P9-T02, Phase 8 | `frontend/src/services/ws.ts`, `frontend/src/App.tsx` | Real-time state updates without page reload, auto-reconnect, exponential backoff. |
| **P9-T04** | Critical Acceptance Test 1 Verification | VERIFIED | P9-T03, Phase 7 | `backend/tests/test_milestone_1_verification.py`, Full stack | Complete UI -> FastAPI -> DB -> MQTT -> Simulator -> ACK -> WebSocket -> UI verified. |

---

## Phase 10 — Motor State Engine

| Task ID | Description | Status | Dependencies | Files Affected | Acceptance Criteria |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **P10-T01** | Motor State Engine Core & Transition Model | VERIFIED | Phase 1, Phase 6 | `backend/app/services/motor_state_engine.py` | Pure deterministic transition engine (`transition_motor_state`, `validate_and_transition`), preserves existing `MotorStatus` enum values, retains `ON` as running state, enforces safety precedence, blocks invalid transitions without migrations. |
| **P10-T02** | Command Lifecycle & Edge Safety State Integration | VERIFIED | P10-T01, Phase 5, Phase 6 | `command_service.py`, `ack_handler.py`, `status_handler.py`, `fault_handler.py`, `command_watchdog.py`, `motor_control.py` | Separates command lifecycle from physical state, validates controller device ownership, enforces stale protection, preserves local edge safety interlocks (Turbidity >25 NTU, Tank >=95%, Source <=10%, E-Stop), adds reset endpoint. |
| **P10-T03** | MotorEvent Audit Logging & Real-Time WebSocket Streaming | VERIFIED | P10-T01, P10-T02, Phase 8 | `MotorEvent`, `streamer.py`, `websocket.py` | State transitions generate `MotorEvent` records (`STARTED`, `STOPPED`, `FAULT`, `RESET`, `EMERGENCY_STOP`, `OFFLINE`, `ONLINE`) without duplicate generation on idempotent MQTT messages, streams `MOTOR_STATE` and `SAFETY_ALERT` via read-only WebSockets. |
| **P10-T04** | Comprehensive Motor State Engine Verification & Regression | VERIFIED | P10-T01..P10-T03 | `backend/tests/test_motor_state_engine.py` | 19 comprehensive tests covering full transition matrix, safety precedence, MQTT ACK/status/fault processing, anti-spoofing, stale protection, concurrency, watchdog timeouts, and RBAC permissions. Full pytest regression suite: 414 passed, 1 warning. |

---

## Phase 11 — Generic Sensor Framework

| Task ID | Description | Status | Dependencies | Files Affected | Acceptance Criteria |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **P11-T01** | Generic Sensor Domain & Schema Normalization | VERIFIED | Phase 1, Phase 3 | `backend/app/services/sensor_service.py`, `backend/app/services/sensor.py` | Specifications for all 10 authoritative `SensorType` values, standard default units, canonical unit aliases, range validation, quality metadata tagging (`GOOD`, `OUT_OF_RANGE`, `BAD`), and UTC datetime normalization. |
| **P11-T02** | Telemetry Ingestion Hardening | VERIFIED | P11-T01, Phase 5 | `backend/app/mqtt/handlers/telemetry_handler.py` | Ingestion path hardened with device anti-spoofing, controller ownership check, unknown sensor rejection, stale reading prevention, and live WebSocket streaming. |
| **P11-T03** | Sensor Telemetry REST API | VERIFIED | P11-T01, P11-T02 | `backend/app/api/v1/sensors.py`, `backend/app/schemas/telemetry.py` | Endpoints `GET /{sensor_id}/telemetry` (history with pagination/filters), `GET /{sensor_id}/latest` (most recent reading), and `POST /{sensor_id}/telemetry` (direct ingest) with RBAC and multi-tenant isolation. |
| **P11-T04** | Frontend Dynamic Sensor Dashboard | VERIFIED | P11-T01..P11-T03, Phase 9 | `frontend/src/components/SensorCard.tsx`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/types/index.ts`, `frontend/src/services/api.ts` | Dynamic sensor discovery via `api.getSensors()`, responsive glassmorphic `SensorCard` widgets, real-time WebSocket state synchronization, and fault badges. |
| **P11-T05** | Comprehensive Verification & Full Regression | VERIFIED | P11-T01..P11-T04 | `backend/tests/test_generic_sensor_framework.py` | 9 comprehensive tests covering all 10 sensor types, unit aliases, quality tags, CRUD, history queries, anti-spoofing, and multi-tenant isolation. Full pytest regression: 423 passed, 1 warning. Real browser E2E verified. |

---

## Phases 12–15 — Wave 1 (Isolated Domain Services & Frontend Types)

| Task ID | Description | Status | Dependencies | Files Affected | Acceptance Criteria |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **P12-T01** | Tank Level & Safety Domain Service | VERIFIED | Phase 1, Phase 11 | `backend/app/services/tank_safety_service.py`, `backend/tests/test_tank_safety.py` | Pure deterministic tank level evaluation, geometry calculations (cylindrical, rectangular), unit conversions (cm, L, %), threshold evaluation (>=95% full auto-stop, <=10% source depletion trip). 7/7 tests passed. |
| **P13-T01** | Water Quality & Turbidity Domain Service | VERIFIED | Phase 1, Phase 11 | `backend/app/services/water_quality_service.py`, `backend/tests/test_turbidity_safety.py` | Pure water quality evaluation enforcing hard safety threshold (>25 NTU trip), station threshold warnings, safe pH range (6.5–8.5). 6/6 tests passed. |
| **P14-T01** | Flow Protection & Dry-Run Domain Service | VERIFIED | Phase 1, Phase 11 | `backend/app/services/flow_protection_service.py`, `backend/tests/test_flow_protection.py` | Pure flow unit normalization (L/min, m³/h, GPM), startup grace period priming, dry-run trip detection (flow approx. 0 after grace period while motor is ON), burst flow detection. 6/6 tests passed. |
| **P15-T01** | Electrical Load & Diagnostics Domain Service | VERIFIED | Phase 1, Phase 11 | `backend/app/services/electrical_protection_service.py`, `backend/tests/test_electrical_protection.py` | Pure electrical metric derivation (kW power from V, I, optional PF; load %), overcurrent trip (>12A / overload), undercurrent trip (<2A while ON), grid undervoltage/overvoltage protection. 8/8 tests passed. |
| **P12-15-FE** | Frontend Types for Phases 12–15 | VERIFIED | Phase 9, Phase 11 | `frontend/src/types/index.ts` | TypeScript domain contracts for tank safety, water quality, flow diagnostics, and electrical diagnostics. Vite production build 0 errors in 2.38s. |

---

## Phases 12–15 — Wave 2 (Settings, Diagnostics & Edge Safety Integration)

| Task ID | Description | Status | Dependencies | Files Affected | Acceptance Criteria |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **P12-T03** | Station Settings & Automation Rules APIs | VERIFIED | Wave 1, Phase 3 | `backend/app/api/v1/stations.py`, `backend/app/api/v1/automation_rules.py`, `backend/app/services/station_settings.py`, `backend/app/services/automation_rule.py`, `backend/tests/test_station_settings_and_rules.py` | `GET/PUT /api/v1/stations/{id}/settings`, `GET/POST/PUT/DELETE /api/v1/automation-rules`, RBAC (`SUPER_ADMIN`, `ORGANIZATION_ADMIN`, `SITE_MANAGER`), tenant IDOR protection. 3/3 tests passed. |
| **P13-T03** | Water Quality Diagnostics API | VERIFIED | Wave 1, Wave 2A | `backend/app/api/v1/stations.py`, `backend/app/services/diagnostics_service.py`, `backend/tests/test_safety_diagnostics_api.py` | `GET /api/v1/stations/{id}/water-quality` returning live turbidity & pH evaluation, threshold warning, and critical trip status with multi-tenant scoping. |
| **P14-T03** | Flow Diagnostics API | VERIFIED | Wave 1, Wave 2A | `backend/app/api/v1/motors.py`, `backend/app/services/diagnostics_service.py`, `backend/tests/test_safety_diagnostics_api.py` | `GET /api/v1/motors/{id}/flow-diagnostics` returning live flow rate (L/min, m³/h), startup grace period state, and dry-run evaluation. |
| **P15-T03** | Electrical Metrics API | VERIFIED | Wave 1, Wave 2A | `backend/app/api/v1/motors.py`, `backend/app/services/diagnostics_service.py`, `backend/tests/test_safety_diagnostics_api.py` | `GET /api/v1/motors/{id}/electrical-metrics` returning live current, voltage, power (kW), load %, and electrical safety evaluation. |
| **P12-15-2C** | Edge Safety Engine Integration & Alerts | VERIFIED | Wave 1, Wave 2A, Wave 2B | `backend/app/mqtt/handlers/telemetry_handler.py`, `backend/app/services/command_service.py`, `backend/tests/test_wave2_safety_integration.py` | Inbound telemetry evaluation across Tank Level (>=95% full auto-stop, <=10% source trip), Turbidity (>25 NTU trip + pre-start check), Flow (dry-run & pipe-burst trips), and Electrical (overload & voltage trips) triggering Phase 10 motor transitions, `MotorEvent` audit records, and `SAFETY_ALERT` WebSocket events. 5/5 tests passed. |

---

## Phases 12–15 — Wave 3 (Frontend Components & Dashboard Integration)

| Task ID | Description | Status | Dependencies | Files Affected | Acceptance Criteria |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **P12-15-3A** | Tank Safety & Water Level UI Component | VERIFIED | Wave 1, Wave 2 | `frontend/src/components/TankSafetyCard.tsx` | Overhead tank level, sump level, auto-stop threshold cutoff, source depletion warning, clear distinction of NORMAL, WARNING, TANK FULL, SOURCE DEPLETED states. |
| **P12-15-3B** | Water Quality UI Component | VERIFIED | Wave 1, Wave 2 | `frontend/src/components/WaterQualityCard.tsx` | Turbidity (NTU), quality tier, threshold limit, pH reading, chemical safety status, TURBIDITY_TRIP critical banner. |
| **P12-15-3C** | Flow Diagnostics UI Component | VERIFIED | Wave 1, Wave 2 | `frontend/src/components/FlowDiagnosticsCard.tsx` | Flow rate L/min and m³/h, startup grace priming indicator, dry-run trip detection, burst flow alert, motor operational state. |
| **P12-15-3D** | Electrical Metrics UI Component | VERIFIED | Wave 1, Wave 2 | `frontend/src/components/ElectricalMetricsCard.tsx` | Line current (A), nominal voltage (V), estimated power (kW), load ratio %, overload/voltage warning badges. |
| **P12-15-3E** | Reusable Safety Alert Banner | VERIFIED | Wave 1, Wave 2 | `frontend/src/components/SafetyAlertBanner.tsx` | Supports all Phase 12–15 trip types (`TANK_FULL`, `SOURCE_DEPLETED`, `TURBIDITY_TRIP`, `DRY_RUN_TRIP`, `PIPE_BURST`, `OVERLOAD_TRIP`, `UNDERCURRENT_TRIP`, `VOLTAGE_TRIP`, `EMERGENCY_STOP`). |
| **P12-15-3F** | Station Settings & Automation Rules Modal | VERIFIED | Wave 2A | `frontend/src/components/StationSettingsModal.tsx` | Station thresholds management, automation rule listing & creation, RBAC UI restrictions (`SUPER_ADMIN`, `ORG_ADMIN`, `SITE_MANAGER` edit; `OPERATOR`, `VIEWER` read-only). |
| **P12-15-3G** | Dashboard Integration | VERIFIED | P12-15-3A..3F | `frontend/src/pages/Dashboard.tsx` | Coherent Station hierarchy: Station -> Tank Safety / Water Quality, Settings Modal, Motors -> Controls, Flow Diagnostics, Electrical Metrics -> Generic Sensors & Safety Alerts. All motor controls and WebSocket streams preserved. |
| **P12-15-3H** | TypeScript & Vite Build Verification | VERIFIED | P12-15-3A..3G | `frontend/src/services/api.ts`, `frontend/src/types/index.ts` | `tsc --noEmit` 0 errors; `npm run build` passed in 6.19s; full backend pytest regression: 461 passed, 1 warning in 137.72s. |

---

## Phases 12–26 (Planned Roadmap)

* **Phase 12–15 Wave 4:** Final Hardening, Edge Simulation & End-to-End Acceptance — *Awaiting Explicit Authorization*
* **Phase 16:** Timers & Schedules (Runtime warnings, 1-min alert, auto-stop)
* **Phase 17:** Notifications (In-app, Push, Email, SMS/WhatsApp)
* **Phase 18:** Alerts & Event History Filters
* **Phase 19:** Tamper-Proof Audit Logging System
* **Phase 20:** Multi-Site Enterprise Management & Fleet Portfolio
* **Phase 21:** Home User Mode (Ultra-simplified UX)
* **Phase 22:** UX Hardening (Stale data indicators, offline messaging)
* **Phase 23:** Security Hardening (JWT, TLS, Rate limits, Secret management)
* **Phase 24:** Observability & Health Probes (`/health`, `/health/db`, `/health/mqtt`)
* **Phase 25:** Comprehensive Automated Test Suite
* **Phase 26:** Production Readiness & Hardware Firmware Integration




