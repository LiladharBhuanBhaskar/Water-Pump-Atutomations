/**
 * HydraControl — REST API Client Service
 * Encapsulates type-safe HTTP communication with the backend API.
 * Injects JWT Bearer tokens and handles error parsing.
 */

import {
  User,
  Organization,
  Site,
  Station,
  Controller,
  Motor,
  Sensor,
  MotorCommand,
  StationSettingsResponse,
  StationSettingsUpdate,
  AutomationRuleResponse,
  AutomationRuleCreate,
  AutomationRuleUpdate,
  WaterQualityResponse,
  FlowDiagnosticsResponse,
  ElectricalMetricsResponse,
  ScheduleResponse,
  ScheduleCreateRequest,
  ScheduleUpdateRequest,
  MotorEventResponse,
  AuditLogResponse,
  OrganizationFleetSummary,
  NotificationPreference,
  NotificationPreferenceUpdate,
  NotificationDispatchResult,
  DeviceRegistrationRequest,
  DeviceRegistrationResponse,
  DeviceLivenessResponse,
  MotorTimerStatus,
} from '../types';

export const DEFAULT_CLOUDFLARE_URL =
  ((import.meta as any).env?.VITE_API_BASE_URL as string) ||
  'https://repository-fighters-voting-bingo.trycloudflare.com';

export function isNativeCapacitorApp(): boolean {
  if (typeof window === 'undefined') return false;

  // 1. Check Capacitor global object
  if (typeof (window as any).Capacitor !== 'undefined') {
    const platform = (window as any).Capacitor.getPlatform?.();
    if (platform === 'android' || platform === 'ios') return true;
    if ((window as any).Capacitor.isNativePlatform?.()) return true;
  }

  // 2. Protocol checks
  if (window.location.protocol === 'capacitor:' || window.location.protocol === 'file:') {
    return true;
  }

  // 3. Android Capacitor WebView serves from https://localhost or http://localhost with NO port
  const isLocalhostNoPort =
    (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') &&
    (window.location.port === '' || window.location.port === '80' || window.location.port === '443');

  if (isLocalhostNoPort && window.location.port !== '5173') {
    return true;
  }

  return false;
}

export function getServerBaseUrl(): string {
  // Check if custom server URL is saved
  const savedUrl = localStorage.getItem('hydra_server_url') || localStorage.getItem('hydra_mobile_server_url') || localStorage.getItem('hydra_web_custom_server');
  if (savedUrl && savedUrl.trim()) {
    return savedUrl.trim().replace(/\/+$/, '');
  }

  // If running inside native Android / Capacitor container, default to Cloudflare remote URL
  if (isNativeCapacitorApp()) {
    return DEFAULT_CLOUDFLARE_URL;
  }

  // On standard Web browser on localhost, use relative proxy /api/v1 (or Cloudflare)
  return '';
}

export function getApiBaseUrl(): string {
  const server = getServerBaseUrl();
  return server ? `${server}/api/v1` : '/api/v1';
}

class ApiService {
  private getToken(): string | null {
    return localStorage.getItem('hydra_token');
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const apiBase = getApiBaseUrl();
    const response = await fetch(`${apiBase}${endpoint}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      // Clear token on 401 Unauthorized
      localStorage.removeItem('hydra_token');
      localStorage.removeItem('hydra_cached_user');
      window.dispatchEvent(new Event('auth:unauthorized'));
    }

    if (!response.ok) {
      let errorDetail = 'An unexpected error occurred';
      try {
        const errorJson = await response.json();
        errorDetail = errorJson.detail || errorJson.message || errorDetail;
      } catch {
        errorDetail = response.statusText || errorDetail;
      }
      throw new Error(errorDetail);
    }

    if (response.status === 204) {
      return {} as T;
    }

    return response.json();
  }

  // Authentication Endpoints
  async login(email: string, password: string): Promise<{ access_token: string; token_type: string; refresh_token?: string; user?: User }> {
    const apiBase = getApiBaseUrl();
    const response = await fetch(`${apiBase}/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email: email.trim(), password }),
    });

    if (!response.ok) {
      let errorDetail = 'Invalid credentials';
      try {
        const errorJson = await response.json();
        errorDetail = errorJson.detail || errorDetail;
      } catch {
        // fallback
      }
      throw new Error(errorDetail);
    }

    return response.json();
  }

  async getMe(): Promise<User> {
    return this.request<User>('/auth/me');
  }

  // Organization Endpoints
  async getOrganizations(): Promise<Organization[]> {
    return this.request<Organization[]>('/organizations');
  }

  // Site Endpoints
  async getSites(orgId?: string): Promise<Site[]> {
    const qs = orgId ? `?organization_id=${orgId}` : '';
    return this.request<Site[]>(`/sites${qs}`);
  }

  // Station Endpoints
  async getStations(siteId?: string): Promise<Station[]> {
    const qs = siteId ? `?site_id=${siteId}` : '';
    return this.request<Station[]>(`/stations${qs}`);
  }

  // Station Settings Endpoints
  async getStationSettings(stationId: string): Promise<StationSettingsResponse> {
    return this.request<StationSettingsResponse>(`/stations/${stationId}/settings`);
  }

  async updateStationSettings(stationId: string, data: StationSettingsUpdate): Promise<StationSettingsResponse> {
    return this.request<StationSettingsResponse>(`/stations/${stationId}/settings`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  // Automation Rules Endpoints
  async getAutomationRules(stationId: string, status?: string): Promise<AutomationRuleResponse[]> {
    const qs = status ? `&status=${status}` : '';
    return this.request<AutomationRuleResponse[]>(`/automation-rules?station_id=${stationId}${qs}`);
  }

  async createAutomationRule(data: AutomationRuleCreate): Promise<AutomationRuleResponse> {
    return this.request<AutomationRuleResponse>('/automation-rules', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateAutomationRule(ruleId: string, data: AutomationRuleUpdate): Promise<AutomationRuleResponse> {
    return this.request<AutomationRuleResponse>(`/automation-rules/${ruleId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteAutomationRule(ruleId: string): Promise<void> {
    return this.request<void>(`/automation-rules/${ruleId}`, {
      method: 'DELETE',
    });
  }

  // Station Water Quality Diagnostics
  async getWaterQuality(stationId: string): Promise<WaterQualityResponse> {
    return this.request<WaterQualityResponse>(`/stations/${stationId}/water-quality`);
  }

  // Controller Endpoints
  async getControllers(stationId?: string): Promise<Controller[]> {
    const qs = stationId ? `?station_id=${stationId}` : '';
    return this.request<Controller[]>(`/controllers${qs}`);
  }

  // Motor Endpoints
  async getMotors(controllerId?: string): Promise<Motor[]> {
    const qs = controllerId ? `?controller_id=${controllerId}` : '';
    return this.request<Motor[]>(`/motors${qs}`);
  }

  async getMotor(motorId: string): Promise<Motor> {
    return this.request<Motor>(`/motors/${motorId}`);
  }

  async startMotor(motorId: string, payload?: Record<string, any>): Promise<MotorCommand> {
    return this.request<MotorCommand>(`/motors/${motorId}/start`, {
      method: 'POST',
      body: payload ? JSON.stringify({ payload }) : undefined,
    });
  }

  async stopMotor(motorId: string): Promise<MotorCommand> {
    return this.request<MotorCommand>(`/motors/${motorId}/stop`, {
      method: 'POST',
    });
  }

  async emergencyStopMotor(motorId: string): Promise<MotorCommand> {
    return this.request<MotorCommand>(`/motors/${motorId}/emergency-stop`, {
      method: 'POST',
    });
  }

  async resetMotor(motorId: string): Promise<MotorCommand> {
    return this.request<MotorCommand>(`/motors/${motorId}/reset`, {
      method: 'POST',
    });
  }

  async getMotorCommands(motorId: string): Promise<MotorCommand[]> {
    return this.request<MotorCommand[]>(`/motors/${motorId}/commands`);
  }

  async getMotorTimer(motorId: string): Promise<MotorTimerStatus> {
    return this.request<MotorTimerStatus>(`/motors/${motorId}/timer`);
  }

  async continueMotorTimer(motorId: string, extendSeconds: number = 900): Promise<MotorTimerStatus> {
    return this.request<MotorTimerStatus>(`/motors/${motorId}/timer/continue`, {
      method: 'POST',
      body: JSON.stringify({ extend_seconds: extendSeconds }),
    });
  }

  async getFlowDiagnostics(motorId: string): Promise<FlowDiagnosticsResponse> {
    return this.request<FlowDiagnosticsResponse>(`/motors/${motorId}/flow-diagnostics`);
  }

  async getElectricalMetrics(motorId: string): Promise<ElectricalMetricsResponse> {
    return this.request<ElectricalMetricsResponse>(`/motors/${motorId}/electrical-metrics`);
  }

  // Sensor Endpoints
  async getSensors(controllerId?: string): Promise<Sensor[]> {
    const qs = controllerId ? `?controller_id=${controllerId}` : '';
    return this.request<Sensor[]>(`/sensors${qs}`);
  }

  async getSensorTelemetry(
    sensorId: string,
    params?: { start_time?: string; end_time?: string; limit?: number; offset?: number }
  ): Promise<any[]> {
    const query = new URLSearchParams();
    if (params?.start_time) query.append('start_time', params.start_time);
    if (params?.end_time) query.append('end_time', params.end_time);
    if (params?.limit) query.append('limit', params.limit.toString());
    if (params?.offset) query.append('offset', params.offset.toString());
    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.request<any[]>(`/sensors/${sensorId}/telemetry${qs}`);
  }

  async getSensorLatest(sensorId: string): Promise<any> {
    return this.request<any>(`/sensors/${sensorId}/latest`);
  }

  // Phase 17: Schedule Endpoints
  async getSchedules(stationId: string): Promise<ScheduleResponse[]> {
    return this.request<ScheduleResponse[]>(`/stations/${stationId}/schedules`);
  }

  async createSchedule(stationId: string, data: ScheduleCreateRequest): Promise<ScheduleResponse> {
    return this.request<ScheduleResponse>(`/stations/${stationId}/schedules`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateSchedule(
    stationId: string,
    scheduleId: string,
    data: ScheduleUpdateRequest
  ): Promise<ScheduleResponse> {
    return this.request<ScheduleResponse>(`/stations/${stationId}/schedules/${scheduleId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteSchedule(stationId: string, scheduleId: string): Promise<void> {
    return this.request<void>(`/stations/${stationId}/schedules/${scheduleId}`, {
      method: 'DELETE',
    });
  }

  // Phase 18 & 20: Event History Endpoints
  async getMotorEvents(
    motorId: string,
    params?: {
      start_time?: string;
      end_time?: string;
      event_type?: string;
      source?: string;
      limit?: number;
      offset?: number;
    }
  ): Promise<MotorEventResponse[]> {
    const query = new URLSearchParams();
    if (params?.start_time) query.append('start_time', params.start_time);
    if (params?.end_time) query.append('end_time', params.end_time);
    if (params?.event_type && params.event_type !== 'ALL') query.append('event_type', params.event_type);
    if (params?.source) query.append('source', params.source);
    if (params?.limit) query.append('limit', params.limit.toString());
    if (params?.offset) query.append('offset', params.offset.toString());
    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.request<MotorEventResponse[]>(`/motors/${motorId}/events${qs}`);
  }

  async getStationEvents(
    stationId: string,
    params?: {
      start_time?: string;
      end_time?: string;
      event_type?: string;
      source?: string;
      motor_id?: string;
      limit?: number;
      offset?: number;
    }
  ): Promise<MotorEventResponse[]> {
    const query = new URLSearchParams();
    if (params?.start_time) query.append('start_time', params.start_time);
    if (params?.end_time) query.append('end_time', params.end_time);
    if (params?.event_type && params.event_type !== 'ALL') query.append('event_type', params.event_type);
    if (params?.source) query.append('source', params.source);
    if (params?.motor_id) query.append('motor_id', params.motor_id);
    if (params?.limit) query.append('limit', params.limit.toString());
    if (params?.offset) query.append('offset', params.offset.toString());
    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.request<MotorEventResponse[]>(`/stations/${stationId}/events${qs}`);
  }

  // Phase 19: Audit Log Endpoints
  async getAuditLogs(
    params?: {
      start_time?: string;
      end_time?: string;
      action?: string;
      actor_user_id?: string;
      resource_type?: string;
      resource_id?: string;
      organization_id?: string;
      limit?: number;
      offset?: number;
    }
  ): Promise<AuditLogResponse[]> {
    const query = new URLSearchParams();
    if (params?.start_time) query.append('start_time', params.start_time);
    if (params?.end_time) query.append('end_time', params.end_time);
    if (params?.action) query.append('action', params.action);
    if (params?.actor_user_id) query.append('actor_user_id', params.actor_user_id);
    if (params?.resource_type) query.append('resource_type', params.resource_type);
    if (params?.resource_id) query.append('resource_id', params.resource_id);
    if (params?.organization_id) query.append('organization_id', params.organization_id);
    if (params?.limit) query.append('limit', params.limit.toString());
    if (params?.offset) query.append('offset', params.offset.toString());
    const qs = query.toString() ? `?${query.toString()}` : '';
    return this.request<AuditLogResponse[]>(`/audit-logs${qs}`);
  }

  // Phase 20: Fleet Summary Endpoints
  async getFleetSummary(organizationId: string): Promise<OrganizationFleetSummary> {
    return this.request<OrganizationFleetSummary>(`/organizations/${organizationId}/fleet-summary`);
  }

  // Phase 17: Notification Preferences Endpoints
  async getNotificationPreferences(): Promise<NotificationPreference> {
    return this.request<NotificationPreference>('/users/me/notification-preferences');
  }

  async updateNotificationPreferences(
    data: NotificationPreferenceUpdate
  ): Promise<NotificationPreference> {
    return this.request<NotificationPreference>('/users/me/notification-preferences', {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async sendTestNotification(): Promise<NotificationDispatchResult> {
    return this.request<NotificationDispatchResult>('/notifications/test', {
      method: 'POST',
    });
  }

  // Device Provisioning & Liveness Endpoints
  async getDeviceStatus(deviceUid: string): Promise<DeviceLivenessResponse> {
    return this.request<DeviceLivenessResponse>(`/devices/${deviceUid}/status`);
  }

  async registerDevice(data: DeviceRegistrationRequest): Promise<DeviceRegistrationResponse> {
    return this.request<DeviceRegistrationResponse>('/devices/register', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async triggerLivenessCheck(): Promise<any> {
    return this.request<any>('/devices/liveness-check', {
      method: 'POST',
    });
  }

  // Admin User & Subscription Management
  async getUsers(): Promise<User[]> {
    return this.request<User[]>('/users');
  }

  async createUser(data: any): Promise<User> {
    return this.request<User>('/users', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateUser(userId: string, data: any): Promise<User> {
    return this.request<User>(`/users/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async deleteUser(userId: string): Promise<void> {
    return this.request<void>(`/users/${userId}`, {
      method: 'DELETE',
    });
  }

  async getSubscriptionPlans(): Promise<any[]> {
    return this.request<any[]>('/users/subscriptions/plans');
  }

  async getCurrentSubscription(): Promise<any> {
    return this.request<any>('/users/subscriptions/current');
  }

  async updateSubscriptionPlan(data: any): Promise<any> {
    return this.request<any>('/users/subscriptions/current', {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }
}

export const api = new ApiService();


