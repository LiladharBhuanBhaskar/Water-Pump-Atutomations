import React, { useState, useEffect, useCallback } from 'react';
import {
  Waves,
  Droplet,
  Shield,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Calendar,
  LogOut,
  Bell,
  Cpu,
  Save,
  SlidersHorizontal,
  Crown,
  ChevronRight,
  BarChart2,
  Trash2,
  Timer,
  FastForward,
  Square,
  Plus,
  Sliders,
  RotateCcw,
} from 'lucide-react';
import {
  Site,
  Station,
  Controller,
  Motor,
  WsServerEvent,
  MotorEventResponse,
  ScheduleResponse,
  MotorTimerStatus,
} from '../types';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import { MobileNavDock, MobileTab } from '../components/MobileNavDock';
import { ScheduleManagerModal } from '../components/ScheduleManagerModal';
import { NotificationPreferencesModal } from '../components/NotificationPreferencesModal';
import { DeviceCommissioningModal } from '../components/DeviceCommissioningModal';
import { StartMotorModal } from '../components/StartMotorModal';
import { UserSubscriptionAdminModal } from '../components/UserSubscriptionAdminModal';
import { audioAlert } from '../utils/audioAlert';

// Dedicated Service Detail Screens
import { MotorSelectionScreen } from '../components/service-views/MotorSelectionScreen';
import { InterlocksScreen } from '../components/service-views/InterlocksScreen';
import { TankLevelScreen } from '../components/service-views/TankLevelScreen';
import { SumpLevelScreen } from '../components/service-views/SumpLevelScreen';
import { FlowRateScreen } from '../components/service-views/FlowRateScreen';
import { WaterQualityScreen } from '../components/service-views/WaterQualityScreen';
import { ElectricalLoadScreen } from '../components/service-views/ElectricalLoadScreen';
import { SchedulesScreen } from '../components/service-views/SchedulesScreen';
import { LatestEventsScreen } from '../components/service-views/LatestEventsScreen';
import { BcssAccountScreen } from '../components/service-views/BcssAccountScreen';
import {
  MotorIcon,
  InterlockIcon,
  TankLevelIcon,
  SumpLevelIcon,
  FlowRateIcon,
  WaterQualityIcon,
  ElectricalLoadIcon,
  PumpScheduleIcon,
  LatestEventIcon,
  WalletCardIcon,
} from '../components/ServiceIcons';

export type ServiceViewType =
  | 'SELECT_MOTOR'
  | 'INTERLOCKS'
  | 'TANK_LEVEL'
  | 'SUMP_LEVEL'
  | 'FLOW_RATE'
  | 'WATER_QUALITY'
  | 'ELECTRICAL_LOAD'
  | 'SCHEDULES'
  | 'LATEST_EVENT'
  | 'BCSS_ACCOUNT'
  | null;

export interface PumpRunSession {
  id: string;
  motorId: string;
  motorCode: string;
  motorName: string;
  startTime: string;
  stopTime: string | null;
  durationSeconds: number;
  triggerType: 'SCHEDULED' | 'MANUAL' | 'PROTECTION' | 'SYSTEM';
  scheduleName?: string;
  description?: string;
  isRunning: boolean;
  status: 'COMPLETED' | 'RUNNING' | 'TRIPPED';
  stopReason: string;
  stopReasonCategory:
    | 'SCHEDULE_END'
    | 'MANUAL_STOP'
    | 'TANK_FULL'
    | 'TURBIDITY'
    | 'DRY_RUN'
    | 'EMERGENCY_STOP'
    | 'FAULT'
    | 'TIMER'
    | 'RUNNING'
    | 'NORMAL';
  stopReasonDetails?: string;
}

export function formatDurationSecs(seconds: number): string {
  if (!seconds || seconds <= 0) return '0s';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  const h = Math.floor(m / 60);
  const remainingM = m % 60;
  if (h > 0) {
    return `${h}h ${remainingM}m ${s > 0 ? `${s}s` : ''}`.trim();
  }
  if (m > 0) {
    return `${m}m ${s > 0 ? `${s}s` : ''}`.trim();
  }
  return `${s}s`;
}

export function parseIsoDate(isoStr: string | null | undefined): Date {
  if (!isoStr) return new Date();
  const trimmed = isoStr.trim();
  let normalized = trimmed.replace(' ', 'T');
  if (!normalized.endsWith('Z') && !/[+-]\d{2}:\d{2}$/.test(normalized)) {
    normalized = normalized + 'Z';
  }
  const d = new Date(normalized);
  return isNaN(d.getTime()) ? new Date(isoStr) : d;
}

interface HomeDashboardProps {
  latestWsEvent?: WsServerEvent | null;
  wsConnected?: boolean;
  onAdminSwitch?: () => void;
}

export const HomeDashboard: React.FC<HomeDashboardProps> = ({
  latestWsEvent,
  wsConnected: _wsConnected = true,
  onAdminSwitch,
}) => {
  const { user, logout, isOperator } = useAuth();
  const { t, language } = useLanguage();
  const [activeTab, setActiveTab] = useState<MobileTab>('HOME');
  const [activeServiceScreen, setActiveServiceScreen] = useState<ServiceViewType>(null);

  const [site, setSite] = useState<Site | null>(null);
  const [station, setStation] = useState<Station | null>(null);
  const [controller, setController] = useState<Controller | null>(null);
  const [controllersList, setControllersList] = useState<Controller[]>([]);
  const [motor, setMotor] = useState<Motor | null>(null);
  const [motorsList, setMotorsList] = useState<Motor[]>([]);
  const [recentEvents, setRecentEvents] = useState<MotorEventResponse[]>([]);
  const [schedules, setSchedules] = useState<ScheduleResponse[]>([]);
  const [activeTimer, setActiveTimer] = useState<MotorTimerStatus | null>(null);
  const [remainingSeconds, setRemainingSeconds] = useState<number>(0);
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState<boolean>(false);
  const [isNotificationModalOpen, setIsNotificationModalOpen] = useState<boolean>(false);
  const [isCommissionModalOpen, setIsCommissionModalOpen] = useState<boolean>(false);
  const [isStartModalOpen, setIsStartModalOpen] = useState<boolean>(false);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [isExtending, setIsExtending] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Station Operational Settings & Thresholds
  const [tankStopThreshold, setTankStopThreshold] = useState<number>(95);
  const [sumpDryRunThreshold, setSumpDryRunThreshold] = useState<number>(10);
  const [turbidityStopThreshold, setTurbidityStopThreshold] = useState<number>(25);
  const [autoStopTankFull, setAutoStopTankFull] = useState<boolean>(true);
  const [autoStopTurbidity, setAutoStopTurbidity] = useState<boolean>(true);
  const [offlineAlertEnabled, setOfflineAlertEnabled] = useState<boolean>(true);
  const [isSavingSettings, setIsSavingSettings] = useState<boolean>(false);

  // Business Admin Management Modal State
  const [isAdminModalOpen, setIsAdminModalOpen] = useState<boolean>(false);
  const [scheduleToDelete, setScheduleToDelete] = useState<ScheduleResponse | null>(null);

  // History Section Filters & View State
  const [historyMotorFilter, setHistoryMotorFilter] = useState<string>('ALL');
  const [historyTypeFilter, setHistoryTypeFilter] = useState<string>('ALL');
  const [historyViewMode, setHistoryViewMode] = useState<'SESSIONS' | 'TIMELINE'>('SESSIONS');

  // Live telemetry state
  const [tankLevel, setTankLevel] = useState<number>(75.0);
  const [sumpLevel, setSumpLevel] = useState<number>(85.0);
  const [waterHeadMeters, _setWaterHeadMeters] = useState<number>(24.5);
  const [flowRateLpm, setFlowRateLpm] = useState<number>(0.0);
  const [turbidity, setTurbidity] = useState<number>(6.0);
  const [ph, setPh] = useState<number>(7.2);
  const [currentAmps, setCurrentAmps] = useState<number>(0.0);
  const [voltage, setVoltage] = useState<number>(230.0);
  const [powerKw, setPowerKw] = useState<number>(0.0);

  // Hierarchy Refs
  const siteRef = React.useRef<Site | null>(null);
  const stationRef = React.useRef<Station | null>(null);
  const controllerRef = React.useRef<Controller | null>(null);
  const controllersListRef = React.useRef<Controller[]>([]);
  const motorsListRef = React.useRef<Motor[]>([]);
  const motorRef = React.useRef<Motor | null>(null);
  const isFetchingRef = React.useRef<boolean>(false);
  const debounceSyncRef = React.useRef<any>(null);

  useEffect(() => {
    siteRef.current = site;
  }, [site]);
  useEffect(() => {
    stationRef.current = station;
  }, [station]);
  useEffect(() => {
    controllerRef.current = controller;
  }, [controller]);
  useEffect(() => {
    controllersListRef.current = controllersList;
  }, [controllersList]);
  useEffect(() => {
    motorsListRef.current = motorsList;
  }, [motorsList]);
  useEffect(() => {
    motorRef.current = motor;
  }, [motor]);

  const isMotorRunning = motor?.status === 'ON' || motor?.status === 'STARTING';

  // High-performance background sync
  const loadData = useCallback(async (showVisualSpinner = false) => {
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;
    if (showVisualSpinner) setIsSyncing(true);

    try {
      let curSite = siteRef.current;
      let curStation = stationRef.current;
      let curController = controllerRef.current;
      let curMotors = motorsListRef.current;

      if (!curSite || !curStation || !curController || curMotors.length === 0) {
        const sites = await api.getSites();
        if (!sites || sites.length === 0) return;
        curSite = sites[0];
        setSite(curSite);
        siteRef.current = curSite;

        const stations = await api.getStations(curSite.id);
        if (!stations || stations.length === 0) return;
        curStation = stations[0];
        setStation(curStation);
        stationRef.current = curStation;

        const controllers = await api.getControllers(curStation.id);
        if (!controllers || controllers.length === 0) return;
        setControllersList(controllers);
        controllersListRef.current = controllers;
        curController = controllers[0];
        setController(curController);
        controllerRef.current = curController;

        const stationMotors = await api.getMotors(undefined, curStation.id);
        const resolvedMotors = stationMotors && stationMotors.length > 0 ? stationMotors : await api.getMotors();
        if (resolvedMotors && resolvedMotors.length > 0) {
          curMotors = resolvedMotors;
          setMotorsList(resolvedMotors);
          motorsListRef.current = resolvedMotors;
          if (!motorRef.current) {
            setMotor(resolvedMotors[0]);
            motorRef.current = resolvedMotors[0];
            const matchingCtrl = controllers.find((c) => c.id === resolvedMotors[0].controller_id);
            if (matchingCtrl) {
              setController(matchingCtrl);
              controllerRef.current = matchingCtrl;
              curController = matchingCtrl;
            }
          }
        }
      }

      const activeTarget = motorRef.current || curMotors[0];
      const targetMotorId = activeTarget?.id;

      const [eventsRes, wqRes, schedRes, elecRes, flowRes, timerRes, settingsRes] =
        await Promise.allSettled([
          curStation
            ? api.getStationEvents(curStation.id, { limit: 50 })
            : targetMotorId
            ? api.getMotorEvents(targetMotorId, { limit: 50 })
            : Promise.resolve([]),
          curStation ? api.getWaterQuality(curStation.id) : Promise.resolve(null),
          curStation ? api.getSchedules(curStation.id) : Promise.resolve([]),
          targetMotorId ? api.getElectricalMetrics(targetMotorId) : Promise.resolve(null),
          targetMotorId ? api.getFlowDiagnostics(targetMotorId) : Promise.resolve(null),
          targetMotorId ? api.getMotorTimer(targetMotorId) : Promise.resolve(null),
          curStation ? api.getStationSettings(curStation.id) : Promise.resolve(null),
        ]);

      if (eventsRes.status === 'fulfilled' && eventsRes.value) {
        setRecentEvents(eventsRes.value);
      }

      if (wqRes.status === 'fulfilled' && wqRes.value) {
        if (wqRes.value.turbidity_ntu !== undefined && wqRes.value.turbidity_ntu !== null) {
          setTurbidity(wqRes.value.turbidity_ntu);
        }
        if (wqRes.value.ph !== undefined && wqRes.value.ph !== null) {
          setPh(wqRes.value.ph);
        }
      }

      if (schedRes.status === 'fulfilled' && schedRes.value) {
        setSchedules(schedRes.value);
      }

      if (elecRes.status === 'fulfilled' && elecRes.value) {
        if (elecRes.value.current_a !== undefined && elecRes.value.current_a !== null) {
          setCurrentAmps(elecRes.value.current_a);
        }
        if (elecRes.value.voltage_v !== undefined && elecRes.value.voltage_v !== null) {
          setVoltage(elecRes.value.voltage_v);
        }
        if (elecRes.value.power_kw !== undefined && elecRes.value.power_kw !== null) {
          setPowerKw(elecRes.value.power_kw);
        }
      }

      if (flowRes.status === 'fulfilled' && flowRes.value) {
        if (flowRes.value.flow_rate_lpm !== undefined && flowRes.value.flow_rate_lpm !== null) {
          setFlowRateLpm(flowRes.value.flow_rate_lpm);
        }
      }

      if (settingsRes.status === 'fulfilled' && settingsRes.value) {
        const s = settingsRes.value;
        if (s.water_level_threshold !== undefined && s.water_level_threshold !== null) {
          setTankStopThreshold(s.water_level_threshold);
        }
        if (s.turbidity_threshold !== undefined && s.turbidity_threshold !== null) {
          setTurbidityStopThreshold(s.turbidity_threshold);
        }
        if (s.auto_stop_on_tank_full !== undefined && s.auto_stop_on_tank_full !== null) {
          setAutoStopTankFull(Boolean(s.auto_stop_on_tank_full));
        }
        if (s.auto_stop_on_turbidity !== undefined && s.auto_stop_on_turbidity !== null) {
          setAutoStopTurbidity(Boolean(s.auto_stop_on_turbidity));
        }
        if (s.offline_alert_enabled !== undefined && s.offline_alert_enabled !== null) {
          setOfflineAlertEnabled(Boolean(s.offline_alert_enabled));
        }
      }

      if (timerRes.status === 'fulfilled' && timerRes.value) {
        const timerData = timerRes.value;
        setActiveTimer(timerData);
        if (timerData.is_running && timerData.remaining_seconds !== undefined) {
          setRemainingSeconds(Math.max(0, Math.round(timerData.remaining_seconds)));
        } else {
          setRemainingSeconds(0);
        }
      } else {
        setActiveTimer(null);
        setRemainingSeconds(0);
      }

      // Re-fetch fresh motor status & sensor readings on each cycle
      try {
        const stationId = curStation?.id;
        const freshMotors = await api.getMotors(undefined, stationId);
        const resolvedMotors = freshMotors && freshMotors.length > 0 ? freshMotors : await api.getMotors();
        if (resolvedMotors && resolvedMotors.length > 0) {
          setMotorsList(resolvedMotors);
          motorsListRef.current = resolvedMotors;
          const updatedCur = resolvedMotors.find((m) => m.id === (motorRef.current?.id || resolvedMotors[0].id)) || resolvedMotors[0];
          setMotor(updatedCur);
          motorRef.current = updatedCur;

          if (controllersListRef.current.length > 0) {
            const matchingCtrl = controllersListRef.current.find((c) => c.id === updatedCur.controller_id);
            if (matchingCtrl && matchingCtrl.id !== controllerRef.current?.id) {
              setController(matchingCtrl);
              controllerRef.current = matchingCtrl;
              curController = matchingCtrl;
            }
          }
        }

        const activeCtrl = controllerRef.current || curController;
        if (activeCtrl) {
          const sensors = await api.getSensors(activeCtrl.id);
          if (sensors && sensors.length > 0) {
            const levelSensors = sensors.filter(s => {
              const sc = s.sensor_code.toUpperCase();
              return s.sensor_type === 'WATER_LEVEL' || sc.includes('LEVEL') || sc.includes('TANK');
            });
            await Promise.all(
              levelSensors.map(async (s) => {
                const sc = s.sensor_code.toUpperCase();
                const latest = await api.getSensorLatest(s.id);
                if (latest && latest.value !== undefined && latest.value !== null) {
                  if (sc.includes('SUMP') || sc.includes('SOURCE')) {
                    setSumpLevel(Number(latest.value));
                  } else {
                    setTankLevel(Number(latest.value));
                  }
                }
              })
            );
          }
        }
      } catch (fetchErr) {
        console.debug('Background motor/sensor poll error:', fetchErr);
      }
    } catch (err) {
      console.error('Failed to load station telemetry:', err);
    } finally {
      isFetchingRef.current = false;
      if (showVisualSpinner) setIsSyncing(false);
    }
  }, []);

  const debouncedSync = useCallback((delay = 300) => {
    if (debounceSyncRef.current) clearTimeout(debounceSyncRef.current);
    debounceSyncRef.current = setTimeout(() => {
      loadData(false);
    }, delay);
  }, [loadData]);

  useEffect(() => {
    loadData(false);
    const interval = setInterval(() => {
      loadData(false);
    }, 5000);
    return () => clearInterval(interval);
  }, [loadData]);

  // Real-time Countdown Synchronizer
  useEffect(() => {
    if (!activeTimer || !activeTimer.end_time || (motor?.status !== 'ON' && motor?.status !== 'STARTING')) {
      setRemainingSeconds(0);
      return;
    }
    const updateTick = () => {
      const target = new Date(activeTimer.end_time!).getTime();
      const now = Date.now();
      const diff = Math.max(0, Math.floor((target - now) / 1000));
      setRemainingSeconds(diff);

      // 1-minute warning sound
      if (diff <= 60 && diff > 0 && !activeTimer.is_warning_active) {
        audioAlert.testSound('WARNING');
      }

      // When scheduled session reaches 0, close motor
      if (diff <= 0) {
        setActiveTimer(null);
        setRemainingSeconds(0);
        setMotor((prev) => (prev ? { ...prev, status: 'OFF' } : null));
        setMotorsList((prev) =>
          prev.map((m) => (m.id === motor?.id ? { ...m, status: 'OFF' } : m))
        );
        audioAlert.testSound('INFO');
        debouncedSync(100);
      }
    };
    updateTick();
    const interval = setInterval(updateTick, 1000);
    return () => clearInterval(interval);
  }, [activeTimer, motor?.status, motor?.id, debouncedSync]);

  // Handle WebSocket updates
  useEffect(() => {
    if (!latestWsEvent) return;

    const ev = latestWsEvent as any;
    if (ev.event === 'TELEMETRY' || ev.event === 'MOTOR_STATE' || ev.type === 'TELEMETRY_UPDATED' || ev.event === 'SAFETY_ALERT') {
      const payload = ev.payload || ev || {};

      // Match target motor by ID, motor_code, or device_uid
      const isTargetMotor =
        (payload.motor_id && motorRef.current && payload.motor_id === motorRef.current.id) ||
        (payload.motor_code && motorRef.current && payload.motor_code.toUpperCase() === motorRef.current.motor_code.toUpperCase()) ||
        (payload.device_uid && controllerRef.current && payload.device_uid === controllerRef.current.device_uid);

      if (payload.status) {
        if (isTargetMotor) {
          setMotor((prev) => (prev ? { ...prev, status: payload.status } : null));
        }
        setMotorsList((prev) =>
          prev.map((m) =>
            (payload.motor_id && m.id === payload.motor_id) ||
            (payload.motor_code && m.motor_code.toUpperCase() === payload.motor_code.toUpperCase())
              ? { ...m, status: payload.status }
              : m
          )
        );
      }

      // Check direct telemetry keys
      if (payload.current_a !== undefined) setCurrentAmps(Number(payload.current_a));
      if (payload.voltage_v !== undefined) setVoltage(Number(payload.voltage_v));
      if (payload.power_kw !== undefined) setPowerKw(Number(payload.power_kw));
      if (payload.flow_rate_lpm !== undefined) setFlowRateLpm(Number(payload.flow_rate_lpm));
      if (payload.tank_level !== undefined) setTankLevel(Number(payload.tank_level));
      if (payload.sump_level !== undefined) setSumpLevel(Number(payload.sump_level));
      if (payload.turbidity_ntu !== undefined) setTurbidity(Number(payload.turbidity_ntu));
      if (payload.ph !== undefined) setPh(Number(payload.ph));

      // Support generic sensor_code mapping from backend stream_telemetry
      if (payload.sensor_code && payload.value !== undefined) {
        const sc = String(payload.sensor_code).toUpperCase();
        if (sc.includes('SUMP') || sc.includes('SOURCE')) {
          setSumpLevel(Number(payload.value));
        } else if (sc.includes('LEVEL') || sc.includes('TANK')) {
          setTankLevel(Number(payload.value));
        } else if (sc.includes('TURB')) {
          setTurbidity(Number(payload.value));
        } else if (sc.includes('CURR')) {
          setCurrentAmps(Number(payload.value));
        } else if (sc.includes('VOLT')) {
          setVoltage(Number(payload.value));
        } else if (sc.includes('FLOW')) {
          setFlowRateLpm(Number(payload.value));
        }
      }

      // Safety alert / Tank full notification
      if (ev.event === 'SAFETY_ALERT' || payload.event_type === 'TANK_FULL' || payload.reason === 'TANK_FULL') {
        setToastMessage('⚠️ Auto-Stop: Overhead Tank Full (Pump Auto-Cutoff)');
        audioAlert.testSound('WARNING');
        setTimeout(() => setToastMessage(null), 4000);
      }

      debouncedSync(300);
    }
  }, [latestWsEvent, debouncedSync]);

  const handleSelectMotor = (selectedMotor: Motor) => {
    setMotor(selectedMotor);
    motorRef.current = selectedMotor;
    const matchingCtrl = controllersListRef.current.find((c) => c.id === selectedMotor.controller_id);
    if (matchingCtrl) {
      setController(matchingCtrl);
      controllerRef.current = matchingCtrl;
    }
    setToastMessage(`Switched active control to ${selectedMotor.name}`);
    setTimeout(() => setToastMessage(null), 2500);
    debouncedSync(100);
  };

  // Reset Latched Fault on Motor to Ready Standby (OFF)
  const handleResetMotor = async (targetMotorId?: string) => {
    const mId = targetMotorId || motor?.id;
    if (!mId || !isOperator) return;
    setIsProcessing(true);
    const targetMotor = motorsList.find((m) => m.id === mId) || motor;
    const prevStatus = targetMotor?.status;
    setMotorsList((prev) => prev.map((m) => (m.id === mId ? { ...m, status: 'OFF' } : m)));
    if (motor && motor.id === mId) {
      setMotor({ ...motor, status: 'OFF' });
    }

    try {
      await api.resetMotor(mId);
      setToastMessage(`Fault cleared for ${targetMotor?.name || 'Pump'}! Motor returned to standby.`);
      audioAlert.testSound('SUCCESS');
      setTimeout(() => setToastMessage(null), 3000);
      await loadData(false);
    } catch (err: any) {
      if (prevStatus) {
        setMotorsList((prev) => prev.map((m) => (m.id === mId ? { ...m, status: prevStatus } : m)));
        if (motor && motor.id === mId) setMotor({ ...motor, status: prevStatus });
      }
      setToastMessage(err.message || 'Failed to clear fault');
      setTimeout(() => setToastMessage(null), 3500);
    } finally {
      setIsProcessing(false);
    }
  };

  // Start / Stop Power Action with Scheduled Closing Duration Support
  const handlePowerToggle = async () => {
    if (!motor || !isOperator) return;

    if (motor.status === 'FAULT') {
      await handleResetMotor(motor.id);
      return;
    }

    if (isMotorRunning) {
      // Direct instant stop
      setIsProcessing(true);
      const prevStatus = motor.status;
      setMotor({ ...motor, status: 'OFF' });
      setMotorsList((prev) => prev.map((m) => (m.id === motor.id ? { ...m, status: 'OFF' } : m)));
      setActiveTimer(null);
      setRemainingSeconds(0);

      try {
        await api.stopMotor(motor.id, {
          reason: 'MANUAL_STOP',
          description: 'Manual stop command by operator',
        });
        setToastMessage(`Pump (${motor.motor_code}) Stopped`);
        audioAlert.testSound('INFO');
        setTimeout(() => setToastMessage(null), 2500);
        await loadData(false);
      } catch (err: any) {
        setMotor({ ...motor, status: prevStatus });
        setMotorsList((prev) => prev.map((m) => (m.id === motor.id ? { ...m, status: prevStatus } : m)));
        setToastMessage(err.message || 'Failed to stop pump');
        setTimeout(() => setToastMessage(null), 3000);
      } finally {
        setIsProcessing(false);
      }
    } else {
      // Open scheduled closing time options modal
      setIsStartModalOpen(true);
    }
  };

  // Confirm Start with Scheduled Auto-Stop Closing Time
  const handleConfirmStartMotor = async (durationMinutes: number = 30) => {
    if (!motor || !isOperator) return;
    setIsProcessing(true);
    const prevStatus = motor.status;
    const durationSeconds = Math.max(60, durationMinutes * 60);

    // Optimistic instant start
    setMotor({ ...motor, status: 'ON' });
    setMotorsList((prev) => prev.map((m) => (m.id === motor.id ? { ...m, status: 'ON' } : m)));

    // Optimistically set active countdown timer
    const now = new Date();
    const endTime = new Date(now.getTime() + durationSeconds * 1000).toISOString();
    setActiveTimer({
      motor_id: motor.id,
      motor_code: motor.motor_code,
      status: 'ON',
      is_running: true,
      duration_seconds: durationSeconds,
      remaining_seconds: durationSeconds,
      elapsed_seconds: 0,
      started_at: now.toISOString(),
      end_time: endTime,
      is_warning_active: false,
      is_expired: false,
      source: 'MANUAL',
      schedule_name: `Timer (${durationMinutes} min)`,
    });
    setRemainingSeconds(durationSeconds);

    try {
      await api.startMotor(motor.id, {
        duration_seconds: durationSeconds,
        reason: 'MANUAL_START',
        schedule_name: `Timer (${durationMinutes} min)`,
      });
      setToastMessage(
        `Pump (${motor.motor_code}) Started • Auto-closing in ${durationMinutes} min`
      );
      audioAlert.testSound('INFO');
      setTimeout(() => setToastMessage(null), 3500);
      await loadData(false);
    } catch (err: any) {
      setMotor({ ...motor, status: prevStatus });
      setMotorsList((prev) => prev.map((m) => (m.id === motor.id ? { ...m, status: prevStatus } : m)));
      setActiveTimer(null);
      setRemainingSeconds(0);
      setToastMessage(err.message || 'Safety lock active: start rejected');
      setTimeout(() => setToastMessage(null), 3000);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleContinueTimer = async (extendSeconds: number = 900) => {
    if (!motor || !isOperator || isExtending) return;
    setIsExtending(true);
    try {
      const updated = await api.continueMotorTimer(motor.id, extendSeconds);
      setActiveTimer(updated);
      setRemainingSeconds(Math.max(0, Math.round(updated.remaining_seconds)));
      setToastMessage(`Scheduled operation extended (+${Math.round(extendSeconds / 60)} min)`);
      audioAlert.testSound('INFO');
      setTimeout(() => setToastMessage(null), 3500);
    } catch (err: any) {
      setToastMessage(err.message || 'Failed to extend schedule timer');
      setTimeout(() => setToastMessage(null), 3500);
    } finally {
      setIsExtending(false);
    }
  };

  const handleUpdateTankThreshold = async (newVal: number) => {
    if (!station) return;
    setTankStopThreshold(newVal);
    await api.updateStationSettings(station.id, {
      water_level_threshold: Number(newVal),
    });
    setToastMessage(`✓ Overhead Tank Auto-Stop Level Saved: ${newVal}%`);
    setTimeout(() => setToastMessage(null), 3000);
    debouncedSync(200);
  };

  const handleToggleAutoStop = async (enabled: boolean) => {
    if (!station) return;
    setAutoStopTankFull(enabled);
    await api.updateStationSettings(station.id, {
      auto_stop_on_tank_full: enabled,
    });
    setToastMessage(`✓ Auto-Stop on Tank Full Rule ${enabled ? 'Enabled' : 'Disabled'}`);
    setTimeout(() => setToastMessage(null), 3000);
    debouncedSync(200);
  };

  const handleUpdateSumpThreshold = async (newVal: number) => {
    if (!station) return;
    setSumpDryRunThreshold(newVal);
    setToastMessage(`✓ Sump Dry-Run Cutoff Saved: ${newVal}%`);
    setTimeout(() => setToastMessage(null), 3000);
    debouncedSync(200);
  };

  const handleUpdateTurbidityThreshold = async (newVal: number) => {
    if (!station) return;
    setTurbidityStopThreshold(newVal);
    await api.updateStationSettings(station.id, {
      turbidity_threshold: Number(newVal),
    });
    setToastMessage(`✓ Turbidity Cutoff Limit Saved: ${newVal} NTU`);
    setTimeout(() => setToastMessage(null), 3000);
    debouncedSync(200);
  };

  const handleToggleScheduleActive = async (s: ScheduleResponse) => {
    if (!station) return;
    try {
      const updated = await api.updateSchedule(station.id, s.id, {
        is_active: !s.is_active,
      });
      setSchedules((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setToastMessage(`Schedule "${s.name}" ${updated.is_active ? 'Activated' : 'Paused'}`);
      setTimeout(() => setToastMessage(null), 3000);
      debouncedSync(200);
    } catch (err: any) {
      setToastMessage(err.message || 'Failed to toggle schedule');
      setTimeout(() => setToastMessage(null), 3000);
    }
  };

  const handleDeleteScheduleDirect = async (s: ScheduleResponse) => {
    if (!station) return;
    try {
      await api.deleteSchedule(station.id, s.id);
      setSchedules((prev) => prev.filter((item) => item.id !== s.id));
      setScheduleToDelete(null);
      setToastMessage(`Schedule "${s.name}" Deleted`);
      setTimeout(() => setToastMessage(null), 3000);
      debouncedSync(200);
    } catch (err: any) {
      setToastMessage(err.message || 'Failed to delete schedule');
      setTimeout(() => setToastMessage(null), 3000);
    }
  };

  const handleSaveOperationalSettings = async () => {
    if (!station) return;
    setIsSavingSettings(true);
    try {
      await api.updateStationSettings(station.id, {
        water_level_threshold: Number(tankStopThreshold),
        turbidity_threshold: Number(turbidityStopThreshold),
        auto_stop_on_tank_full: Boolean(autoStopTankFull),
        auto_stop_on_turbidity: Boolean(autoStopTurbidity),
        offline_alert_enabled: Boolean(offlineAlertEnabled),
      });
      setToastMessage('✓ Operational Thresholds & Safety Rules Saved!');
      setTimeout(() => setToastMessage(null), 3500);
      debouncedSync(100);
    } catch (err: any) {
      setToastMessage(err.message || 'Failed to save station settings');
      setTimeout(() => setToastMessage(null), 3500);
    } finally {
      setIsSavingSettings(false);
    }
  };

  // Refresh events whenever user enters Activity & Audit Log screen
  useEffect(() => {
    if (activeServiceScreen === 'LATEST_EVENT') {
      loadData(false);
    }
  }, [activeServiceScreen, loadData]);

  // Convert raw events into structured sessions
  const runSessions: PumpRunSession[] = React.useMemo(() => {
    const sorted = [...recentEvents].sort((a, b) => {
      const timeDiff = new Date(a.occurred_at).getTime() - new Date(b.occurred_at).getTime();
      if (timeDiff !== 0) return timeDiff;
      if (a.event_type === 'STARTED' && b.event_type !== 'STARTED') return -1;
      if (a.event_type !== 'STARTED' && b.event_type === 'STARTED') return 1;
      return 0;
    });

    const sessions: PumpRunSession[] = [];
    const openStartsByMotor: Record<string, MotorEventResponse> = {};

    for (const ev of sorted) {
      const motorId = ev.motor_id;
      const targetMotor = motorsList.find((m) => m.id === motorId) || motor;
      const motorCode = targetMotor?.motor_code || 'MTR-1';
      const motorName = targetMotor?.name || 'Main Pump';

      if (ev.event_type === 'STARTED') {
        const existing = openStartsByMotor[motorId];
        // If an existing start was already an AUTOMATION / SCHEDULED event, preserve its metadata
        if (existing && (existing.source === 'AUTOMATION' || existing.event_payload?.schedule_name)) {
          openStartsByMotor[motorId] = {
            ...ev,
            source: existing.source,
            description: existing.description,
            event_payload: { ...ev.event_payload, ...existing.event_payload },
            occurred_at: existing.occurred_at,
          };
        } else {
          openStartsByMotor[motorId] = ev;
        }
      } else if (ev.event_type === 'STOPPED' || ev.event_type === 'FAULT' || ev.event_type === 'EMERGENCY_STOP') {
        const startEv = openStartsByMotor[motorId];
        const stopTime = ev.occurred_at;
        const startTime = startEv ? startEv.occurred_at : stopTime;
        let durationSecs = Math.max(
          0,
          Math.round((new Date(stopTime).getTime() - new Date(startTime).getTime()) / 1000)
        );

        if (durationSecs === 0 && ev.event_payload?.runtime_seconds) {
          durationSecs = Math.max(0, Math.round(Number(ev.event_payload.runtime_seconds)));
        }

        let stopCategory: PumpRunSession['stopReasonCategory'] = 'NORMAL';
        let stopReason = ev.description || 'Routine Cycle Finished';

        if (ev.event_payload?.reason) {
          stopReason = ev.event_payload.reason;
        }

        const reasonUpper = stopReason.toUpperCase();
        if (reasonUpper.includes('SCHEDULE') || reasonUpper.includes('AUTO_STOP')) {
          stopCategory = 'SCHEDULE_END';
        } else if (reasonUpper.includes('TANK_FULL') || reasonUpper.includes('OVERFLOW')) {
          stopCategory = 'TANK_FULL';
        } else if (reasonUpper.includes('TURBIDITY')) {
          stopCategory = 'TURBIDITY';
        } else if (reasonUpper.includes('DRY_RUN')) {
          stopCategory = 'DRY_RUN';
        } else if (reasonUpper.includes('MANUAL')) {
          stopCategory = 'MANUAL_STOP';
        } else if (reasonUpper.includes('EMERGENCY')) {
          stopCategory = 'EMERGENCY_STOP';
        }

        const isSchedSession = Boolean(
          startEv?.source === 'AUTOMATION' ||
          ev.source === 'AUTOMATION' ||
          startEv?.event_payload?.schedule_name ||
          ev.event_payload?.schedule_name ||
          startEv?.event_payload?.schedule_id ||
          ev.event_payload?.schedule_id ||
          String(startEv?.description || '').toLowerCase().includes('schedule') ||
          String(ev.description || '').toLowerCase().includes('schedule')
        );

        const schedName =
          startEv?.event_payload?.schedule_name ||
          ev.event_payload?.schedule_name ||
          (startEv?.description?.startsWith('Schedule: ')
            ? startEv.description.replace('Schedule: ', '').trim()
            : ev.description?.startsWith('Schedule Completed: ')
            ? ev.description.replace('Schedule Completed: ', '').trim()
            : startEv?.description?.startsWith('Schedule Completed: ')
            ? startEv.description.replace('Schedule Completed: ', '').trim()
            : undefined);

        if (schedName && stopCategory === 'SCHEDULE_END' && !stopReason.includes(schedName)) {
          stopReason = `Schedule Completed: ${schedName}`;
        }

        sessions.unshift({
          id: ev.id,
          motorId,
          motorCode,
          motorName,
          startTime,
          stopTime,
          durationSeconds: durationSecs,
          triggerType: isSchedSession ? 'SCHEDULED' : 'MANUAL',
          scheduleName: schedName,
          description: ev.description || startEv?.description || (schedName ? `Schedule: ${schedName}` : undefined),
          isRunning: false,
          status: ev.event_type === 'FAULT' || ev.event_type === 'EMERGENCY_STOP' ? 'TRIPPED' : 'COMPLETED',
          stopReason,
          stopReasonCategory: stopCategory,
        });

        delete openStartsByMotor[motorId];
      }
    }

    // Include currently running sessions for any active motors
    const runningMotors = motorsList.length > 0
      ? motorsList.filter((m) => m.status === 'ON' || m.status === 'STARTING')
      : (motor && isMotorRunning ? [motor] : []);

    for (const runM of runningMotors) {
      const isCur = runM.id === motor?.id;
      const runTimer = isCur ? activeTimer : null;
      const openStart = openStartsByMotor[runM.id];

      const isSchedRunning = Boolean(
        runTimer?.schedule_name ||
        runTimer?.source === 'SCHEDULED' ||
        openStart?.source === 'AUTOMATION' ||
        openStart?.event_payload?.schedule_name ||
        openStart?.event_payload?.schedule_id ||
        String(openStart?.description || '').toLowerCase().includes('schedule')
      );

      const schedName =
        runTimer?.schedule_name ||
        openStart?.event_payload?.schedule_name ||
        (openStart?.description?.startsWith('Schedule: ')
          ? openStart.description.replace('Schedule: ', '').trim()
          : undefined);

      const startTime = runTimer?.started_at || openStart?.occurred_at || new Date().toISOString();
      const startMs = new Date(startTime).getTime();
      const nowMs = Date.now();
      const elapsedSecs = Math.max(0, Math.round((nowMs - startMs) / 1000));

      const durationSecs = runTimer && runTimer.duration_seconds > 0
        ? Math.max(0, runTimer.duration_seconds - remainingSeconds)
        : (openStart ? elapsedSecs : 120);

      sessions.unshift({
        id: `live-active-session-${runM.id}`,
        motorId: runM.id,
        motorCode: runM.motor_code,
        motorName: runM.name,
        startTime,
        stopTime: null,
        durationSeconds: durationSecs,
        triggerType: isSchedRunning ? 'SCHEDULED' : 'MANUAL',
        scheduleName: schedName,
        description: schedName
          ? `Running on Schedule: ${schedName}`
          : (openStart?.description || 'Currently running active pumping cycle'),
        isRunning: true,
        status: 'RUNNING',
        stopReason: schedName ? `Schedule in Progress: ${schedName}` : 'Active Operation In Progress',
        stopReasonCategory: isSchedRunning ? 'SCHEDULE_END' : 'RUNNING',
      });
    }

    // Also include any open starts for motors that may be in transition
    for (const [mId, openEv] of Object.entries(openStartsByMotor)) {
      if (!runningMotors.some((rm) => rm.id === mId)) {
        const targetMotor = motorsList.find((m) => m.id === mId) || motor;
        const motorCode = targetMotor?.motor_code || 'MTR-1';
        const motorName = targetMotor?.name || 'Main Pump';

        const isSched = Boolean(
          openEv.source === 'AUTOMATION' ||
          openEv.event_payload?.schedule_name ||
          openEv.event_payload?.schedule_id ||
          String(openEv.description || '').toLowerCase().includes('schedule')
        );

        const schedName =
          openEv.event_payload?.schedule_name ||
          (openEv.description?.startsWith('Schedule: ')
            ? openEv.description.replace('Schedule: ', '').trim()
            : undefined);

        const startMs = new Date(openEv.occurred_at).getTime();
        const nowMs = Date.now();
        const elapsedSecs = Math.max(0, Math.round((nowMs - startMs) / 1000));

        sessions.unshift({
          id: `live-open-session-${openEv.id}`,
          motorId: mId,
          motorCode,
          motorName,
          startTime: openEv.occurred_at,
          stopTime: null,
          durationSeconds: elapsedSecs,
          triggerType: isSched ? 'SCHEDULED' : 'MANUAL',
          scheduleName: schedName,
          description: openEv.description || (schedName ? `Schedule: ${schedName}` : 'Running active cycle'),
          isRunning: true,
          status: 'RUNNING',
          stopReason: schedName ? `Schedule in Progress: ${schedName}` : 'Active Operation In Progress',
          stopReasonCategory: isSched ? 'SCHEDULE_END' : 'RUNNING',
        });
      }
    }

    return sessions;
  }, [recentEvents, motorsList, motor, isMotorRunning, activeTimer, remainingSeconds]);

  const filteredSessions = runSessions.filter((s) => {
    if (historyMotorFilter !== 'ALL' && s.motorId !== historyMotorFilter) return false;
    if (historyTypeFilter !== 'ALL' && s.triggerType !== historyTypeFilter) return false;
    return true;
  });

  const filteredEvents = recentEvents.filter((ev) => {
    if (historyMotorFilter !== 'ALL' && ev.motor_id !== historyMotorFilter) return false;
    return true;
  });

  const historyMetrics = React.useMemo(() => {
    let totalSecs = 0;
    let schedSecs = 0;
    let manualSecs = 0;
    let schedCount = 0;
    let manualCount = 0;

    for (const s of runSessions) {
      totalSecs += s.durationSeconds;
      if (s.triggerType === 'SCHEDULED') {
        schedSecs += s.durationSeconds;
        schedCount++;
      } else {
        manualSecs += s.durationSeconds;
        manualCount++;
      }
    }

    return {
      totalFormatted: formatDurationSecs(totalSecs),
      scheduledFormatted: formatDurationSecs(schedSecs),
      manualFormatted: formatDurationSecs(manualSecs),
      scheduledCount: schedCount,
      manualCount: manualCount,
    };
  }, [runSessions]);

  const isAdmin = user?.role === 'SUPER_ADMIN' || user?.role === 'ORGANIZATION_ADMIN';

  return (
    <div className="w-full max-w-lg mx-auto px-3.5 pt-1.5 pb-dock-clearance space-y-3.5 font-sans selection:bg-blue-500 selection:text-white">
      {/* Toast Alert */}
      {toastMessage && (
        <div className="fixed top-[calc(4.25rem+env(safe-area-inset-top,0px))] left-1/2 -translate-x-1/2 z-50 px-4 py-2.5 rounded-xl bg-slate-900/95 border border-slate-700 text-white text-xs font-semibold flex items-center gap-2 backdrop-blur-md shadow-lg animate-fade-in">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 1: HOME (OR DETAIL SERVICE SCREEN IF SELECTED) */}
      {/* ========================================================================= */}
      {activeTab === 'HOME' && (
        <>
          {/* ------------------------------------------------------------- */}
          {/* DETAIL SERVICE SCREENS (WHEN CLICKED ON ANY SERVICE CARD) */}
          {/* ------------------------------------------------------------- */}
          {activeServiceScreen === 'SELECT_MOTOR' && (
            <MotorSelectionScreen
              onBack={() => setActiveServiceScreen(null)}
              motors={motorsList.length > 0 ? motorsList : (motor ? [motor] : [])}
              activeMotor={motor}
              onSelectMotor={handleSelectMotor}
              isProcessing={isProcessing}
              onPowerToggle={handlePowerToggle}
              onResetMotor={(mId) => handleResetMotor(mId)}
              onOpenStartModal={() => setIsStartModalOpen(true)}
              currentAmps={currentAmps}
              voltage={voltage}
              powerKw={powerKw}
              onRefresh={() => loadData(true)}
              isSyncing={isSyncing}
            />
          )}

          {activeServiceScreen === 'INTERLOCKS' && (
            <InterlocksScreen
              onBack={() => setActiveServiceScreen(null)}
              tankLevel={tankLevel}
              tankStopThreshold={tankStopThreshold}
              autoStopTankFull={autoStopTankFull}
              onToggleAutoStopTankFull={async (val) => {
                setAutoStopTankFull(val);
                if (station) {
                  try {
                    await api.updateStationSettings(station.id, { auto_stop_on_tank_full: val });
                    setToastMessage(`✓ Tank Overflow Cutoff: ${val ? 'ENABLED' : 'DISABLED'}`);
                    setTimeout(() => setToastMessage(null), 3000);
                  } catch (e: any) {
                    console.error('Failed to update tank auto-stop setting:', e);
                  }
                }
              }}
              sumpLevel={sumpLevel}
              sumpDryRunThreshold={sumpDryRunThreshold}
              turbidity={turbidity}
              turbidityStopThreshold={turbidityStopThreshold}
              autoStopTurbidity={autoStopTurbidity}
              onToggleAutoStopTurbidity={async (val) => {
                setAutoStopTurbidity(val);
                if (station) {
                  try {
                    await api.updateStationSettings(station.id, { auto_stop_on_turbidity: val });
                    setToastMessage(`✓ Turbidity Clarity Cutoff: ${val ? 'ENABLED' : 'DISABLED'}`);
                    setTimeout(() => setToastMessage(null), 3000);
                  } catch (e: any) {
                    console.error('Failed to update turbidity cutoff setting:', e);
                  }
                }
              }}
              currentAmps={currentAmps}
              voltage={voltage}
              onRefresh={() => loadData(true)}
              isSyncing={isSyncing}
            />
          )}

          {activeServiceScreen === 'TANK_LEVEL' && (
            <TankLevelScreen
              onBack={() => setActiveServiceScreen(null)}
              tankLevel={tankLevel}
              waterHeadMeters={waterHeadMeters}
              tankStopThreshold={tankStopThreshold}
              onUpdateTankThreshold={handleUpdateTankThreshold}
              autoStopTankFull={autoStopTankFull}
              onToggleAutoStop={handleToggleAutoStop}
              onRefresh={() => loadData(true)}
              isSyncing={isSyncing}
            />
          )}

          {activeServiceScreen === 'SUMP_LEVEL' && (
            <SumpLevelScreen
              onBack={() => setActiveServiceScreen(null)}
              sumpLevel={sumpLevel}
              sumpDryRunThreshold={sumpDryRunThreshold}
              onUpdateSumpThreshold={handleUpdateSumpThreshold}
              onRefresh={() => loadData(true)}
              isSyncing={isSyncing}
            />
          )}

          {activeServiceScreen === 'FLOW_RATE' && (
            <FlowRateScreen
              onBack={() => setActiveServiceScreen(null)}
              flowRateLpm={flowRateLpm}
              isMotorRunning={isMotorRunning}
              onRefresh={() => loadData(true)}
              isSyncing={isSyncing}
            />
          )}

          {activeServiceScreen === 'WATER_QUALITY' && (
            <WaterQualityScreen
              onBack={() => setActiveServiceScreen(null)}
              turbidity={turbidity}
              ph={ph}
              turbidityStopThreshold={turbidityStopThreshold}
              onUpdateTurbidityThreshold={handleUpdateTurbidityThreshold}
              onRefresh={() => loadData(true)}
              isSyncing={isSyncing}
            />
          )}

          {activeServiceScreen === 'ELECTRICAL_LOAD' && (
            <ElectricalLoadScreen
              onBack={() => setActiveServiceScreen(null)}
              currentAmps={currentAmps}
              voltage={voltage}
              powerKw={powerKw}
              isMotorRunning={isMotorRunning}
              onRefresh={() => loadData(true)}
              isSyncing={isSyncing}
            />
          )}

          {activeServiceScreen === 'SCHEDULES' && (
            <SchedulesScreen
              onBack={() => setActiveServiceScreen(null)}
              schedules={schedules}
              motors={motorsList.length > 0 ? motorsList : (motor ? [motor] : [])}
              activeMotor={motor}
              onOpenAddSchedule={() => setIsScheduleModalOpen(true)}
              onToggleScheduleActive={handleToggleScheduleActive}
              onDeleteSchedule={(s) => setScheduleToDelete(s)}
              onRefresh={() => loadData(true)}
              isSyncing={isSyncing}
            />
          )}

          {activeServiceScreen === 'LATEST_EVENT' && (
            <LatestEventsScreen
              onBack={() => setActiveServiceScreen(null)}
              runSessions={runSessions}
              filteredSessions={filteredSessions}
              filteredEvents={filteredEvents}
              motors={motorsList}
              historyMotorFilter={historyMotorFilter}
              setHistoryMotorFilter={setHistoryMotorFilter}
              historyTypeFilter={historyTypeFilter}
              setHistoryTypeFilter={setHistoryTypeFilter}
              historyViewMode={historyViewMode}
              setHistoryViewMode={setHistoryViewMode}
              historyMetrics={historyMetrics}
              onRefresh={() => loadData(true)}
              isSyncing={isSyncing}
              parseIsoDate={parseIsoDate}
              formatDurationSecs={formatDurationSecs}
            />
          )}

          {activeServiceScreen === 'BCSS_ACCOUNT' && (
            <BcssAccountScreen
              onBack={() => setActiveServiceScreen(null)}
              onOpenAdminModal={() => setIsAdminModalOpen(true)}
            />
          )}

          {/* ------------------------------------------------------------- */}
          {/* DEFAULT HOME PAGE VIEW (EXACT PIXEL REPLICA OF SCREENSHOT) */}
          {/* ------------------------------------------------------------- */}
          {activeServiceScreen === null && (
            <>
              {/* 1. STATION STATUS CARD */}
              <div className="mobile-card p-3.5 flex items-center justify-between gap-2.5 rounded-2xl bg-white border border-slate-200">
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <span className="relative flex h-2.5 w-2.5 flex-shrink-0">
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500 ring-2 ring-emerald-500/20"></span>
                  </span>
                  <div className="min-w-0">
                    <h2 className="text-sm font-black text-slate-900 tracking-tight leading-tight truncate">
                      {station?.name || 'Demo Water Pump Station'}
                    </h2>
                    <div className="text-[11px] text-slate-400 font-medium truncate mt-0.5">
                      {site?.name || 'Demo Main Site'} &bull; {controller?.device_uid || 'DEMO-ESP32-001'}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 flex-shrink-0">
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl bg-amber-50 border border-amber-200/80 text-[10px] font-bold text-amber-700 whitespace-nowrap">
                    <AlertTriangle className="w-3 h-3 text-amber-500 flex-shrink-0" />
                    <span>1m ago</span>
                  </span>
                  <button
                    onClick={() => loadData(true)}
                    title="Refresh Station Data"
                    className="p-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors flex-shrink-0 cursor-pointer"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin text-blue-600' : ''}`} />
                  </button>
                </div>
              </div>

              {/* FAULT TRIP BANNER & 1-CLICK RESET */}
              {motor?.status === 'FAULT' && (
                <div className="p-4 rounded-3xl bg-rose-50 border-2 border-rose-300 space-y-3 shadow-sm animate-fade-in">
                  <div className="flex items-center gap-3">
                    <span className="p-2.5 rounded-2xl bg-rose-600 text-white flex-shrink-0 animate-pulse">
                      <AlertTriangle className="w-5 h-5 stroke-[2.5]" />
                    </span>
                    <div className="min-w-0">
                      <h3 className="text-xs font-black text-rose-900 uppercase tracking-wide truncate">
                        Pump Fault Tripped: {motor.name}
                      </h3>
                      <p className="text-[11px] text-rose-700 font-medium">
                        Safety latch or dry-run protection active. Reset the pump to return it to standby.
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleResetMotor(motor.id)}
                    disabled={isProcessing || !isOperator}
                    className="w-full py-3 px-4 rounded-2xl bg-rose-600 hover:bg-rose-700 active:scale-95 text-white text-xs font-black flex items-center justify-center gap-2 transition-all cursor-pointer shadow-md shadow-rose-600/25 disabled:opacity-50"
                  >
                    <RotateCcw className="w-4 h-4 stroke-[2.5]" />
                    <span>{isProcessing ? 'RESETTING FAULT...' : 'CLEAR FAULT & RESET PUMP'}</span>
                  </button>
                </div>
              )}

              {/* 2. MOTOR UNITS & CONTROLS SECTION */}
              {motorsList.length > 0 ? (
                /* MOTORS SELECTION & STATUS CARD */
                <div className="p-3.5 rounded-3xl bg-white border border-slate-200 space-y-2.5">
                  <div className="flex items-center justify-between gap-1 text-[11px] font-black tracking-tight text-slate-700 uppercase">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <Sliders className="w-3.5 h-3.5 text-blue-600 flex-shrink-0" />
                      <span className="truncate">{t.selectActiveMotor}</span>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className="px-2 py-0.5 rounded-lg bg-blue-50 border border-blue-200/80 text-[10px] font-bold text-blue-700">
                        {language === 'hi'
                          ? `${motorsList.length} मोटर उपलब्ध`
                          : `${motorsList.length} Unit${motorsList.length !== 1 ? 's' : ''} Configured`}
                      </span>
                      <button
                        type="button"
                        onClick={() => setActiveServiceScreen('SELECT_MOTOR')}
                        className="text-[10px] text-blue-600 hover:text-blue-800 font-bold flex items-center gap-0.5 cursor-pointer"
                      >
                        <span>{language === 'hi' ? 'विवरण' : 'View All'}</span>
                        <ChevronRight className="w-3 h-3" />
                      </button>
                    </div>
                  </div>

                  {/* Motors Grid (Supports 1, 2, or 3+ motors) */}
                  <div
                    className={`grid gap-2 ${
                      motorsList.length === 1
                        ? 'grid-cols-1'
                        : motorsList.length === 2
                        ? 'grid-cols-2'
                        : 'grid-cols-2 sm:grid-cols-3'
                    }`}
                  >
                    {motorsList.map((m) => {
                      const isSelected = motor?.id === m.id;
                      const isRunning = m.status === 'ON' || m.status === 'STARTING';
                      return (
                        <button
                          key={m.id}
                          type="button"
                          onClick={() => handleSelectMotor(m)}
                          className={`p-3 rounded-2xl border text-left flex flex-col justify-between transition-all duration-200 relative overflow-hidden cursor-pointer ${
                            isSelected
                              ? 'bg-blue-50/70 border-blue-500 ring-1 ring-blue-500/30'
                              : 'bg-slate-50/80 hover:bg-slate-100/90 border-slate-200/80 text-slate-600 hover:border-slate-300'
                          }`}
                        >
                          {isSelected && (
                            <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-blue-500 to-cyan-500" />
                          )}

                          <div className="flex items-start justify-between gap-1.5">
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-1.5">
                                <span
                                  className={`w-2 h-2 rounded-full flex-shrink-0 ${
                                    isRunning
                                      ? 'bg-emerald-500 animate-pulse'
                                      : m.status === 'FAULT'
                                      ? 'bg-rose-500'
                                      : 'bg-slate-400'
                                  }`}
                                />
                                <div className="text-xs font-black text-slate-900 truncate">
                                  {m.name}
                                </div>
                              </div>
                              <div className="text-[10px] font-mono text-slate-400 font-semibold mt-0.5 truncate">
                                {m.motor_code} &bull; {m.rated_power ?? 1.5} kW
                              </div>
                            </div>

                            <span
                              className={`px-1.5 py-0.5 rounded-md text-[9px] font-black uppercase tracking-wider flex-shrink-0 ${
                                isRunning
                                  ? 'bg-emerald-100 text-emerald-700'
                                  : m.status === 'FAULT'
                                  ? 'bg-rose-100 text-rose-700'
                                  : 'bg-slate-200 text-slate-600'
                              }`}
                            >
                              {m.status}
                            </span>
                          </div>

                          <div className="flex items-center justify-between pt-2 mt-1.5 border-t border-slate-100 text-[10px] font-bold">
                            <span className={isSelected ? 'text-blue-600 font-bold' : 'text-slate-400'}>
                              {isSelected ? `✓ ${t.active}` : t.select}
                            </span>
                            <span className="font-mono text-slate-500">
                              {isSelected ? `${voltage.toFixed(0)}V • ` : ''}{m.rated_power ?? 1.5}kW
                            </span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ) : (
                /* HERO BANNER CARD (1 MOTOR / DEFAULT STATION) */
                <div className="relative rounded-3xl overflow-hidden border border-slate-200 bg-[#eff6ff] p-5">
                  <div className="absolute right-0 top-0 bottom-0 w-1/2 pointer-events-none overflow-hidden">
                    <img
                      src="/pump-station-hero.png"
                      alt="Industrial Pump Station"
                      className="w-full h-full object-cover object-center opacity-90 mix-blend-multiply"
                    />
                    <div className="absolute inset-0 bg-gradient-to-r from-[#eff6ff] via-[#eff6ff]/50 to-transparent" />
                  </div>

                  <div className="relative z-10 max-w-[62%] space-y-2">
                    <span className="text-[10px] font-black uppercase tracking-wider text-blue-600 block">
                      {t.smartWaterManagement}
                    </span>

                    <h1 className="text-lg sm:text-xl font-black text-slate-900 tracking-tight leading-tight">
                      {t.monitorControlHeader}
                    </h1>

                    <p className="text-[11px] text-slate-600 font-medium pb-1">
                      {t.heroSub}
                    </p>

                    <div className="space-y-1.5 pt-1 text-[11px] font-bold text-slate-800">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                        <span className="truncate">{t.systemOnline}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Droplet className="w-4 h-4 text-blue-600 flex-shrink-0 fill-current" />
                        <span className="truncate">{t.allParametersNormal}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <BarChart2 className="w-4 h-4 text-slate-700 flex-shrink-0" />
                        <span className="truncate">{t.realtimeMonitoring}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Shield className="w-4 h-4 text-slate-700 flex-shrink-0" />
                        <span className="truncate">{t.safeReliableOperation}</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* 3. BCSS ACCOUNT CARD (REPLACED BY LIVE COUNTDOWN TIMER WHEN MOTOR IS STARTED) */}
              {isMotorRunning ? (
                activeTimer && remainingSeconds > 0 && (remainingSeconds <= 60 || activeTimer.is_warning_active) ? (
                  /* PROMINENT 1-MINUTE PRE-EXPIRATION WARNING CARD */
                  <div className="p-4 rounded-3xl bg-amber-50 border-2 border-amber-400 space-y-3">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="p-2 rounded-xl bg-amber-500 text-white">
                          <AlertTriangle className="w-4 h-4 stroke-[2.5]" />
                        </span>
                        <div className="min-w-0">
                          <h3 className="text-xs font-black text-amber-900 uppercase tracking-wide truncate">
                            {t.motorWillStopIn} {remainingSeconds}s
                          </h3>
                          <p className="text-[11px] text-amber-800 font-medium truncate">
                            {activeTimer.schedule_name || t.scheduledOperation}
                          </p>
                        </div>
                      </div>
                      <div className="px-3 py-1.5 rounded-2xl bg-amber-500 text-white font-mono font-black text-sm flex-shrink-0">
                        00:{String(remainingSeconds).padStart(2, '0')}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 pt-1">
                      <button
                        type="button"
                        onClick={() => handleContinueTimer(900)}
                        disabled={isExtending || !isOperator}
                        className="flex-1 py-3 px-3 rounded-2xl bg-amber-600 hover:bg-amber-700 text-white text-xs font-black flex items-center justify-center gap-1.5 transition-all active:scale-95 disabled:opacity-50 cursor-pointer"
                      >
                        <FastForward className="w-4 h-4 stroke-[2.5]" />
                        <span>{isExtending ? 'EXTENDING...' : t.extend15m}</span>
                      </button>

                      <button
                        type="button"
                        onClick={handlePowerToggle}
                        disabled={isProcessing || !isOperator}
                        className="py-3 px-4 rounded-2xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-black flex items-center justify-center gap-1.5 transition-all active:scale-95 disabled:opacity-50 cursor-pointer"
                      >
                        <Square className="w-4 h-4 fill-current" />
                        <span>{t.stopNow}</span>
                      </button>
                    </div>
                  </div>
                ) : (
                  /* ACTIVE RUNNING COUNTDOWN TIMER CARD (REPLACES BCSS ACCOUNT WHEN MOTOR RUNNING) */
                  <div className="p-4 rounded-3xl bg-blue-600 text-white border border-blue-500 space-y-3 relative overflow-hidden">
                    <div className="flex items-center justify-between gap-2 relative z-10">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="p-2 rounded-xl bg-blue-700 text-cyan-200">
                          <Timer className="w-4 h-4" />
                        </span>
                        <div className="min-w-0">
                          <div className="text-[10px] font-black uppercase tracking-wider text-blue-200">
                            {t.pumpActive} &bull; {motor?.name || 'Main Motor'}
                          </div>
                          <div className="text-xs font-bold text-white/95 truncate">
                            {activeTimer?.schedule_name || t.scheduledOperation}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 flex-shrink-0">
                        <div className="px-3 py-1.5 rounded-2xl bg-blue-700 border border-blue-400/40 font-mono font-black text-sm text-white">
                          {remainingSeconds > 0
                            ? `${Math.floor(remainingSeconds / 60)}:${String(remainingSeconds % 60).padStart(2, '0')}`
                            : t.dockRunning}
                        </div>
                        {isOperator && activeTimer && (
                          <button
                            type="button"
                            onClick={() => handleContinueTimer(900)}
                            disabled={isExtending}
                            title="Add 15 minutes to run"
                            className="py-1.5 px-2.5 rounded-xl bg-white hover:bg-blue-50 text-blue-900 text-xs font-black flex items-center gap-1 transition-all active:scale-95 disabled:opacity-50 cursor-pointer"
                          >
                            <Plus className="w-3.5 h-3.5 stroke-[3]" />
                            <span>15m</span>
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Live Telemetry Mini Grid Inside Timer */}
                    <div className="grid grid-cols-3 gap-2 pt-1 border-t border-blue-500/60 text-center relative z-10">
                      <div className="p-2 rounded-2xl bg-blue-700/60 border border-blue-500/40">
                        <div className="text-[9px] font-bold text-blue-200 uppercase">{t.current}</div>
                        <div className="text-xs font-black font-mono mt-0.5">{currentAmps.toFixed(1)} A</div>
                      </div>
                      <div className="p-2 rounded-2xl bg-blue-700/60 border border-blue-500/40">
                        <div className="text-[9px] font-bold text-blue-200 uppercase">{t.voltage}</div>
                        <div className="text-xs font-black font-mono mt-0.5">{voltage.toFixed(0)} V</div>
                      </div>
                      <div className="p-2 rounded-2xl bg-blue-700/60 border border-blue-500/40">
                        <div className="text-[9px] font-bold text-blue-200 uppercase">{t.power}</div>
                        <div className="text-xs font-black font-mono mt-0.5">{powerKw.toFixed(1)} kW</div>
                      </div>
                    </div>
                  </div>
                )
              ) : (
                /* BCSS ACCOUNT CARD (SHOWN ONLY WHEN MOTOR IS IDLE/STOPPED) */
                <button
                  type="button"
                  onClick={() => setActiveServiceScreen('BCSS_ACCOUNT')}
                  className="w-full mobile-card p-4 rounded-2xl flex items-center justify-between bg-white border border-slate-200 hover:border-blue-300 transition-all cursor-pointer text-left"
                >
                  <div className="flex items-center gap-3.5 min-w-0">
                    <div className="w-10 h-10 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-center flex-shrink-0">
                      <WalletCardIcon className="w-6 h-6" />
                    </div>
                    <div>
                      <div className="text-xs font-black text-slate-900 leading-tight">BCSS Account</div>
                      <div className="text-[11px] text-slate-500 font-medium mt-0.5 flex items-center gap-1.5">
                        <span>Balance</span>
                        <span className="text-[#f43f5e] font-bold">₹</span>
                        <span className="font-bold text-slate-900 font-mono">0</span>
                      </div>
                    </div>
                  </div>

                  <div className="w-7 h-7 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center flex-shrink-0">
                    <ChevronRight className="w-4 h-4 stroke-[2.5]" />
                  </div>
                </button>
              )}

              {/* 4. 3x3 SERVICE / FUNCTION GRID */}
              <div className="grid grid-cols-3 gap-3">
                {/* 1. Select Active Motor */}
                <button
                  type="button"
                  onClick={() => setActiveServiceScreen('SELECT_MOTOR')}
                  className="mobile-card p-3.5 sm:p-4 rounded-3xl bg-white border border-slate-200 hover:border-blue-400 transition-all active:scale-[0.98] flex flex-col items-center justify-between aspect-square cursor-pointer text-center group"
                >
                  <div className="w-14 h-14 sm:w-16 sm:h-16 rounded-full bg-[#f0f9ff] flex items-center justify-center group-hover:scale-105 transition-transform my-auto">
                    <MotorIcon className="w-10 h-10 sm:w-12 sm:h-12" />
                  </div>
                  <span className="text-[11px] sm:text-xs font-black text-slate-800 leading-tight text-center mt-1">
                    {t.cardSelectMotor}
                  </span>
                </button>

                {/* 2. Interlocks */}
                <button
                  type="button"
                  onClick={() => setActiveServiceScreen('INTERLOCKS')}
                  className="mobile-card p-3.5 sm:p-4 rounded-3xl bg-white border border-slate-200 hover:border-emerald-400 transition-all active:scale-[0.98] flex flex-col items-center justify-between aspect-square cursor-pointer text-center group"
                >
                  <div className="w-14 h-14 sm:w-16 sm:h-16 rounded-full bg-[#ecfdf5] flex items-center justify-center group-hover:scale-105 transition-transform my-auto">
                    <InterlockIcon className="w-10 h-10 sm:w-12 sm:h-12" />
                  </div>
                  <span className="text-[11px] sm:text-xs font-black text-slate-800 leading-tight text-center mt-1">
                    {t.cardInterlocks}
                  </span>
                </button>

                {/* 3. Tank Level */}
                <button
                  type="button"
                  onClick={() => setActiveServiceScreen('TANK_LEVEL')}
                  className="mobile-card p-3.5 sm:p-4 rounded-3xl bg-white border border-slate-200 hover:border-blue-400 transition-all active:scale-[0.98] flex flex-col items-center justify-between aspect-square cursor-pointer text-center group"
                >
                  <div className="w-14 h-14 sm:w-16 sm:h-16 rounded-full bg-[#f0f9ff] flex items-center justify-center group-hover:scale-105 transition-transform my-auto">
                    <TankLevelIcon className="w-10 h-10 sm:w-12 sm:h-12" />
                  </div>
                  <span className="text-[11px] sm:text-xs font-black text-slate-800 leading-tight text-center mt-1">
                    {t.cardTankLevel}
                  </span>
                </button>

                {/* 4. Sump Level */}
                <button
                  type="button"
                  onClick={() => setActiveServiceScreen('SUMP_LEVEL')}
                  className="mobile-card p-3.5 sm:p-4 rounded-3xl bg-white border border-slate-200 hover:border-blue-400 transition-all active:scale-[0.98] flex flex-col items-center justify-between aspect-square cursor-pointer text-center group"
                >
                  <div className="w-14 h-14 sm:w-16 sm:h-16 rounded-full bg-[#f0f9ff] flex items-center justify-center group-hover:scale-105 transition-transform my-auto">
                    <SumpLevelIcon className="w-10 h-10 sm:w-12 sm:h-12" />
                  </div>
                  <span className="text-[11px] sm:text-xs font-black text-slate-800 leading-tight text-center mt-1">
                    {t.cardSumpLevel}
                  </span>
                </button>

                {/* 5. Flow Rate */}
                <button
                  type="button"
                  onClick={() => setActiveServiceScreen('FLOW_RATE')}
                  className="mobile-card p-3.5 sm:p-4 rounded-3xl bg-white border border-slate-200 hover:border-blue-400 transition-all active:scale-[0.98] flex flex-col items-center justify-between aspect-square cursor-pointer text-center group"
                >
                  <div className="w-14 h-14 sm:w-16 sm:h-16 rounded-full bg-[#f0f9ff] flex items-center justify-center group-hover:scale-105 transition-transform my-auto">
                    <FlowRateIcon className="w-10 h-10 sm:w-12 sm:h-12" />
                  </div>
                  <span className="text-[11px] sm:text-xs font-black text-slate-800 leading-tight text-center mt-1">
                    {t.cardFlowRate}
                  </span>
                </button>

                {/* 6. Water Quality */}
                <button
                  type="button"
                  onClick={() => setActiveServiceScreen('WATER_QUALITY')}
                  className="mobile-card p-3.5 sm:p-4 rounded-3xl bg-white border border-slate-200 hover:border-blue-400 transition-all active:scale-[0.98] flex flex-col items-center justify-between aspect-square cursor-pointer text-center group"
                >
                  <div className="w-14 h-14 sm:w-16 sm:h-16 rounded-full bg-[#f0f9ff] flex items-center justify-center group-hover:scale-105 transition-transform my-auto">
                    <WaterQualityIcon className="w-10 h-10 sm:w-12 sm:h-12" />
                  </div>
                  <span className="text-[11px] sm:text-xs font-black text-slate-800 leading-tight text-center mt-1">
                    {t.cardWaterQuality}
                  </span>
                </button>

                {/* 7. Electrical Load */}
                <button
                  type="button"
                  onClick={() => setActiveServiceScreen('ELECTRICAL_LOAD')}
                  className="mobile-card p-3.5 sm:p-4 rounded-3xl bg-white border border-slate-200 hover:border-amber-400 transition-all active:scale-[0.98] flex flex-col items-center justify-between aspect-square cursor-pointer text-center group"
                >
                  <div className="w-14 h-14 sm:w-16 sm:h-16 rounded-full bg-[#f0f9ff] flex items-center justify-center group-hover:scale-105 transition-transform my-auto">
                    <ElectricalLoadIcon className="w-10 h-10 sm:w-12 sm:h-12" />
                  </div>
                  <span className="text-[11px] sm:text-xs font-black text-slate-800 leading-tight text-center mt-1">
                    {t.cardElectricalLoad}
                  </span>
                </button>

                {/* 8. Pump Schedules */}
                <button
                  type="button"
                  onClick={() => setActiveServiceScreen('SCHEDULES')}
                  className="mobile-card p-3.5 sm:p-4 rounded-3xl bg-white border border-slate-200 hover:border-blue-400 transition-all active:scale-[0.98] flex flex-col items-center justify-between aspect-square cursor-pointer text-center group"
                >
                  <div className="w-14 h-14 sm:w-16 sm:h-16 rounded-full bg-[#f0f9ff] flex items-center justify-center group-hover:scale-105 transition-transform my-auto">
                    <PumpScheduleIcon className="w-10 h-10 sm:w-12 sm:h-12" />
                  </div>
                  <span className="text-[11px] sm:text-xs font-black text-slate-800 leading-tight text-center mt-1">
                    {t.cardSchedules}
                  </span>
                </button>

                {/* 9. Latest Event */}
                <button
                  type="button"
                  onClick={() => setActiveServiceScreen('LATEST_EVENT')}
                  className="mobile-card p-3.5 sm:p-4 rounded-3xl bg-white border border-slate-200 hover:border-slate-400 transition-all active:scale-[0.98] flex flex-col items-center justify-between aspect-square cursor-pointer text-center group"
                >
                  <div className="w-14 h-14 sm:w-16 sm:h-16 rounded-full bg-[#f0f9ff] flex items-center justify-center group-hover:scale-105 transition-transform my-auto">
                    <LatestEventIcon className="w-10 h-10 sm:w-12 sm:h-12" />
                  </div>
                  <span className="text-[11px] sm:text-xs font-black text-slate-800 leading-tight text-center mt-1">
                    {t.cardLatestEvent}
                  </span>
                </button>
              </div>
            </>
          )}
        </>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: SCHEDULES (FULL VIEW) */}
      {/* ========================================================================= */}
      {activeTab === 'SCHEDULES' && (
        <SchedulesScreen
          onBack={() => setActiveTab('HOME')}
          schedules={schedules}
          motors={motorsList.length > 0 ? motorsList : (motor ? [motor] : [])}
          activeMotor={motor}
          onOpenAddSchedule={() => setIsScheduleModalOpen(true)}
          onToggleScheduleActive={handleToggleScheduleActive}
          onDeleteSchedule={(s) => setScheduleToDelete(s)}
          onRefresh={() => loadData(true)}
          isSyncing={isSyncing}
        />
      )}

      {/* ========================================================================= */}
      {/* TAB 3: HISTORY (FULL VIEW) */}
      {/* ========================================================================= */}
      {activeTab === 'HISTORY' && (
        <LatestEventsScreen
          onBack={() => setActiveTab('HOME')}
          runSessions={runSessions}
          filteredSessions={filteredSessions}
          filteredEvents={filteredEvents}
          motors={motorsList}
          historyMotorFilter={historyMotorFilter}
          setHistoryMotorFilter={setHistoryMotorFilter}
          historyTypeFilter={historyTypeFilter}
          setHistoryTypeFilter={setHistoryTypeFilter}
          historyViewMode={historyViewMode}
          setHistoryViewMode={setHistoryViewMode}
          historyMetrics={historyMetrics}
          onRefresh={() => loadData(true)}
          isSyncing={isSyncing}
          parseIsoDate={parseIsoDate}
          formatDurationSecs={formatDurationSecs}
        />
      )}

      {/* ========================================================================= */}
      {/* TAB 4: SETTINGS (FULL OPERATOR CONTROL & ADVANCED ADMIN) */}
      {/* ========================================================================= */}
      {activeTab === 'SETTINGS' && (
        <div className="space-y-4 animate-fade-in">
          <div className="flex items-center justify-between pt-1">
            <div>
              <h2 className="text-base font-black text-slate-900 tracking-tight leading-tight">
                PUMP &amp; SYSTEM SETTINGS
              </h2>
              <p className="text-[11px] text-slate-400 font-medium">
                Adjust cutoffs, dry-run protection, water quality &amp; manage subscriptions
              </p>
            </div>
            <button
              onClick={() => loadData(true)}
              disabled={isSyncing}
              className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors cursor-pointer"
              title="Refresh Settings"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin text-blue-600' : ''}`} />
            </button>
          </div>

          {/* 1. OPERATIONAL SAFETY THRESHOLDS CARD */}
          <div className="mobile-card p-4 space-y-4 border-2 border-blue-500/20">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-700 flex items-center justify-center">
                  <SlidersHorizontal className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-xs font-black text-slate-900 uppercase tracking-tight">
                    Safety Cutoff Thresholds
                  </h3>
                  <p className="text-[10px] text-slate-400">Set automatic stop levels &amp; sensor trips</p>
                </div>
              </div>
              <span className="px-2 py-0.5 rounded-lg bg-blue-100 text-blue-800 text-[10px] font-black">
                OPERATOR CONTROL
              </span>
            </div>

            {/* THRESHOLD 1: OVERHEAD TANK STOP LEVEL */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-black text-slate-800 flex items-center gap-1.5">
                  <Waves className="w-3.5 h-3.5 text-blue-600 shrink-0" />
                  <span>Tank Auto-Stop Level</span>
                </label>
                <div className="flex items-center gap-1">
                  <span className="text-sm font-black text-blue-700 font-mono">{tankStopThreshold}%</span>
                  <span className="text-[10px] text-slate-400 font-medium">Cutoff</span>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min="70"
                  max="100"
                  step="1"
                  value={tankStopThreshold}
                  onChange={(e) => setTankStopThreshold(Number(e.target.value))}
                  className="flex-1 accent-blue-600 cursor-pointer h-2 bg-slate-100 rounded-lg"
                />
                <input
                  type="number"
                  min="70"
                  max="100"
                  value={tankStopThreshold}
                  onChange={(e) => setTankStopThreshold(Math.max(70, Math.min(100, Number(e.target.value))))}
                  className="w-14 px-2 py-1 text-xs font-black text-center font-mono rounded-lg border border-slate-200 bg-white"
                />
              </div>
            </div>

            {/* THRESHOLD 2: SUMP DRY-RUN CUTOFF */}
            <div className="space-y-1.5 pt-2 border-t border-slate-100">
              <div className="flex items-center justify-between">
                <label className="text-xs font-black text-slate-800 flex items-center gap-1.5">
                  <Droplet className="w-3.5 h-3.5 text-cyan-600 shrink-0" />
                  <span>Sump Dry-Run Protection Level</span>
                </label>
                <div className="flex items-center gap-1">
                  <span className="text-sm font-black text-cyan-700 font-mono">{sumpDryRunThreshold}%</span>
                  <span className="text-[10px] text-slate-400 font-medium">Min Source</span>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min="5"
                  max="40"
                  step="1"
                  value={sumpDryRunThreshold}
                  onChange={(e) => setSumpDryRunThreshold(Number(e.target.value))}
                  className="flex-1 accent-cyan-600 cursor-pointer h-2 bg-slate-100 rounded-lg"
                />
                <input
                  type="number"
                  min="5"
                  max="40"
                  value={sumpDryRunThreshold}
                  onChange={(e) => setSumpDryRunThreshold(Math.max(5, Math.min(40, Number(e.target.value))))}
                  className="w-14 px-2 py-1 text-xs font-black text-center font-mono rounded-lg border border-slate-200 bg-white"
                />
              </div>
            </div>

            {/* THRESHOLD 3: WATER TURBIDITY */}
            <div className="space-y-1.5 pt-2 border-t border-slate-100">
              <div className="flex items-center justify-between">
                <label className="text-xs font-black text-slate-800 flex items-center gap-1.5">
                  <Shield className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                  <span>Turbidity Max Safe Limit</span>
                </label>
                <div className="flex items-center gap-1">
                  <span className="text-sm font-black text-amber-700 font-mono">{turbidityStopThreshold} NTU</span>
                  <span className="text-[10px] text-slate-400 font-medium">Max Murkiness</span>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min="5"
                  max="50"
                  step="1"
                  value={turbidityStopThreshold}
                  onChange={(e) => setTurbidityStopThreshold(Number(e.target.value))}
                  className="flex-1 accent-amber-500 cursor-pointer h-2 bg-slate-100 rounded-lg"
                />
                <input
                  type="number"
                  min="5"
                  max="50"
                  value={turbidityStopThreshold}
                  onChange={(e) => setTurbidityStopThreshold(Math.max(5, Math.min(50, Number(e.target.value))))}
                  className="w-14 px-2 py-1 text-xs font-black text-center font-mono rounded-lg border border-slate-200 bg-white"
                />
              </div>
            </div>

            {/* TOGGLES */}
            <div className="space-y-2 pt-2 border-t border-slate-100">
              <label className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 border border-slate-200/60 cursor-pointer">
                <div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-bold text-slate-800">Auto-Stop on Tank Overflow</span>
                    <span className="px-1.5 py-0.5 rounded-md text-[9px] font-black bg-teal-100 text-teal-800 border border-teal-200">STANDBY STOP</span>
                  </div>
                  <div className="text-[10px] text-slate-400">Safely stop pump into ready standby when tank is full (not fault)</div>
                </div>
                <input
                  type="checkbox"
                  checked={autoStopTankFull}
                  onChange={(e) => setAutoStopTankFull(e.target.checked)}
                  className="w-4 h-4 accent-blue-600 rounded cursor-pointer"
                />
              </label>

              <label className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 border border-slate-200/60 cursor-pointer">
                <div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-bold text-slate-800">Auto-Cutoff on High Turbidity</span>
                    <span className="px-1.5 py-0.5 rounded-md text-[9px] font-black bg-purple-100 text-purple-800 border border-purple-200">STANDBY STOP</span>
                  </div>
                  <div className="text-[10px] text-slate-400">Safely pause pump on murky/dirty water (not a motor fault)</div>
                </div>
                <input
                  type="checkbox"
                  checked={autoStopTurbidity}
                  onChange={(e) => setAutoStopTurbidity(e.target.checked)}
                  className="w-4 h-4 accent-blue-600 rounded cursor-pointer"
                />
              </label>

              <label className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 border border-slate-200/60 cursor-pointer">
                <div>
                  <div className="text-xs font-bold text-slate-800">Offline Gateway Timeout Alert</div>
                  <div className="text-[10px] text-slate-400">Notify immediately if ESP32 controller disconnects</div>
                </div>
                <input
                  type="checkbox"
                  checked={offlineAlertEnabled}
                  onChange={(e) => setOfflineAlertEnabled(e.target.checked)}
                  className="w-4 h-4 accent-blue-600 rounded cursor-pointer"
                />
              </label>
            </div>

            {/* SAVE BUTTON */}
            <button
              type="button"
              onClick={handleSaveOperationalSettings}
              disabled={isSavingSettings || !isOperator}
              className="w-full py-3 rounded-2xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-black flex items-center justify-center gap-2 transition-all cursor-pointer disabled:opacity-50"
            >
              {isSavingSettings ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              <span>{isSavingSettings ? 'SAVING SETTINGS...' : 'SAVE OPERATIONAL THRESHOLDS'}</span>
            </button>
          </div>

          {/* 2. AUTOMATION & HARDWARE SHORTCUTS */}
          <div className="space-y-2">
            <h4 className="text-xs font-black uppercase tracking-wider text-slate-400 px-1">
              Automation &amp; Hardware Controls
            </h4>

            <div className="mobile-card p-4 space-y-2.5">
              <button
                type="button"
                onClick={() => setIsScheduleModalOpen(true)}
                className="w-full py-2.5 px-3 rounded-xl bg-blue-50 hover:bg-blue-100 text-blue-800 text-xs font-bold flex items-center justify-between transition-colors border border-blue-200/60 cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-blue-600" />
                  <span>Manage Automation Schedules</span>
                </div>
                <span className="text-[10px] font-bold text-blue-700 bg-white px-2 py-0.5 rounded-md border border-blue-200">
                  {schedules.length} Slots
                </span>
              </button>

              <button
                type="button"
                onClick={() => setIsNotificationModalOpen(true)}
                className="w-full py-2.5 px-3 rounded-xl bg-amber-50 hover:bg-amber-100 text-amber-800 text-xs font-bold flex items-center justify-between transition-colors border border-amber-200/60 cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  <Bell className="w-4 h-4 text-amber-600" />
                  <span>Notification Channels &amp; Buzzer Audio</span>
                </div>
                <span className="text-[10px] font-bold text-amber-700 bg-white px-2 py-0.5 rounded-md border border-amber-200">
                  Configure
                </span>
              </button>

              {station && (
                <button
                  type="button"
                  onClick={() => setIsCommissionModalOpen(true)}
                  className="w-full py-2.5 px-3 rounded-xl bg-slate-50 hover:bg-slate-100 text-slate-800 text-xs font-bold flex items-center justify-between transition-colors border border-slate-200/60 cursor-pointer"
                >
                  <div className="flex items-center gap-2">
                    <Cpu className="w-4 h-4 text-slate-600" />
                    <span>Pair / Commission New Controller</span>
                  </div>
                  <span className="text-[10px] font-bold text-slate-600 bg-white px-2 py-0.5 rounded-md border border-slate-200">
                    Add Device
                  </span>
                </button>
              )}
            </div>
          </div>

          {/* 3. BUSINESS ADMIN SECTION */}
          {isAdmin && (
            <div className="space-y-2">
              <h4 className="text-xs font-black uppercase tracking-wider text-purple-700 px-1 flex items-center gap-1.5">
                <Crown className="w-3.5 h-3.5 text-purple-600" />
                <span>Business Administration</span>
              </h4>

              <div className="mobile-card p-4 space-y-3 bg-gradient-to-r from-purple-500/10 via-slate-50 to-purple-500/10 border-purple-200">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs font-black text-slate-900">User Accounts &amp; Subscription</div>
                    <div className="text-[10px] text-slate-500">
                      Add operators, set employee roles &amp; manage enterprise subscription quotas
                    </div>
                  </div>
                  <span className="px-2 py-0.5 rounded-lg bg-purple-100 text-purple-800 text-[10px] font-black">
                    ADMIN ONLY
                  </span>
                </div>

                <button
                  type="button"
                  onClick={() => setIsAdminModalOpen(true)}
                  className="w-full py-3 rounded-2xl bg-slate-900 hover:bg-purple-900 text-white text-xs font-black flex items-center justify-center gap-2 transition-all cursor-pointer"
                >
                  <Crown className="w-4 h-4 text-purple-300" />
                  <span>MANAGE USERS &amp; SUBSCRIPTION PLANS</span>
                </button>
              </div>
            </div>
          )}

          {/* 4. ACCOUNT & SIGN OUT */}
          <div className="mobile-card p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xs font-bold text-slate-900">Signed In User</div>
                <div className="text-[11px] text-slate-500">{user?.email}</div>
              </div>
              <span className="px-2.5 py-1 rounded-xl bg-purple-50 text-purple-700 text-xs font-bold">
                {user?.role}
              </span>
            </div>

            {onAdminSwitch && (
              <button
                type="button"
                onClick={onAdminSwitch}
                className="w-full py-2.5 rounded-xl bg-blue-50 hover:bg-blue-100 text-blue-700 text-xs font-bold flex items-center justify-center gap-2 transition-colors border border-blue-200 cursor-pointer"
              >
                <Shield className="w-4 h-4" />
                <span>Switch to Advanced Admin Console</span>
              </button>
            )}

            <button
              type="button"
              onClick={logout}
              className="w-full py-2.5 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-700 text-xs font-bold flex items-center justify-center gap-2 transition-colors border border-rose-200 cursor-pointer"
            >
              <LogOut className="w-4 h-4" />
              <span>Sign Out</span>
            </button>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* BOTTOM NAVIGATION DOCK */}
      {/* ========================================================================= */}
      <MobileNavDock
        activeTab={activeTab}
        onTabChange={(t) => {
          setActiveTab(t);
          setActiveServiceScreen(null);
          loadData();
        }}
        isMotorRunning={isMotorRunning}
        isProcessing={isProcessing}
        onPowerToggle={handlePowerToggle}
        motorStatus={motor?.status}
      />

      {/* Schedule Manager Modal */}
      {station && (
        <ScheduleManagerModal
          isOpen={isScheduleModalOpen}
          onClose={() => {
            setIsScheduleModalOpen(false);
            loadData();
          }}
          station={station}
          motors={motorsList.length > 0 ? motorsList : (motor ? [motor] : [])}
        />
      )}

      {/* Notification Preferences Modal */}
      <NotificationPreferencesModal
        isOpen={isNotificationModalOpen}
        onClose={() => setIsNotificationModalOpen(false)}
      />

      {/* Device Commissioning Modal */}
      {station && (
        <DeviceCommissioningModal
          isOpen={isCommissionModalOpen}
          onClose={() => setIsCommissionModalOpen(false)}
          station={station}
          onDeviceCommissioned={() => {
            loadData();
          }}
        />
      )}

      {/* Start Motor with Scheduled Closing Time Modal */}
      {motor && (
        <StartMotorModal
          isOpen={isStartModalOpen}
          onClose={() => setIsStartModalOpen(false)}
          motor={motor}
          onConfirmStart={handleConfirmStartMotor}
          isProcessing={isProcessing}
        />
      )}

      {/* Admin User & Subscription Management Modal */}
      <UserSubscriptionAdminModal
        isOpen={isAdminModalOpen}
        onClose={() => {
          setIsAdminModalOpen(false);
          loadData();
        }}
      />

      {/* Schedule Delete Confirmation Popup */}
      {scheduleToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-fade-in font-sans">
          <div className="bg-white w-full max-w-sm rounded-2xl p-5 border border-slate-200 space-y-4 shadow-2xl">
            <div className="flex items-center gap-3 text-rose-600">
              <div className="w-10 h-10 rounded-2xl bg-rose-50 flex items-center justify-center shrink-0">
                <Trash2 className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-black text-slate-900">Delete Schedule?</h3>
                <p className="text-[11px] text-slate-400">This routine will stop executing.</p>
              </div>
            </div>

            <div className="p-3 bg-slate-50 rounded-2xl border border-slate-100 text-xs space-y-1">
              <div className="font-bold text-slate-800">{scheduleToDelete.name}</div>
              <div className="text-[11px] text-slate-500">
                Start: {scheduleToDelete.start_time} &bull; Duration: {Math.round(scheduleToDelete.duration_seconds / 60)} min
              </div>
            </div>

            <div className="flex items-center gap-2 pt-1">
              <button
                type="button"
                onClick={() => setScheduleToDelete(null)}
                className="flex-1 py-2.5 rounded-xl border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-bold cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => handleDeleteScheduleDirect(scheduleToDelete)}
                className="flex-1 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-black cursor-pointer"
              >
                Confirm Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
