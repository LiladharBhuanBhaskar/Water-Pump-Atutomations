# HydraControl — Architectural Decision Records (ADRs)

This document tracks all key technical and architectural decisions made throughout the lifecycle of HydraControl.

---

### DEC-001: Technology Baseline & Modular Monolith Architecture
* **Date:** 2026-10-01
* **Decision:** Adopt a modular monolith architecture for V1 utilizing FastAPI (Python 3.11+), PostgreSQL, SQLAlchemy with Alembic, Mosquitto MQTT Broker, and React/Next.js/TypeScript frontend.
* **Reason:** Ensures rapid end-to-end iteration, unified type safety, clean separation of concerns, and prevents premature microservice complexity while maintaining strong modular boundaries.
* **Alternatives Considered:** 
  1. Microservices architecture (rejected: unnecessary network latency, deployment overhead, and complexity for V1).
  2. Django / Node.js (rejected: FastAPI provides native async high-throughput WebSocket & MQTT integration with Pydantic typing).
* **Impact:** Clean module boundaries between auth, device management, command dispatch, MQTT handlers, and real-time WebSocket pipelines.

---

### DEC-002: Command State vs Actual State Separation
* **Date:** 2026-10-01
* **Decision:** Decouple `command_state` (PENDING, SENT, ACKNOWLEDGED, EXECUTED, FAILED, TIMEOUT) from `actual_motor_state` (OFF, STARTING, RUNNING, STOPPING, FAULT, OFFLINE).
* **Reason:** IoT commands are asynchronous requests over unreliable networks. The UI and backend must never assume command submission equals physical motor execution.
* **Alternatives Considered:** Single motor state updated immediately upon API call (rejected: causes false status displays, dangerous race conditions, and prevents fault detection).
* **Impact:** Every motor command carries a unique `command_id` traceable through PostgreSQL, MQTT, ESP32 firmware/simulator, and WebSocket streams.

---

### DEC-003: Local Controller Safety Priority ("Cloud Controls, Local Controller Protects")
* **Date:** 2026-10-01
* **Decision:** Local controller (ESP32/PLC) holds autonomous local safety logic (turbidity cutoff, tank high/low cutoff, dry run/no-flow cutoff) that executes independently of cloud connectivity.
* **Reason:** Critical physical safety decisions must not depend on internet uptime, network latency, or backend availability.
* **Alternatives Considered:** Cloud-only decision engine (rejected: risk of tank overflow, motor burn-out, or contaminated water pumping during network outages).
* **Impact:** ESP32 simulator and firmware enforce local safety interlocks and publish resulting fault events to the cloud when connected.

---

### DEC-004: Primary Key UUID Strategy
* **Date:** 2026-10-01
* **Decision:** Adopt standard UUIDv4 primary keys for all domain models via SQLAlchemy 2.0 `Uuid(as_uuid=True)` with automatic python `uuid.uuid4` generation.
* **Reason:** Guarantees globally unique, non-sequential entity identifiers suitable for distributed multi-tenant IoT systems while maintaining seamless cross-compatibility between PostgreSQL (native `UUID`) and SQLite (char/binary in tests).
* **Alternatives Considered:** Auto-incrementing integers (rejected: leaks business volume, security risks in multi-tenancy, conflicts in distributed data sync).
* **Impact:** All models inherit `id: Mapped[uuid.UUID]` with default `uuid.uuid4`.

---

### DEC-005: Timezone-Aware UTC Timestamp & BaseModel Inheritance Pattern
* **Date:** 2026-10-01
* **Decision:** Enforce timezone-aware UTC timestamps (`DateTime(timezone=True)`) with `default=utc_now` and `server_default=func.now()` across all models via `TimestampMixin` and abstract `BaseModel`.
* **Reason:** Eliminates timezone ambiguity across multi-site enterprise installations and IoT device event logging.
* **Alternatives Considered:** Naive UTC datetimes (rejected: prone to subtle offset comparison bugs and client timezone misinterpretations).
* **Impact:** Every entity tracks `created_at` and `updated_at` in standardized UTC.

---

### DEC-006: User Role Representation and Storage Strategy
* **Date:** 2026-10-01
* **Decision:** Implement `UserRole` as a string-backed Python Enum (`str, enum.Enum`) and map to database column as `Enum(UserRole, native_enum=False, length=50)` with indexed status.
* **Reason:** Ensures full cross-dialect portability (native strings in SQLite, check-constrained text in PostgreSQL), prevents enum migration pain when adding new roles, and supports both Enterprise (`SUPER_ADMIN`, `ORGANIZATION_ADMIN`, `SITE_MANAGER`, `STATION_OPERATOR`, `TECHNICIAN`, `VIEWER`) and Home (`OWNER`, `FAMILY_MEMBER`, `VIEWER`) roles.
* **Alternatives Considered:** Separate integer lookup table (rejected: unnecessary join overhead for basic authorization checks).
* **Impact:** Clean, type-safe role checks in FastAPI RBAC dependencies.

---

### DEC-007: Password Hash-Only Storage & Email Uniqueness
* **Date:** 2026-10-01
* **Decision:** The `User` database model strictly stores `password_hash: str` (length 255) with zero plaintext password fields. Uniqueness on `email` is enforced via a database unique index, while lowercase email normalization is delegated to the application/service layer.
* **Reason:** Follows defense-in-depth security best practices and keeps the ORM model lean and free of unnecessary serialization hooks.
* **Alternatives Considered:** Storing passwords or salt columns separately (rejected: modern hash algorithms like bcrypt/Argon2 encapsulate salt in the hash string).
* **Impact:** Password hashing logic stays isolated within `app.core.security`.

---

### DEC-008: Progressive Foreign Key Introduction in Phase 1
* **Date:** 2026-10-01
* **Decision:** Maintain `organization_id` as a nullable `Uuid` column on `User` during P1-T03, establishing explicit Foreign Key and relationship navigation during P1-T04 / P1-T16.
* **Reason:** Enables strictly sequential, isolated testing of each domain model without circular model dependency or premature placeholder tables.
* **Alternatives Considered:** Creating stub Organization model early (rejected: violates incremental phase discipline and risks untested schema assumptions).
* **Impact:** Clean, verified step-by-step model creation with full relationship wiring in P1-T16.

---

### DEC-009: Organization Code & Status Representation Strategy
* **Date:** 2026-10-01
* **Decision:** Assign every Organization a human-readable, unique, and indexed `organization_code: str` (e.g. `ACME-001`) alongside its internal `id: uuid.UUID`, and model lifecycle state using `OrganizationStatus` enum (`ACTIVE`, `INACTIVE`, `SUSPENDED`).
* **Reason:** Operators and commercial tenants identify sites and plants using stable business codes rather than UUID strings.
* **Alternatives Considered:** Using organization name as the human identifier (rejected: names are subject to corporate renames/rebranding and spaces create awkward API URLs).
* **Impact:** Clean URLs, unambiguous billing/operator references, and fast indexed lookups.

---

### DEC-010: Tenant Boundary & Non-Destructive User Deletion Policy (SET NULL)
* **Date:** 2026-10-01
* **Decision:** Configure `User.organization_id` foreign key with `ondelete="SET NULL"` rather than `CASCADE`.
* **Reason:** Users (especially technicians, operators, and platform admins) maintain immutable historical audit trails (command history, alarm acknowledgments, maintenance logs) that must not be wiped out if an organization tenant is decommissioned or archived.
* **Alternatives Considered:** Cascade delete (rejected: destroys audit trails and breaks compliance requirements).
* **Impact:** Audit records and user logs remain intact while unlinking tenant affiliation.

---

### DEC-011: Multi-Tenant Scoped Site Code Uniqueness Strategy
* **Date:** 2026-10-01
* **Decision:** Enforce composite uniqueness on `(organization_id, site_code)` via `UniqueConstraint("organization_id", "site_code", name="uq_sites_org_code")`.
* **Reason:** Allows different customer organizations to independently choose intuitive site identifiers (e.g. `SITE-001`, `PLANT-1`, `HOME-01`) without global namespace collisions across tenants.
* **Alternatives Considered:** Global site_code uniqueness (rejected: forces artificial prefixing or UUIDs on commercial customers).
* **Impact:** Clean, natural multi-tenant scoping.

---

### DEC-012: Site Timezone & Location Architecture
* **Date:** 2026-10-01
* **Decision:** Store site display/scheduling timezone as `timezone: str` (defaulting to `Asia/Kolkata`) alongside human-readable `location: str`. All underlying telemetry, events, and database timestamps remain strictly in UTC.
* **Reason:** Allows pump timer schedules and user dashboard charts to align with local site solar/operating hours without corrupting the UTC audit log timeline.
* **Alternatives Considered:** Storing local timestamps directly (rejected: breaks cross-site fleet comparison and daylight savings math).
* **Impact:** Clean conversion between backend UTC and site-localized schedules.

---

### DEC-013: Organization-to-Site Restrictive Deletion Policy (RESTRICT)
* **Date:** 2026-10-01
* **Decision:** Configure `Site.organization_id` foreign key with `ondelete="RESTRICT"`.
* **Reason:** Physical sites contain industrial plant hardware, controller registries, and telemetry history that must not be accidentally purged by deleting a tenant record.
* **Alternatives Considered:** Cascade delete (rejected: massive risk of permanent operational data loss).
* **Impact:** Decommissioning a site requires explicit step-by-step de-provisioning.

---

### DEC-014: Station-to-Site Restrictive Deletion Policy (RESTRICT)
* **Date:** 2026-10-03
* **Decision:** Configure `Station.site_id` foreign key with `ondelete="RESTRICT"`.
* **Reason:** Stations contain controllers, motors, and critical telemetry history. Deleting a site should fail if stations still exist to prevent accidental data loss of physical hardware context.
* **Alternatives Considered:** Cascade delete (rejected: risks silent deletion of active hardware connections and audit histories).
* **Impact:** Requires explicit cleanup of stations before a site can be removed.

---

### DEC-015: Station Code Scope and Uniqueness
* **Date:** 2026-10-03
* **Decision:** Enforce composite uniqueness on `(site_id, station_code)` via `UniqueConstraint("site_id", "station_code", name="uq_stations_site_code")`.
* **Reason:** Ensures stations can use simple, repeatable codes (like "STN-01") within a site without global or organization-wide collisions, which is ideal for large-scale multi-site enterprise deployments.
* **Alternatives Considered:** Organization-wide station codes (rejected: overly restrictive for enterprises with independent sites).
* **Impact:** Supports highly localized naming conventions while maintaining tenant boundary via the Site link.

---

### DEC-016: Controller-to-Station Restrictive Deletion Policy (RESTRICT)
* **Date:** 2026-10-03
* **Decision:** Configure `Controller.station_id` foreign key with `ondelete="RESTRICT"`.
* **Reason:** Controllers are physical devices that execute commands and record critical telemetry. Deleting a station should be blocked to prevent accidental or malicious destruction of hardware connectivity contexts and audit trails.
* **Alternatives Considered:** Cascade delete (rejected: risks silent deletion of physical device records).
* **Impact:** Demands explicit cleanup of controllers before a station can be deleted.

---

### DEC-017: Controller Device UID vs Code Uniqueness
* **Date:** 2026-10-03
* **Decision:** `device_uid` is made globally unique and indexed across the entire database, while `controller_code` is scoped and uniquely constrained only within a given `station_id`.
* **Reason:** `device_uid` corresponds to immutable physical hardware identities (e.g. MAC addresses, burned-in serials) meaning one physical board cannot exist twice. `controller_code` is the human-readable functional name (e.g. "MAIN-CTRL") which can be identical across different physical pump stations.
* **Alternatives Considered:** Making both globally unique (rejected: prevents stations from reusing standard naming schemes like "CTRL-01").
* **Impact:** Supports multi-tenant standard naming while firmly securing device provisioning.

---

### DEC-018: Motor Ownership and Identity Model
* **Date:** 2026-10-03
* **Decision:** Implement the `Motor` model explicitly owned by exactly one `Controller`. Motor does not duplicate organization/site/station IDs. `motor_code` is scoped uniquely within the `controller_id`. `ondelete="RESTRICT"` is enforced on the Controller-Motor foreign key.
* **Reason:** Motors are physical sub-devices wired to controllers. Attempting to manage them independently or globally risks architectural integrity. Controller deletion must be restricted while motors are wired/assigned to it.
* **Alternatives Considered:** Global motor codes (rejected: prevents logical grouping and reusing codes like "PUMP-1").
* **Impact:** Provides a clear mapping of physical topology, separates lifecycle states (e.g. `OFF`, `ON`, `FAULT`), and intentionally defers telemetry/metrics to a later schema phase.

---

### DEC-019: Sensor Ownership and Identity Model
* **Date:** 2026-10-03
* **Decision:** Implement the `Sensor` model explicitly owned by exactly one `Controller`. Sensor does not directly belong to Motor, Tank, or Station. `sensor_code` is scoped uniquely within the `controller_id`. `ondelete="RESTRICT"` is enforced on the Controller-Sensor foreign key.
* **Reason:** Sensors are physical measurement devices wired into controllers. While a sensor may logically monitor a tank or a motor (via a future configuration table or telemetry relationship), its physical ownership belongs to the controller collecting its data. Deleting a controller is restricted while sensors are associated.
* **Alternatives Considered:** Polymorphic sensor ownership allowing parent_id to map to motor/tank/controller (rejected: violates strict schema normalization and breaks relational integrity).
* **Impact:** Cleanly separates physical sensor identity/configuration from runtime telemetry and logical asset mapping (which will be handled in a later phase).

---

### DEC-020: Motor Command Database Identity and Execution Separation
* **Date:** 2026-10-03
* **Decision:** Implement `MotorCommand` as a purely historical database record of an intended operation, owned strictly by a `Motor` (with `ondelete="RESTRICT"`). It features an optional `requested_by` relationship mapped to `User` (with `ondelete="SET NULL"`). Command states (PENDING, SENT, ACKNOWLEDGED, EXECUTED, FAILED, TIMEOUT) and types (START, STOP, RESET, EMERGENCY_STOP) are encapsulated as Enums, and MQTT execution behavior is intentionally excluded from the database model layer. Payload data is stored in portable `JSON`. Timestamps use timezone-aware UTC.
* **Reason:** Separating the command record from the execution layer guarantees that database models remain unaware of MQTT, background tasks, or delivery mechanism details, strictly tracking what was requested, by whom, and its eventual state. The `RESTRICT` behavior preserves audit history for command events even when physical devices are replaced, while `SET NULL` on user deletion ensures that the commands remain in history when operators are removed from the system.
* **Alternatives Considered:** Building an integrated worker state-machine into the model (rejected: couples models to asynchronous execution mechanics).
* **Impact:** Clean and strictly delimited database definition laying the ground for a separate asynchronous Command Delivery and Feedback service in Phase 6.

---

### DEC-021: Motor Event Distinct from Motor Command
* **Date:** 2026-10-03
* **Decision:** Implement `MotorEvent` as a separate database model representing actual historical events occurring on a `Motor`, independent of requested commands (`MotorCommand`). The model has a bidirectional relationship with `Motor` with `ondelete="RESTRICT"` and includes fields for `MotorEventType`, `MotorEventSource`, `occurred_at` (timezone-aware UTC), and optional `event_payload` / `description`.
* **Reason:** Distinguishing between requested actions (commands) and actual real-world occurrences (events) avoids complex hybrid states in a single table. It cleanly maps event histories for auditing (e.g. system faults, user interventions, sensor-triggered shutoffs).
* **Alternatives Considered:** Polymorphic events linked to multiple assets (rejected: violates schema integrity). Linking `MotorEvent` to `MotorCommand` directly (deferred: not strictly required at this foundational layer without an established correlation mechanism).
* **Impact:** Lays groundwork for telemetry ingestion, auditing, and analytics without polluting execution or real-time state boundaries.

---

### DEC-022: Telemetry Relational Model
* **Date:** 2026-10-03
* **Decision:** Implement `TelemetryReading` as a relational model associated with `Sensor` using `ondelete="RESTRICT"`. It stores exactly one measurement per record using `Numeric(20,6)` for decimal precision (to prevent float issues) along with a required `unit` string. It uses `occurred_at` (actual measurement time) and includes a composite index `(sensor_id, occurred_at)` for optimal history querying. No dedicated time-series databases (e.g., QuestDB) are integrated at this stage.
* **Reason:** Ensures that standard SQL can be used seamlessly for telemetry storage initially. The model clearly isolates raw measurement points conceptually from motor state operations. Retaining RESTRICT deletion rules prevents silent corruption of historical records if a sensor entity is removed.
* **Alternatives Considered:** Multi-metric payload objects or dedicated time-series DB engines (deferred: premature optimization for early data-modeling phase).
* **Impact:** Provides a portable, universally testable telemetry storage standard for initial phase feature building.

### DEC-023: Automation Rule Model Structure
- **Date**: 2026-10-03
- **Context**: Need to store configuration for automation rules like high water stops or daily timers.
- **Decision**: Implemented `AutomationRule` with relationships to `Station`, `Sensor` (optional, for condition), `Motor` (target of action), and `User` (creator). Included composite index `(station_id, status)` for quick filtering. Deletion rules: User/Sensor deletes cascade to `SET NULL` to preserve historical configuration, while Station/Motor deletes are `RESTRICTED` to prevent orphan rules.
- **Consequences**: Safely links automation logic to physical devices without hardcoding rules into application code.

### DEC-024: Station Settings Model Configuration vs Runtime State
- **Date**: 2026-10-03
- **Context**: Need to store configuration variables scoped entirely to physical stations.
- **Decision**: Implemented `StationSettings` with a strict one-to-one relationship to `Station`. All fields are explicitly mapped in SQL; no generic JSON bucket was used. Enforced strict cascade deletion behavior (`ondelete='CASCADE'`), treating configuration as tightly coupled rather than historical audit data like events and telemetry. Deliberately separated runtime concepts (like TelemetryReading values) from static configuration (like thresholds).
- **Consequences**: Improves reliability of validation/querying. Clearly bifurcates configuration and physical operational events in the database architecture.

### DEC-025: Audit Log Immutability and Reference Architecture
- **Date**: 2026-10-03
- **Context**: System requires tracking configuration changes, security events, and operator commands for multi-tenant accountability.
- **Decision**: Implemented `AuditLog` as an append-only historical log. Deletions of referenced resources (User, Organization, Site, Station) cascade to `SET NULL` rather than `CASCADE`, ensuring the audit trail outlives the entity itself. Implemented composite index on `(resource_type, resource_id)` to avoid polymorphic foreign keys (which SQLAlchemy handles poorly across varying id types or deleted records) while allowing quick search across events targeting specific domain entities.
- **Consequences**: Guarantees compliance and historical tracking regardless of entity lifecycle. Requires application logic to serialize resource descriptors since relational integrity via foreign key is intentionally soft.

### DEC-026: Alembic Migrations Infrastructure
- **Date**: 2026-10-03
- **Context**: Need a robust database migration infrastructure for the verified SQLAlchemy domain models.
- **Decision**: Integrated Alembic in `backend/alembic`. The `env.py` dynamically resolves `sqlalchemy.url` using the centralized configuration (`app.core.config.settings.DATABASE_URL`) to seamlessly switch between the async app context and the migration environment without duplication. Native async support via `async_engine_from_config` has been maintained. The initial generated migration (`bffa49d195ad`) successfully replicates the current declarative metadata (incorporating the `UUIDMixin`, enum strings, json types, and constraints) and correctly handles SQLite-specific `render_as_batch=True` mechanics.
- **Consequences**: Safe evolution of production and demo schemas. Re-installs of fresh databases can be run from `alembic upgrade head` guaranteeing a consistent start point.

### DEC-027: Development and Demo Seed Strategy
- **Date**: 2026-10-03
- **Context**: Need a repeatable, idempotent way to populate development databases with realistic demo data across all Phase 1 models.
- **Decision**: Implemented `backend/scripts/seed_demo.py` which strictly protects against production execution by verifying `ENVIRONMENT == "development"`. It uses deterministic constraints (e.g. `organization_code`, `sensor_code`) to ensure subsequent runs do not create duplicates (Idempotency). No `AuditLog` entries are generated intentionally to keep system setup distinct from business audits. Passwords for demo users are hashed securely if supported, otherwise safely generated.
- **Consequences**: Ensures developers and demo environments have a stable baseline. Any new models will need to be added to this seed process to be visible in demos.

### DEC-028: RBAC Dependency Injection (require_roles)
- **Date**: 2026-10-03
- **Context**: Need a scalable and reliable mechanism for enforcing Role-Based Access Control (RBAC) across endpoints without duplicating JWT/user lookup logic.
- **Decision**: Implemented a `require_roles` dependency factory in `backend/app/api/deps.py`. It wraps the existing `get_current_user` dependency, checks the authenticated user's `UserRole` against an allowed list, and raises HTTP 403 Forbidden for unauthorized access. HTTP 401 is strictly reserved for unauthenticated/invalid tokens. The existing `UserRole` Enum is used natively.
- **Consequences**: Clean separation of authentication (Who are you?) and authorization (Are you allowed?). RBAC can be attached to any router or endpoint using `Depends(require_roles([...]))`. No separate permissions tables are required for Phase 2 roles.

---

### DEC-029: Organization Isolation & Multi-Tenant Query Scoping
- **Date**: 2026-10-03
- **Context**: Need robust tenant isolation ensuring users can only query and mutate resources within their authenticated organization boundary (`User.organization_id`), with zero trust in client-supplied tenant identifiers (query params, body fields, URL overrides).
- **Decision**:
  1. Implemented `get_current_organization` in `backend/app/api/deps.py`, which derives the tenant context strictly from `current_user.organization_id`, validates organization existence in the database, and enforces `OrganizationStatus.ACTIVE`.
  2. Implemented `build_org_scoped_query` and `get_org_scoped_resource` in `backend/app/services/tenant.py` to query resources by ID while verifying tenant ownership in a single atomic database query through domain relationship joins (`Site -> Station -> Controller -> Motor/Sensor -> Telemetry/Commands/Events/Rules/Settings`). No redundant `organization_id` columns are added to child tables.
  3. Cross-tenant resource queries return `None` (resulting in HTTP 404 Not Found), effectively preventing IDOR attacks and avoiding information disclosure of cross-tenant resource existence.
  4. RBAC and Tenant Isolation operate as orthogonal security layers: a user with an elevated role (e.g., `SUPER_ADMIN`, `ORGANIZATION_ADMIN`) cannot access resources belonging to a foreign tenant.
- **Consequences**: High-assurance tenant isolation across all hierarchical resources without unnecessary schema denormalization or migrations.

---

### DEC-030: Site-Level Authorization Policy & Query Scoping
- **Date**: 2026-10-03
- **Context**: Need site-level authorization boundaries inside an isolated organization tenant, ensuring users only access authorized, operational sites and their child resources.
- **Decision**:
  1. Implemented `get_current_site` in `backend/app/api/deps.py` and `validate_site_access_policy` in `backend/app/services/site_auth.py`.
  2. Anchored site authorization strictly in the authenticated user's verified organization context (`Site.organization_id == current_user.organization_id`). Cross-organization site requests return HTTP 404 Not Found (IDOR defense).
  3. Enforced site lifecycle states: `INACTIVE` (HTTP 403), `SUSPENDED` (HTTP 403), and `MAINTENANCE` (accessible only to `SUPER_ADMIN`, `ORGANIZATION_ADMIN`, `SITE_MANAGER`, `TECHNICIAN`, `OWNER`; blocked with HTTP 403 for `STATION_OPERATOR`, `VIEWER`, `FAMILY_MEMBER`).
  4. Implemented `build_site_scoped_query` and `get_site_scoped_resource` in `backend/app/services/site_auth.py` to scope hierarchical resource queries by `site_id` and `organization_id` in a single query without database schema alterations.
- **Consequences**: Fine-grained site-level protection and hierarchical isolation achieved with zero database migrations.

---

### DEC-031: Motor State Engine Architecture and Transition Semantics
- **Date**: 2026-10-06
- **Context**: Need a deterministic, authoritative state engine to govern motor operational lifecycle across cloud commands, MQTT status ingestion, edge safety events, and real-time streaming, adhering to the core principle: "Cloud controls, local controller protects."
- **Decision**:
  1. **Authoritative State Model**: Preserved the existing `MotorStatus` enum (`OFF`, `STARTING`, `ON`, `STOPPING`, `FAULT`, `MAINTENANCE`, `OFFLINE`, `DISABLED`). Retained `ON` as the authoritative running state (`RUNNING` remains non-authoritative roadmap terminology). `STANDBY` is functionally represented by `OFF`. No database enum alterations or migrations were introduced.
  2. **Transition Function & Conventions**: Implemented pure transition evaluation in `backend/app/services/motor_state_engine.py` via `transition_motor_state` returning `TransitionResult(next_state, reason, event_type, is_valid)`. Provided `validate_and_transition` for service-layer validation raising `InvalidStateTransitionException` when invalid transitions occur.
  3. **Safety Precedence**: Defined strict deterministic precedence: `EMERGENCY_STOP` > `SAFETY_TRIP` > `MAINTENANCE_LOCK` > `ADMIN_DISABLE` > `HEARTBEAT_TIMEOUT` > Normal operational commands (`CMD_START`, `CMD_STOP`). Safety trips latched in `FAULT` cannot be bypassed by cloud `CMD_START` without an explicit `RESET` after edge safety conditions are verified cleared.
  4. **Command vs State Separation**: Commands follow `PENDING -> SENT -> ACKNOWLEDGED -> EXECUTED`. A START command dispatch moves the motor to `STARTING`, but transition to `ON` strictly requires hardware confirmation (ACK `EXECUTED` or valid controller `STATUS` report). STOP dispatch moves the motor to `STOPPING`, reaching `OFF` only upon execution confirmation.
  5. **Stale Message Protection**: Implemented timezone-aware UTC comparison (`is_stale_message`, `ensure_utc`) rejecting older or out-of-order MQTT status reports to prevent state regression.
  6. **Anti-Spoofing & Tenant Integrity**: Enforced strict controller `device_uid` ownership and organization hierarchy resolution in `ack_handler.py`, `status_handler.py`, and `fault_handler.py`. Mismatched or cross-device reports are logged and rejected without state mutation.
  7. **Audit Logging & Streaming**: Verified transitions automatically generate `MotorEvent` audit records (`STARTED`, `STOPPED`, `FAULT`, `RESET`, `EMERGENCY_STOP`, `OFFLINE`, `ONLINE`) without duplicate generation on idempotent messages, and broadcast `MOTOR_STATE` and `SAFETY_ALERT` over read-only WebSocket channels.
### DEC-032: Generic Sensor Framework Architecture & Normalization
- **Date**: 2026-10-06
- **Context**: Need a unified, type-aware generic sensor validation, unit normalization, quality metadata tagging, and historical query framework across all 10 authoritative `SensorType` categories (`WATER_LEVEL`, `TURBIDITY`, `FLOW`, `PRESSURE`, `TEMPERATURE`, `HUMIDITY`, `CURRENT`, `VOLTAGE`, `PH`, `OTHER`) while adhering strictly to existing relational models without schema migrations.
- **Decision**:
  1. **Sensor Type Specifications & Default Units**: Implemented `SENSOR_SPECS` in `backend/app/services/sensor_service.py` defining standard units (`%`, `NTU`, `L/min`, `bar`, `°C`, `%RH`, `A`, `V`, `pH`, `count`), canonical unit alias mappings (e.g. `percent` -> `%`, `ntu` -> `NTU`, `c` -> `°C`, `amp` -> `A`), and defensible valid operating ranges.
  2. **Three-Tier Validation Architecture**: Explicitly decoupled (a) Unit Normalization, (b) Range Validation / Quality Tagging (`GOOD`, `OUT_OF_RANGE`, `BAD`), and (c) Edge Safety Threshold Evaluation (`Turbidity > 25 NTU`, `Tank >= 95%`, `Source <= 10%`). An `OUT_OF_RANGE` reading is tagged with quality metadata and persisted with raw values intact; it never triggers arbitrary safety trips unless required by established edge safety rules.
  3. **Telemetry Ingestion & Anti-Spoofing**: Hardened `backend/app/mqtt/handlers/telemetry_handler.py` and REST direct ingestion to validate controller ownership, ensure sensor codes belong to the reporting device, reject spoofed or cross-tenant payloads, normalize timestamps to timezone-aware UTC, and stream real-time updates over WebSockets.
  4. **Historical & Latest Telemetry Queries**: Implemented `get_sensor_telemetry_history` (supporting optional start/end filters, pagination via limit/offset, chronological ordering) and `get_sensor_latest_telemetry` with strict multi-tenant scoping and IDOR denial (returning 404 for cross-tenant lookups).
  5. **Frontend Dynamic Sensor Discovery**: Updated `Dashboard.tsx` to dynamically query registered sensors for active controllers via `api.getSensors()` and render modular `SensorCard` components, displaying live telemetry, quality flags, status badges, and fault states without hardcoded simulator sensor assumptions.
- **Consequences**: Scalable, high-integrity generic sensor framework fully interoperable with Phase 1–10 contracts, real-time WebSockets, and edge safety architecture with zero database schema alterations.### DEC-033: Phase 12–15 Wave 1 Domain Services & Safety Diagnostics Architecture
- **Date**: 2026-10-06
- **Context**: Need pure, parallel-safe domain services and TypeScript types for Phases 12–15 (Tank Level Safety, Water Quality & Turbidity, Flow Protection, and Electrical Load Diagnostics) without modifying shared runtime engines (`motor_state_engine.py`), MQTT handlers, or performing database migrations.
- **Decision**:
  1. **Pure Domain Service Isolation**: Implemented four isolated backend domain services:
     - `TankSafetyService` (`backend/app/services/tank_safety_service.py`): Pure geometry calculation (cylindrical/rectangular), unit conversions (cm, liters, %), and threshold evaluation (>=95% full auto-stop, <=10% source depletion trip).
     - `WaterQualityService` (`backend/app/services/water_quality_service.py`): Pure water quality evaluation enforcing the hard safety threshold (>25 NTU trip), station configurable turbidity warnings, and safe pH range (6.5–8.5).
     - `FlowProtectionService` (`backend/app/services/flow_protection_service.py`): Pure flow unit normalization (L/min, m³/h, GPM), startup grace period priming, dry-run trip detection (flow approx. 0 after grace period while motor is ON), and excessive/burst flow evaluation.
     - `ElectricalProtectionService` (`backend/app/services/electrical_protection_service.py`): Pure electrical metric derivation (kW power from V, I, and optional power factor; load percentage), overcurrent / locked rotor trip, undercurrent / dry-run trip, and grid undervoltage/overvoltage protection.
  2. **Frontend Type System Additions**: Added strongly-typed TypeScript domain contracts to `frontend/src/types/index.ts` (`TankSafetyEvaluation`, `WaterQualityEvaluation`, `FlowSafetyEvaluation`, `ElectricalSafetyEvaluation`, `TankGeometryConfig`, `ElectricalMetrics`) preserving full backward compatibility.
- **Consequences**: Fast, robust, parallel-safe foundation verified with 27 dedicated unit tests and 450 total passing pytest tests without any regression.

---

### DEC-034: Phase 12–15 Wave 2 Integration & Edge Safety Architecture
- **Date**: 2026-10-06
- **Context**: Need modular, verified integration of Wave 1 domain services into Station Settings/Automation APIs (Wave 2A), Diagnostics APIs (Wave 2B), and Edge Telemetry Safety Integration (Wave 2C) adhering strictly to Phase 10 motor state machine semantics and Phase 11 generic sensor framework without database migrations.
- **Decision**:
  1. **Station Settings & Automation Rules (Wave 2A)**: Implemented `GET/PUT /api/v1/stations/{id}/settings` and `GET/POST/PUT/DELETE /api/v1/automation-rules` using existing `StationSettings` and `AutomationRule` models. Enforced strict RBAC (`SUPER_ADMIN`, `ORGANIZATION_ADMIN`, `SITE_MANAGER` for mutations) and multi-tenant IDOR defense with 404 responses for foreign resources.
  2. **Safety Diagnostics APIs (Wave 2B)**: Implemented `GET /api/v1/stations/{id}/water-quality`, `GET /api/v1/motors/{id}/flow-diagnostics`, and `GET /api/v1/motors/{id}/electrical-metrics` in `diagnostics_service.py` to evaluate live telemetry against domain thresholds with full multi-tenant query scoping.
  3. **Edge Safety Integration & State Engine Wiring (Wave 2C)**: Hardened `backend/app/mqtt/handlers/telemetry_handler.py` to evaluate:
     - **Tank Safety**: Overhead tank >=95% auto-stop (`CMD_STOP` -> `STOPPING`/`OFF`) and source tank <=10% depletion trip (`SAFETY_TRIP` -> `FAULT`).
     - **Turbidity Safety**: Water turbidity >25 NTU contamination trip (`SAFETY_TRIP` -> `FAULT`) and pre-start command rejection in `command_service.py`.
     - **Flow Safety**: Running pump zero-flow dry-run trip after startup grace period and pipe-burst excessive flow trip (`SAFETY_TRIP` -> `FAULT`).
     - **Electrical Safety**: Overcurrent (>12A / overload), undercurrent (<2A), and grid undervoltage/overvoltage protection (`SAFETY_TRIP` -> `FAULT`).
  4. **Audit Logging & Real-Time Alerts**: All safety trips generate `MotorEvent` records and broadcast `SAFETY_ALERT` and `MOTOR_STATE` WebSocket events across tenant-isolated channels.
- **Consequences**: Complete safety integration verified across 461 passing pytest tests, with 0 migrations and untouched runtime database.


