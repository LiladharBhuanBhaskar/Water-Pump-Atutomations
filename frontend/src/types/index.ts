/**
 * HydraControl — Core TypeScript Domain Types & Interfaces
 * Matches backend schemas and models for Organizations, Sites, Stations, Controllers,
 * Motors, Sensors, Commands, Telemetry, and Real-Time WebSocket events.
 */

export type UserRole =
  | 'SUPER_ADMIN'
  | 'ORGANIZATION_ADMIN'
  | 'SITE_MANAGER'
  | 'STATION_OPERATOR'
  | 'TECHNICIAN'
  | 'VIEWER'
  | 'OWNER'
  | 'FAMILY_MEMBER';

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  organization_id: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export type OrganizationStatus = 'ACTIVE' | 'INACTIVE' | 'SUSPENDED';

export interface Organization {
  id: string;
  name: string;
  organization_code: string;
  status: OrganizationStatus;
  description?: string | null;
  created_at?: string;
}

export type SiteStatus = 'ACTIVE' | 'INACTIVE' | 'SUSPENDED' | 'MAINTENANCE';
export type SiteType = 'HOME' | 'FARM' | 'APARTMENT' | 'COMMERCIAL' | 'FACTORY' | 'PUMP_STATION' | 'OTHER';

export interface Site {
  id: string;
  organization_id: string;
  name: string;
  site_code: string;
  site_type: SiteType;
  status: SiteStatus;
  location?: string | null;
  timezone: string;
  description?: string | null;
  created_at?: string;
}

export type StationStatus = 'ACTIVE' | 'INACTIVE' | 'MAINTENANCE';
export type StationType = 'WATER_SUPPLY' | 'BOREWELL' | 'SUMP_OVERHEAD' | 'IRRIGATION' | 'TREATMENT_PLANT' | 'OTHER';

export interface Station {
  id: string;
  site_id: string;
  name: string;
  station_code: string;
  station_type: StationType;
  status: StationStatus;
  location_in_site?: string | null;
  description?: string | null;
  created_at?: string;
}

export type ControllerStatus = 'ACTIVE' | 'INACTIVE' | 'MAINTENANCE' | 'OFFLINE' | 'DECOMMISSIONED';
export type ControllerType = 'ESP32' | 'ESP32_ETHERNET' | 'ESP32_4G' | 'PLC' | 'INDUSTRIAL_GATEWAY' | 'OTHER';

export interface Controller {
  id: string;
  station_id: string;
  name: string;
  controller_code: string;
  device_uid: string;
  controller_type: ControllerType;
  status: ControllerStatus;
  firmware_version?: string | null;
  ip_address?: string | null;
  mac_address?: string | null;
  last_seen_at?: string | null;
  description?: string | null;
}

export type MotorStatus =
  | 'OFF'
  | 'STARTING'
  | 'ON'
  | 'STOPPING'
  | 'FAULT'
  | 'STANDBY'
  | 'MAINTENANCE'
  | 'OFFLINE'
  | 'DISABLED';

export type MotorType = 'SUBMERSIBLE' | 'MONOBLOCK' | 'CENTRIFUGAL' | 'JET' | 'BOOSTER' | 'SOLAR_PUMP' | 'WATER_PUMP' | 'OTHER';

export interface Motor {
  id: string;
  controller_id: string;
  name: string;
  motor_code: string;
  motor_type: MotorType;
  status: MotorStatus;
  rated_power?: number | null;
  max_runtime_minutes?: number | null;
  cooldown_minutes?: number | null;
  description?: string | null;
}

export type SensorType =
  | 'WATER_LEVEL'
  | 'TURBIDITY'
  | 'FLOW'
  | 'FLOW_RATE'
  | 'PRESSURE'
  | 'TEMPERATURE'
  | 'HUMIDITY'
  | 'CURRENT'
  | 'VOLTAGE'
  | 'PH'
  | 'OTHER';

export type SensorStatus = 'ACTIVE' | 'INACTIVE' | 'MAINTENANCE' | 'FAULT' | 'DISABLED';

export interface Sensor {
  id: string;
  controller_id: string;
  name: string;
  sensor_code: string;
  sensor_type: SensorType;
  status: SensorStatus;
  unit?: string;
  description?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface TelemetryReading {
  id: string;
  sensor_id: string;
  value: number;
  unit: string;
  occurred_at: string;
  metadata?: Record<string, any> | null;
  created_at?: string;
}

export type CommandType = 'START' | 'STOP' | 'RESET' | 'EMERGENCY_STOP';
export type CommandStatus = 'PENDING' | 'SENT' | 'ACKNOWLEDGED' | 'EXECUTED' | 'FAILED' | 'TIMEOUT';

export interface MotorCommand {
  id: string;
  motor_id: string;
  command_type: CommandType;
  status: CommandStatus;
  requested_by?: string | null;
  command_payload?: Record<string, any> | null;
  error_message?: string | null;
  requested_at: string;
  sent_at?: string | null;
  acknowledged_at?: string | null;
  executed_at?: string | null;
  failed_at?: string | null;
}

// WebSocket Event Payloads
export interface WsTelemetryEvent {
  event: 'TELEMETRY';
  device_uid: string;
  station_id?: string | null;
  site_id?: string | null;
  organization_id?: string | null;
  sensor_id: string;
  sensor_code: string;
  value: number;
  unit: string;
  occurred_at: string;
  metadata?: Record<string, any>;
}

export interface WsMotorStateEvent {
  event: 'MOTOR_STATE';
  motor_id: string;
  motor_code: string;
  device_uid: string;
  station_id?: string | null;
  site_id?: string | null;
  organization_id?: string | null;
  status: MotorStatus;
  previous_status?: MotorStatus | null;
  timestamp: string;
}

export interface WsCommandLifecycleEvent {
  event: 'COMMAND_LIFECYCLE';
  command_id: string;
  motor_id: string;
  command_type: CommandType;
  status: CommandStatus;
  error_message?: string | null;
  device_uid: string;
  station_id?: string | null;
  site_id?: string | null;
  organization_id?: string | null;
  timestamp: string;
}

export interface WsSafetyAlertEvent {
  event: 'SAFETY_ALERT';
  event_type: 'EMERGENCY_STOP' | 'FAULT' | 'RESET' | string;
  motor_id: string;
  motor_code: string;
  device_uid: string;
  station_id?: string | null;
  site_id?: string | null;
  organization_id?: string | null;
  description?: string | null;
  payload?: Record<string, any>;
  timestamp: string;
}

export type WsServerEvent =
  | WsTelemetryEvent
  | WsMotorStateEvent
  | WsCommandLifecycleEvent
  | WsSafetyAlertEvent;

// ==========================================
// Phase 12–15 Domain & Safety Diagnostics Types
// ==========================================

// Phase 12: Tank Level & Geometry
export type TankType = 'OVERHEAD' | 'SUMP' | 'SOURCE' | 'BUFFER';
export type TankGeometryType = 'CYLINDRICAL' | 'RECTANGULAR' | 'GENERIC';
export type TankSafetyStatus = 'SAFE' | 'FULL' | 'DEPLETED' | 'INVALID';

export interface TankGeometryConfig {
  geometry_type: TankGeometryType;
  height_cm: number;
  diameter_cm?: number | null;
  length_cm?: number | null;
  width_cm?: number | null;
  total_capacity_liters?: number | null;
}

export interface TankSafetyEvaluation {
  status: TankSafetyStatus;
  is_safe: boolean;
  should_auto_stop: boolean;
  should_trip: boolean;
  fill_percentage: number;
  volume_liters?: number | null;
  water_height_cm?: number | null;
  trip_reason?: string | null;
}

// Phase 12: Station Settings & Automation Rules
export interface StationSettingsUpdate {
  timezone?: string | null;
  auto_stop_on_tank_full?: boolean | null;
  water_level_threshold?: number | null;
  turbidity_threshold?: number | null;
  default_timer_seconds?: number | null;
  offline_alert_enabled?: boolean | null;
  offline_timeout_seconds?: number | null;
}

export interface StationSettingsResponse {
  id: string;
  station_id: string;
  timezone: string;
  auto_stop_on_tank_full: boolean;
  water_level_threshold?: number | null;
  turbidity_threshold?: number | null;
  default_timer_seconds?: number | null;
  offline_alert_enabled: boolean;
  offline_timeout_seconds: number;
  created_at: string;
  updated_at: string;
}

export type AutomationRuleType =
  | 'TANK_FULL_AUTO_STOP'
  | 'SOURCE_DEPLETION_AUTO_STOP'
  | 'TURBIDITY_CUTOFF'
  | 'SCHEDULED_TIMER'
  | 'DRY_RUN_PROTECTION'
  | 'ELECTRICAL_OVERLOAD_PROTECTION';

export type AutomationOperator = 'GT' | 'GTE' | 'LT' | 'LTE' | 'EQ' | 'NEQ';
export type AutomationAction = 'STOP' | 'START' | 'ALERT_ONLY' | 'LOCKOUT';
export type AutomationRuleStatus = 'ACTIVE' | 'INACTIVE' | 'DISABLED';

export interface AutomationRuleCreate {
  station_id: string;
  name: string;
  description?: string | null;
  rule_type: AutomationRuleType;
  status?: AutomationRuleStatus;
  sensor_id?: string | null;
  operator?: AutomationOperator | null;
  threshold_value?: number | null;
  threshold_unit?: string | null;
  duration_seconds?: number | null;
  motor_id: string;
  action: AutomationAction;
  cooldown_seconds?: number | null;
}

export interface AutomationRuleUpdate {
  name?: string | null;
  description?: string | null;
  rule_type?: AutomationRuleType | null;
  status?: AutomationRuleStatus | null;
  sensor_id?: string | null;
  operator?: AutomationOperator | null;
  threshold_value?: number | null;
  threshold_unit?: string | null;
  duration_seconds?: number | null;
  motor_id?: string | null;
  action?: AutomationAction | null;
  cooldown_seconds?: number | null;
}

export interface AutomationRuleResponse {
  id: string;
  station_id: string;
  name: string;
  description?: string | null;
  rule_type: AutomationRuleType;
  status: AutomationRuleStatus;
  sensor_id?: string | null;
  operator?: AutomationOperator | null;
  threshold_value?: number | null;
  threshold_unit?: string | null;
  duration_seconds?: number | null;
  motor_id: string;
  action: AutomationAction;
  cooldown_seconds?: number | null;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
}

// Phase 13: Water Quality & Turbidity
export type WaterQualityStatus = 'SAFE' | 'UNSAFE' | 'WARNING' | 'INVALID';

export interface WaterQualityEvaluation {
  status: WaterQualityStatus;
  is_safe: boolean;
  should_trip: boolean;
  trip_reason?: string | null;
  turbidity_ntu?: number | null;
  ph?: number | null;
  threshold_used?: number | null;
  details?: Record<string, any>;
}

export interface WaterQualityResponse {
  station_id: string;
  turbidity_ntu?: number | null;
  turbidity_quality?: string | null;
  turbidity_updated_at?: string | null;
  ph?: number | null;
  ph_quality?: string | null;
  ph_updated_at?: string | null;
  status: WaterQualityStatus;
  is_safe: boolean;
  should_trip: boolean;
  trip_reason?: string | null;
  threshold_used?: number | null;
  details?: Record<string, any>;
}

// Phase 14: Flow Protection & Dry-Run
export type FlowSafetyStatus = 'NORMAL' | 'DRY_RUN' | 'BURST' | 'STARTUP_GRACE' | 'INVALID';
export type FlowUnit = 'L_MIN' | 'M3_H' | 'GPM';

export interface FlowSafetyEvaluation {
  status: FlowSafetyStatus;
  is_safe: boolean;
  should_trip: boolean;
  trip_reason?: string | null;
  flow_rate_lpm?: number | null;
  flow_rate_m3h?: number | null;
  is_startup_grace_period: boolean;
  details?: Record<string, any>;
}

export interface FlowDiagnosticsResponse {
  motor_id: string;
  motor_status: MotorStatus;
  flow_rate_lpm?: number | null;
  flow_rate_m3h?: number | null;
  raw_flow_value?: number | null;
  raw_flow_unit?: string | null;
  flow_updated_at?: string | null;
  is_startup_grace_period: boolean;
  status: FlowSafetyStatus;
  is_safe: boolean;
  should_trip: boolean;
  trip_reason?: string | null;
  details?: Record<string, any>;
}

// Phase 15: Electrical Load & Diagnostics
export type ElectricalSafetyStatus = 'NORMAL' | 'OVERCURRENT' | 'UNDERCURRENT' | 'UNDERVOLTAGE' | 'OVERVOLTAGE' | 'INVALID';

export interface ElectricalMetrics {
  current_a: number;
  voltage_v: number;
  power_kw: number;
  load_percentage: number;
  is_power_factor_estimated: boolean;
  power_factor: number;
}

export interface ElectricalSafetyEvaluation {
  status: ElectricalSafetyStatus;
  is_safe: boolean;
  should_trip: boolean;
  trip_reason?: string | null;
  metrics?: ElectricalMetrics | null;
  details?: Record<string, any>;
}

export interface ElectricalMetricsResponse {
  motor_id: string;
  motor_status: MotorStatus;
  current_a?: number | null;
  voltage_v?: number | null;
  power_kw?: number | null;
  rated_power_kw?: number | null;
  load_percentage?: number | null;
  power_factor?: number | null;
  is_power_factor_estimated: boolean;
  current_updated_at?: string | null;
  voltage_updated_at?: string | null;
  status: ElectricalSafetyStatus;
  is_safe: boolean;
  should_trip: boolean;
  trip_reason?: string | null;
  details?: Record<string, any>;
}

// Phase 17: Schedule Definitions & Execution
export interface ScheduleResponse {
  id: string;
  station_id: string;
  motor_id?: string | null;
  name: string;
  days_of_week: string[];
  start_time: string;
  duration_seconds: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ScheduleCreateRequest {
  station_id: string;
  motor_id: string;
  name: string;
  days_of_week: string[];
  start_time: string;
  duration_seconds: number;
  is_active?: boolean;
}

export interface ScheduleUpdateRequest {
  name?: string;
  days_of_week?: string[];
  start_time?: string;
  duration_seconds?: number;
  is_active?: boolean;
}

// Phase 18 & 20: Motor & Station Event History
export type MotorEventType =
  | 'STARTED'
  | 'STOPPED'
  | 'FAULT'
  | 'RESET'
  | 'EMERGENCY_STOP'
  | 'OFFLINE'
  | 'ONLINE'
  | 'COMMUNICATION_LOST';

export type MotorEventSource = 'USER' | 'AUTOMATION' | 'CONTROLLER' | 'SYSTEM';

export interface MotorEventResponse {
  id: string;
  motor_id: string;
  event_type: MotorEventType;
  source: MotorEventSource;
  description?: string | null;
  event_payload?: Record<string, any> | null;
  occurred_at: string;
  created_at: string;
}

// Phase 19: Audit Logging
export type AuditAction =
  | 'CREATE'
  | 'UPDATE'
  | 'DELETE'
  | 'LOGIN'
  | 'LOGOUT'
  | 'START'
  | 'STOP'
  | 'RESET'
  | 'EMERGENCY_STOP'
  | 'CONFIGURE'
  | 'ENABLE'
  | 'DISABLE'
  | 'ACKNOWLEDGE'
  | 'EXPORT'
  | 'IMPORT'
  | 'OTHER';

export type AuditActorType = 'USER' | 'SYSTEM' | 'CONTROLLER' | 'AUTOMATION';

export interface AuditLogResponse {
  id: string;
  organization_id?: string | null;
  site_id?: string | null;
  station_id?: string | null;
  actor_user_id?: string | null;
  actor_type: AuditActorType;
  action: AuditAction;
  resource_type: string;
  resource_id?: string | null;
  action_description: string;
  audit_metadata?: Record<string, any> | null;
  ip_address?: string | null;
  user_agent?: string | null;
  occurred_at: string;
  created_at: string;
}
