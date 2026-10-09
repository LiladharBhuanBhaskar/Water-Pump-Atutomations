import React, { useState, useEffect, useCallback } from 'react';
import { 
  Building2, 
  MapPin, 
  Layers, 
  Cpu, 
  AlertCircle,
  RefreshCw,
  Radio,
  Sliders,
  Calendar,
  History,
} from 'lucide-react';
import {
  Site,
  Station,
  Controller,
  Motor,
  Sensor,
  MotorCommand,
  WsServerEvent,
  WaterQualityResponse,
  FlowDiagnosticsResponse,
  ElectricalMetricsResponse,
  StationSettingsResponse,
  MotorTimerStatus,
} from '../types';
import { api } from '../services/api';
import { ws } from '../services/ws';
import { TelemetryGauge } from '../components/TelemetryGauge';
import { SensorCard } from '../components/SensorCard';
import { MotorCard } from '../components/MotorCard';
import { TankSafetyCard } from '../components/TankSafetyCard';
import { WaterQualityCard } from '../components/WaterQualityCard';
import { FlowDiagnosticsCard } from '../components/FlowDiagnosticsCard';
import { ElectricalMetricsCard } from '../components/ElectricalMetricsCard';
import { SafetyAlertBanner, SafetyAlert } from '../components/SafetyAlertBanner';
import { StationSettingsModal } from '../components/StationSettingsModal';
import { ScheduleManagerModal } from '../components/ScheduleManagerModal';
import { EventHistoryModal } from '../components/EventHistoryModal';
import { FleetSummaryModal } from '../components/FleetSummaryModal';
import { audioAlert } from '../utils/audioAlert';
import { NotificationPreferencesModal } from '../components/NotificationPreferencesModal';
import { DeviceCommissioningModal } from '../components/DeviceCommissioningModal';
import { AuditLogsModal } from '../components/AuditLogsModal';
import { Spinner } from '../components/common/Spinner';
import { TelemetryFreshnessBadge } from '../components/common/TelemetryFreshnessBadge';
import { ControllerOfflineOverlay } from '../components/common/ControllerOfflineOverlay';
import { ErrorBoundary } from '../components/common/ErrorBoundary';
import { Bell, ShieldCheck } from 'lucide-react';

interface DashboardProps {
  latestWsEvent?: WsServerEvent | null;
}

export const Dashboard: React.FC<DashboardProps> = ({ latestWsEvent }) => {
  const [sites, setSites] = useState<Site[]>([]);
  const [selectedSiteId, setSelectedSiteId] = useState<string>('');
  const [stations, setStations] = useState<Station[]>([]);
  const [selectedStationId, setSelectedStationId] = useState<string>('');
  const [controllers, setControllers] = useState<Controller[]>([]);
  const [selectedControllerId, setSelectedControllerId] = useState<string>('');
  const [motors, setMotors] = useState<Motor[]>([]);
  const [sensors, setSensors] = useState<Sensor[]>([]);
  const [sensorReadings, setSensorReadings] = useState<Record<string, { value: number; unit: string; occurred_at: string; metadata?: any }>>({});
  const [activeCommands, setActiveCommands] = useState<Record<string, MotorCommand>>({});
  const [safetyAlerts, setSafetyAlerts] = useState<SafetyAlert[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Station Settings & Diagnostics State (Phase 12-15 Wave 2/3)
  const [stationSettings, setStationSettings] = useState<StationSettingsResponse | null>(null);
  const [waterQuality, setWaterQuality] = useState<WaterQualityResponse | null>(null);
  const [flowDiagnostics, setFlowDiagnostics] = useState<Record<string, FlowDiagnosticsResponse>>({});
  const [electricalMetrics, setElectricalMetrics] = useState<Record<string, ElectricalMetricsResponse>>({});
  const [motorTimers, setMotorTimers] = useState<Record<string, MotorTimerStatus>>({});
  const [timerRemainingSeconds, setTimerRemainingSeconds] = useState<Record<string, number>>({});
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState<boolean>(false);

  // Synchronized countdown ticker
  useEffect(() => {
    const updateTicker = () => {
      const now = Date.now();
      const updated: Record<string, number> = {};
      for (const [mId, t] of Object.entries(motorTimers)) {
        if (t && t.end_time) {
          const target = new Date(t.end_time).getTime();
          updated[mId] = Math.max(0, Math.floor((target - now) / 1000));
        } else {
          updated[mId] = 0;
        }
      }
      setTimerRemainingSeconds(updated);
    };
    updateTicker();
    const interval = setInterval(updateTicker, 1000);
    return () => clearInterval(interval);
  }, [motorTimers]);

  // Phase 17 & Phase 20 State
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState<boolean>(false);
  const [isEventHistoryModalOpen, setIsEventHistoryModalOpen] = useState<boolean>(false);
  const [selectedHistoryMotor, setSelectedHistoryMotor] = useState<Motor | null>(null);

  // Enterprise & Hardware Modals State
  const [isFleetModalOpen, setIsFleetModalOpen] = useState<boolean>(false);
  const [isNotificationModalOpen, setIsNotificationModalOpen] = useState<boolean>(false);
  const [isCommissionModalOpen, setIsCommissionModalOpen] = useState<boolean>(false);
  const [isAuditModalOpen, setIsAuditModalOpen] = useState<boolean>(false);

  // Live Telemetry state for primary summary gauge
  const [telemetry, setTelemetry] = useState<{
    waterLevel?: number;
    turbidity?: number;
    flowRate?: number;
    current?: number;
    voltage?: number;
    pressure?: number;
    lastUpdated?: string;
  }>({
    waterLevel: 65.0,
    turbidity: 12.5,
    flowRate: 0.0,
    current: 0.0,
    voltage: 230.0,
    pressure: 0.0,
  });

  // Load Sites on mount
  const loadSites = useCallback(async () => {
    try {
      setError(null);
      const siteList = await api.getSites();
      setSites(siteList);
      if (siteList.length > 0) {
        setSelectedSiteId((prev) => prev || siteList[0].id);
      }
    } catch (err: any) {
      setError(err.message || 'Failed loading sites.');
    }
  }, []);

  useEffect(() => {
    loadSites();
  }, [loadSites]);

  // Load Stations when Site changes
  useEffect(() => {
    if (!selectedSiteId) return;

    const loadStations = async () => {
      try {
        const stationList = await api.getStations(selectedSiteId);
        setStations(stationList);
        if (stationList.length > 0) {
          setSelectedStationId(stationList[0].id);
        } else {
          setSelectedStationId('');
          setControllers([]);
          setMotors([]);
          setSensors([]);
          setWaterQuality(null);
        }
      } catch (err: any) {
        console.error('Failed loading stations:', err);
      }
    };

    loadStations();
  }, [selectedSiteId]);

  // Load Station Diagnostics (Water Quality & Settings) when Station changes
  const loadStationDiagnostics = useCallback(async (stationId: string) => {
    if (!stationId) return;
    try {
      const [wq, settings] = await Promise.allSettled([
        api.getWaterQuality(stationId),
        api.getStationSettings(stationId),
      ]);
      if (wq.status === 'fulfilled') {
        setWaterQuality(wq.value);
      }
      if (settings.status === 'fulfilled') {
        setStationSettings(settings.value);
      }
    } catch (err) {
      console.error('Failed loading station diagnostics:', err);
    }
  }, []);

  useEffect(() => {
    if (selectedStationId) {
      loadStationDiagnostics(selectedStationId);
    }
  }, [selectedStationId, loadStationDiagnostics]);

  // Load Controllers when Station changes
  useEffect(() => {
    if (!selectedStationId) return;

    const loadControllers = async () => {
      try {
        const controllerList = await api.getControllers(selectedStationId);
        setControllers(controllerList);
        if (controllerList.length > 0) {
          setSelectedControllerId(controllerList[0].id);
        } else {
          setSelectedControllerId('');
          setMotors([]);
          setSensors([]);
        }
      } catch (err: any) {
        console.error('Failed loading controllers:', err);
      }
    };

    loadControllers();
  }, [selectedStationId]);

  // Load Hierarchy Details (Motors, Dynamic Sensors, Flow Diagnostics & Electrical Metrics)
  const loadHierarchyDetails = useCallback(async () => {
    if (!selectedControllerId) {
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const [motorList, sensorList] = await Promise.all([
        api.getMotors(selectedControllerId),
        api.getSensors(selectedControllerId),
      ]);
      setMotors(motorList);
      setSensors(sensorList);

      // Subscribe to motor and device channels
      const activeCtrl = controllers.find((c) => c.id === selectedControllerId);
      const subChannels = motorList.map((m) => `motor:${m.id}`);
      if (activeCtrl) {
        subChannels.push(`device:${activeCtrl.device_uid}`);
      }
      if (selectedSiteId) {
        subChannels.push(`site:${selectedSiteId}`);
      }
      if (selectedStationId) {
        subChannels.push(`station:${selectedStationId}`);
      }
      ws.subscribeChannels(subChannels);

      // Fetch latest telemetry for each registered sensor
      for (const s of sensorList) {
        try {
          const latest = await api.getSensorLatest(s.id);
          if (latest) {
            setSensorReadings((prev) => ({
              ...prev,
              [s.sensor_code.toUpperCase()]: {
                value: latest.value,
                unit: latest.unit,
                occurred_at: latest.occurred_at,
                metadata: latest.metadata,
              },
              [s.id]: {
                value: latest.value,
                unit: latest.unit,
                occurred_at: latest.occurred_at,
                metadata: latest.metadata,
              },
            }));
          }
        } catch {
          // ignore if no initial readings exist
        }
      }

      // Load latest command history and diagnostics for each motor
      for (const m of motorList) {
        try {
          const [cmds, flowDiag, elecMetrics] = await Promise.allSettled([
            api.getMotorCommands(m.id),
            api.getFlowDiagnostics(m.id),
            api.getElectricalMetrics(m.id),
          ]);
          if (cmds.status === 'fulfilled' && cmds.value.length > 0) {
            setActiveCommands((prev) => ({
              ...prev,
              [m.id]: cmds.value[0],
            }));
          }
          if (flowDiag.status === 'fulfilled') {
            setFlowDiagnostics((prev) => ({
              ...prev,
              [m.id]: flowDiag.value,
            }));
          }
          if (elecMetrics.status === 'fulfilled') {
            setElectricalMetrics((prev) => ({
              ...prev,
              [m.id]: elecMetrics.value,
            }));
          }

          // Fetch active schedule timer status if motor is ON
          if (m.status === 'ON') {
            api.getMotorTimer(m.id).then((timer) => {
              if (timer && timer.is_running) {
                setMotorTimers((prev) => ({ ...prev, [m.id]: timer }));
              }
            }).catch(() => {});
          }
        } catch {
          // ignore
        }
      }
    } catch (err: any) {
      setError(err.message || 'Failed loading station devices.');
    } finally {
      setLoading(false);
    }
  }, [selectedControllerId, controllers, selectedSiteId, selectedStationId]);

  useEffect(() => {
    loadHierarchyDetails();
  }, [loadHierarchyDetails]);

  // Handle incoming real-time WebSocket events
  useEffect(() => {
    if (!latestWsEvent) return;

    if (latestWsEvent.event === 'TELEMETRY') {
      const { sensor_id, sensor_code, value, unit, occurred_at, metadata } = latestWsEvent;
      const codeUpper = sensor_code.toUpperCase();

      // Update dynamic sensor readings map
      setSensorReadings((prev) => ({
        ...prev,
        [codeUpper]: { value, unit, occurred_at, metadata },
        [sensor_id]: { value, unit, occurred_at, metadata },
      }));

      // Update summary gauge and diagnostic values
      setTelemetry((prev) => {
        const updated = { ...prev, lastUpdated: occurred_at };
        if (codeUpper.includes('LEVEL') || codeUpper.includes('LVL') || codeUpper.includes('TANK')) {
          updated.waterLevel = value;
        } else if (codeUpper.includes('TURBID') || codeUpper.includes('NTU')) {
          updated.turbidity = value;
          setWaterQuality((prevWq) =>
            prevWq
              ? {
                  ...prevWq,
                  turbidity_ntu: value,
                  turbidity_updated_at: occurred_at,
                  is_safe: value <= (prevWq.threshold_used ?? 5.0),
                  status: value > (prevWq.threshold_used ?? 5.0) ? 'UNSAFE' : 'SAFE',
                }
              : null
          );
        } else if (codeUpper.includes('FLOW')) {
          updated.flowRate = value;
        } else if (codeUpper.includes('CURR') || codeUpper.includes('AMP')) {
          updated.current = value;
        } else if (codeUpper.includes('VOLT')) {
          updated.voltage = value;
        } else if (codeUpper.includes('PRESS') || codeUpper.includes('BAR')) {
          updated.pressure = value;
        }
        return updated;
      });
    } else if (latestWsEvent.event === 'MOTOR_STATE') {
      const { motor_id, status } = latestWsEvent;
      setMotors((prev) =>
        prev.map((m) => (m.id === motor_id ? { ...m, status } : m))
      );
      // Update diagnostics motor status
      setFlowDiagnostics((prev) =>
        prev[motor_id] ? { ...prev, [motor_id]: { ...prev[motor_id], motor_status: status } } : prev
      );
      setElectricalMetrics((prev) =>
        prev[motor_id] ? { ...prev, [motor_id]: { ...prev[motor_id], motor_status: status } } : prev
      );
      if (status === 'ON') {
        api.getMotorTimer(motor_id).then((timer) => {
          if (timer && timer.is_running) {
            setMotorTimers((prev) => ({ ...prev, [motor_id]: timer }));
          }
        }).catch(() => {});
      } else {
        setMotorTimers((prev) => {
          const next = { ...prev };
          delete next[motor_id];
          return next;
        });
      }
    } else if (latestWsEvent.event === 'COMMAND_LIFECYCLE') {
      const { command_id, motor_id, command_type, status, error_message, timestamp } = latestWsEvent;
      setActiveCommands((prev) => ({
        ...prev,
        [motor_id]: {
          id: command_id,
          motor_id,
          command_type,
          status,
          error_message,
          requested_at: timestamp,
        },
      }));
    } else if (latestWsEvent.event === 'NOTIFICATION_RECEIVED') {
      audioAlert.playBuzzer(latestWsEvent.notification_id, latestWsEvent.severity);
      const newAlert: SafetyAlert = {
        id: latestWsEvent.notification_id || `${latestWsEvent.timestamp}-${Math.random()}`,
        eventType: latestWsEvent.event_type || 'NOTIFICATION',
        motorCode: latestWsEvent.motor_id ? 'MOTOR' : 'STATION',
        deviceUid: '',
        stationId: latestWsEvent.station_id || selectedStationId,
        description: `${latestWsEvent.title}: ${latestWsEvent.message}`,
        timestamp: latestWsEvent.timestamp,
      };
      setSafetyAlerts((prev) => [newAlert, ...prev.slice(0, 5)]);

      if (latestWsEvent.motor_id) {
        if (latestWsEvent.event_type === 'SCHEDULE_STARTED') {
          setMotors((prev) =>
            prev.map((m) => (m.id === latestWsEvent.motor_id ? { ...m, status: 'ON' } : m))
          );
        } else if (latestWsEvent.event_type === 'SCHEDULE_STOPPED' || latestWsEvent.event_type === 'TIMER_EXPIRED') {
          setMotors((prev) =>
            prev.map((m) => (m.id === latestWsEvent.motor_id ? { ...m, status: 'OFF' } : m))
          );
        }
      }

      if (latestWsEvent.motor_id && (latestWsEvent.event_type?.includes('TIMER') || latestWsEvent.event_type?.includes('SCHEDULE'))) {
        api.getMotorTimer(latestWsEvent.motor_id).then((t) => {
          if (t && t.is_running) {
            setMotorTimers((prev) => ({ ...prev, [latestWsEvent.motor_id!]: t }));
          }
        }).catch(() => {});
      }

      if (selectedStationId && (latestWsEvent.event_type?.includes('SCHEDULE') || latestWsEvent.event_type?.includes('TIMER'))) {
        loadHierarchyDetails();
      }
    } else if (latestWsEvent.event === 'SAFETY_ALERT') {
      audioAlert.playBuzzer(latestWsEvent.timestamp, 'CRITICAL');
      const newAlert: SafetyAlert = {
        id: `${latestWsEvent.timestamp}-${Math.random()}`,
        eventType: latestWsEvent.event_type,
        motorCode: latestWsEvent.motor_code,
        deviceUid: latestWsEvent.device_uid,
        stationId: latestWsEvent.station_id || selectedStationId,
        description: latestWsEvent.description || 'Safety cutoff activated by hardware.',
        timestamp: latestWsEvent.timestamp,
      };
      setSafetyAlerts((prev) => [newAlert, ...prev.slice(0, 5)]);

      // If alert affects a motor, update diagnostic evaluations
      if (latestWsEvent.motor_id) {
        if (latestWsEvent.event_type === 'DRY_RUN_TRIP') {
          setFlowDiagnostics((prev) =>
            prev[latestWsEvent.motor_id]
              ? {
                  ...prev,
                  [latestWsEvent.motor_id]: {
                    ...prev[latestWsEvent.motor_id],
                    status: 'DRY_RUN',
                    is_safe: false,
                    should_trip: true,
                    trip_reason: latestWsEvent.description,
                  },
                }
              : prev
          );
        } else if (latestWsEvent.event_type === 'OVERLOAD_TRIP') {
          setElectricalMetrics((prev) =>
            prev[latestWsEvent.motor_id]
              ? {
                  ...prev,
                  [latestWsEvent.motor_id]: {
                    ...prev[latestWsEvent.motor_id],
                    status: 'OVERCURRENT',
                    is_safe: false,
                    should_trip: true,
                    trip_reason: latestWsEvent.description,
                  },
                }
              : prev
          );
        }
      }
    }
  }, [latestWsEvent, selectedStationId, loadHierarchyDetails]);

  // Motor Control Handlers
  const handleStartMotor = async (motorId: string) => {
    try {
      const cmd = await api.startMotor(motorId);
      setActiveCommands((prev) => ({
        ...prev,
        [motorId]: cmd,
      }));
    } catch (err: any) {
      alert(`Start failed: ${err.message}`);
    }
  };

  const handleStopMotor = async (motorId: string) => {
    try {
      const cmd = await api.stopMotor(motorId);
      setActiveCommands((prev) => ({
        ...prev,
        [motorId]: cmd,
      }));
    } catch (err: any) {
      alert(`Stop failed: ${err.message}`);
    }
  };

  const handleEmergencyStopMotor = async (motorId: string) => {
    try {
      const cmd = await api.emergencyStopMotor(motorId);
      setActiveCommands((prev) => ({
        ...prev,
        [motorId]: cmd,
      }));
    } catch (err: any) {
      alert(`Emergency Stop failed: ${err.message}`);
    }
  };

  const handleResetMotor = async (motorId: string) => {
    try {
      const cmd = await api.resetMotor(motorId);
      setActiveCommands((prev) => ({
        ...prev,
        [motorId]: cmd,
      }));
    } catch (err: any) {
      alert(`Reset failed: ${err.message}`);
    }
  };

  const activeSite = sites.find((s) => s.id === selectedSiteId);
  const activeStation = stations.find((s) => s.id === selectedStationId);
  const activeController = controllers.find((c) => c.id === selectedControllerId);

  // Derive overhead & sump tank values from sensor readings or telemetry
  const overheadLevel =
    sensorReadings['TANK_LEVEL_OVERHEAD']?.value ??
    sensorReadings['WATER_LEVEL']?.value ??
    telemetry.waterLevel ??
    75;
  const sumpLevel =
    sensorReadings['TANK_LEVEL_SUMP']?.value ??
    sensorReadings['SUMP_LEVEL']?.value ??
    82;

  const isTankFull = overheadLevel >= (stationSettings?.water_level_threshold ?? 95);
  const isSourceDepleted = sumpLevel < 15;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Top Breadcrumb & Hierarchy Filter Controls */}
      <div className="glass-panel p-4 rounded-2xl flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-3">
          {/* Site Selector */}
          <div className="flex items-center gap-2 bg-slate-900/80 px-3 py-1.5 rounded-xl border border-slate-800">
            <Building2 className="w-4 h-4 text-cyan-400" />
            <span className="text-xs text-slate-400 font-medium">Site:</span>
            <select
              value={selectedSiteId}
              onChange={(e) => setSelectedSiteId(e.target.value)}
              className="bg-transparent text-xs font-bold text-white focus:outline-none cursor-pointer"
            >
              {sites.map((s) => (
                <option key={s.id} value={s.id} className="bg-slate-900 text-white">
                  {s.name} ({s.site_code})
                </option>
              ))}
            </select>
          </div>

          {/* Station Selector */}
          <div className="flex items-center gap-2 bg-slate-900/80 px-3 py-1.5 rounded-xl border border-slate-800">
            <Layers className="w-4 h-4 text-blue-400" />
            <span className="text-xs text-slate-400 font-medium">Station:</span>
            <select
              value={selectedStationId}
              onChange={(e) => setSelectedStationId(e.target.value)}
              disabled={stations.length === 0}
              className="bg-transparent text-xs font-bold text-white focus:outline-none cursor-pointer disabled:opacity-50"
            >
              {stations.map((st) => (
                <option key={st.id} value={st.id} className="bg-slate-900 text-white">
                  {st.name} ({st.station_code})
                </option>
              ))}
            </select>
          </div>

          {/* Controller Selector */}
          {controllers.length > 0 && (
            <div className="flex items-center gap-2 bg-slate-900/80 px-3 py-1.5 rounded-xl border border-slate-800">
              <Cpu className="w-4 h-4 text-purple-400" />
              <span className="text-xs text-slate-400 font-medium">Controller:</span>
              <select
                value={selectedControllerId}
                onChange={(e) => setSelectedControllerId(e.target.value)}
                className="bg-transparent text-xs font-bold text-white focus:outline-none cursor-pointer"
              >
                {controllers.map((ctrl) => (
                  <option key={ctrl.id} value={ctrl.id} className="bg-slate-900 text-white">
                    {ctrl.name} ({ctrl.device_uid})
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {activeStation && (
            <>
              <button
                onClick={() => setIsScheduleModalOpen(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-cyan-400 text-xs font-bold border border-slate-700 transition-colors"
                title="Automated Schedules & Timers"
              >
                <Calendar className="w-3.5 h-3.5" />
                <span>Schedules</span>
              </button>

              <button
                onClick={() => {
                  setSelectedHistoryMotor(null);
                  setIsEventHistoryModalOpen(true);
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-cyan-400 text-xs font-bold border border-slate-700 transition-colors"
                title="Station-Wide Event History"
              >
                <History className="w-3.5 h-3.5" />
                <span>Events</span>
              </button>

              <button
                onClick={() => setIsSettingsModalOpen(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-cyan-400 text-xs font-bold border border-slate-700 transition-colors"
                title="Station Settings & Automation Rules"
              >
                <Sliders className="w-3.5 h-3.5" />
                <span>Rules & Settings</span>
              </button>

              <button
                onClick={() => setIsCommissionModalOpen(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-emerald-400 text-xs font-bold border border-slate-700 transition-colors"
                title="Commission & Pair IoT Device"
              >
                <Cpu className="w-3.5 h-3.5" />
                <span>Pair Device</span>
              </button>
            </>
          )}

          {/* Enterprise Global Modals */}
          {activeSite && (
            <button
              onClick={() => setIsFleetModalOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-teal-950/60 hover:bg-teal-900/80 text-teal-300 text-xs font-bold border border-teal-800/80 transition-colors"
              title="Enterprise Multi-Site Fleet Summary"
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Fleet</span>
            </button>
          )}

          <button
            onClick={() => setIsAuditModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold border border-slate-700 transition-colors"
            title="Compliance Audit Logs"
          >
            <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" />
            <span>Audit</span>
          </button>

          <button
            onClick={() => setIsNotificationModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold border border-slate-700 transition-colors"
            title="Notification Channel Preferences"
          >
            <Bell className="w-3.5 h-3.5 text-amber-400" />
            <span>Alerts</span>
          </button>

          <button
            onClick={() => {
              loadHierarchyDetails();
              if (selectedStationId) loadStationDiagnostics(selectedStationId);
            }}
            title="Refresh station state"
            className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Safety Alert Banners */}
      <SafetyAlertBanner
        alerts={safetyAlerts}
        onDismiss={(id) => setSafetyAlerts((prev) => prev.filter((a) => a.id !== id))}
      />

      {/* Error Message if any */}
      {error && (
        <div className="p-4 rounded-2xl bg-rose-950/80 border border-rose-800/80 text-rose-300 text-xs flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Station Overview Header */}
      {activeStation && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 text-xs font-bold mb-2">
              <MapPin className="w-3.5 h-3.5" />
              {activeSite?.name} &bull; {activeStation.station_type}
            </div>
            <h2 className="text-2xl font-extrabold text-white tracking-tight">
              {activeStation.name}
            </h2>
          </div>

          <div className="text-xs text-slate-400 flex items-center gap-2">
            <span>Operational Mode:</span>
            <span className="font-bold text-emerald-400">Autonomous Edge Safety Active</span>
          </div>
        </div>
      )}

      {/* Controller Offline Warning if applicable */}
      {activeController && activeController.status !== 'ACTIVE' && (
        <ControllerOfflineOverlay controller={activeController} />
      )}

      {/* WAVE 3A: Station Safety Tier (Tank Safety & Water Quality) */}
      <ErrorBoundary fallbackTitle="Station Safety Tier Error">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold text-white uppercase tracking-wider text-xs text-slate-400">
              Station Safety & Environmental Diagnostics
            </h3>
            <TelemetryFreshnessBadge occurredAt={telemetry.lastUpdated} />
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* 1. Tank Safety Card */}
            <TankSafetyCard
              overheadLevel={overheadLevel}
              sumpLevel={sumpLevel}
              overheadThreshold={stationSettings?.water_level_threshold ?? 95}
              sumpThreshold={15}
              isTankFull={isTankFull}
              isSourceDepleted={isSourceDepleted}
              motorStatus={motors[0]?.status}
              lastUpdated={telemetry.lastUpdated}
            />

            {/* 2. Water Quality Card */}
            <WaterQualityCard
              data={waterQuality}
              onRefresh={() => selectedStationId && loadStationDiagnostics(selectedStationId)}
            />
          </div>
        </div>
      </ErrorBoundary>

      {/* Primary Summary Gauges */}
      <ErrorBoundary fallbackTitle="Telemetry Gauges Error">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold text-white uppercase tracking-wider text-xs text-slate-400">
              Primary Station Telemetry
            </h3>
            <TelemetryFreshnessBadge occurredAt={telemetry.lastUpdated} />
          </div>
          <TelemetryGauge telemetry={telemetry} />
        </div>
      </ErrorBoundary>

      {/* Motors & Pumps Section with Flow Diagnostics & Electrical Metrics */}
      <ErrorBoundary fallbackTitle="Pump Controls & Diagnostics Error">
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold text-white uppercase tracking-wider text-xs text-slate-400">
              Pump & Motor Operational Controls & Diagnostics
            </h3>
          </div>

          {loading ? (
            <div className="py-12 flex justify-center">
              <Spinner size="lg" label="Loading station pumps..." />
            </div>
          ) : motors.length === 0 ? (
            <div className="glass-panel p-8 rounded-3xl text-center text-slate-400 text-sm">
              No motors currently mapped to this controller.
            </div>
          ) : (
            <div className="space-y-8">
              {motors.map((motor) => (
                <div key={motor.id} className="space-y-4 p-6 rounded-3xl bg-slate-950/40 border border-slate-800/80">
                  {/* Motor Controls */}
                  <MotorCard
                    motor={motor}
                    activeCommand={activeCommands[motor.id]}
                    timerRemainingSeconds={timerRemainingSeconds[motor.id]}
                    onStart={handleStartMotor}
                    onStop={handleStopMotor}
                    onEmergencyStop={handleEmergencyStopMotor}
                    onReset={handleResetMotor}
                    disabledReason={
                      activeController && activeController.status !== 'ACTIVE'
                        ? `Controller is ${activeController.status}`
                        : null
                    }
                    onViewEvents={(m) => {
                      setSelectedHistoryMotor(m);
                      setIsEventHistoryModalOpen(true);
                    }}
                  />

                  {/* Motor Diagnostics Tier: Flow Protection & Electrical Metrics */}
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pt-2">
                    <FlowDiagnosticsCard
                      motorName={motor.name}
                      data={flowDiagnostics[motor.id]}
                      onRefresh={async () => {
                        try {
                          const diag = await api.getFlowDiagnostics(motor.id);
                          setFlowDiagnostics((prev) => ({ ...prev, [motor.id]: diag }));
                        } catch (e) {
                          console.error(e);
                        }
                      }}
                    />

                    <ElectricalMetricsCard
                      motorName={motor.name}
                      data={electricalMetrics[motor.id]}
                      onRefresh={async () => {
                        try {
                          const metrics = await api.getElectricalMetrics(motor.id);
                          setElectricalMetrics((prev) => ({ ...prev, [motor.id]: metrics }));
                        } catch (e) {
                          console.error(e);
                        }
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </ErrorBoundary>

      {/* Registered Dynamic Sensors Grid */}
      {sensors.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Radio className="w-4 h-4 text-cyan-400 animate-pulse" />
              <h3 className="text-base font-bold text-white uppercase tracking-wider text-xs text-slate-400">
                Connected Sensor Network ({sensors.length})
              </h3>
            </div>
            <span className="text-[11px] text-slate-500 font-mono">Generic Sensor Framework</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {sensors.map((sensor) => {
              const reading = sensorReadings[sensor.sensor_code.toUpperCase()] || sensorReadings[sensor.id];
              return (
                <SensorCard
                  key={sensor.id}
                  sensor={sensor}
                  latestReading={reading}
                />
              );
            })}
          </div>
        </div>
      )}

      {/* Station Settings & Automation Rules Modal */}
      {activeStation && (
        <StationSettingsModal
          station={activeStation}
          motors={motors}
          sensors={sensors}
          isOpen={isSettingsModalOpen}
          onClose={() => setIsSettingsModalOpen(false)}
        />
      )}

      {/* Schedule Definitions & Timers Modal (Phase 17) */}
      {activeStation && (
        <ScheduleManagerModal
          station={activeStation}
          motors={motors}
          isOpen={isScheduleModalOpen}
          onClose={() => setIsScheduleModalOpen(false)}
        />
      )}

      {/* Motor & Station Historical Events Modal (Phase 20) */}
      {activeStation && (
        <EventHistoryModal
          station={activeStation}
          motor={selectedHistoryMotor}
          isOpen={isEventHistoryModalOpen}
          onClose={() => {
            setIsEventHistoryModalOpen(false);
            setSelectedHistoryMotor(null);
          }}
        />
      )}

      {/* Enterprise Fleet Operational Summary Modal (Phase 20) */}
      {activeSite && (
        <FleetSummaryModal
          isOpen={isFleetModalOpen}
          onClose={() => setIsFleetModalOpen(false)}
          organizationId={activeSite.organization_id}
          organizationName={activeSite.name}
        />
      )}

      {/* Notification Preferences Modal (Phase 17) */}
      <NotificationPreferencesModal
        isOpen={isNotificationModalOpen}
        onClose={() => setIsNotificationModalOpen(false)}
      />

      {/* IoT Device Commissioning Wizard */}
      {activeStation && (
        <DeviceCommissioningModal
          isOpen={isCommissionModalOpen}
          onClose={() => setIsCommissionModalOpen(false)}
          station={activeStation}
          onDeviceCommissioned={() => {
            loadHierarchyDetails();
          }}
        />
      )}

      {/* Compliance Audit Logs Modal (Phase 19) */}
      <AuditLogsModal
        isOpen={isAuditModalOpen}
        onClose={() => setIsAuditModalOpen(false)}
        organizationId={activeSite?.organization_id || null}
      />
    </div>
  );
};
