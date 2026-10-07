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
} from '../types';

const API_BASE = '/api/v1';

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

    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      // Clear token on 401 Unauthorized
      localStorage.removeItem('hydra_token');
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
  async login(email: string, password: string): Promise<{ access_token: string; token_type: string }> {
    const response = await fetch(`${API_BASE}/auth/login`, {
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

  async getDeviceStatus(deviceUid: string): Promise<any> {
    return this.request(`/devices/${deviceUid}/status`);
  }

  // Motor Endpoints
  async getMotors(controllerId?: string): Promise<Motor[]> {
    const qs = controllerId ? `?controller_id=${controllerId}` : '';
    return this.request<Motor[]>(`/motors${qs}`);
  }

  async getMotor(motorId: string): Promise<Motor> {
    return this.request<Motor>(`/motors/${motorId}`);
  }

  async startMotor(motorId: string): Promise<MotorCommand> {
    return this.request<MotorCommand>(`/motors/${motorId}/start`, {
      method: 'POST',
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
}

export const api = new ApiService();

