import React, { useState, useEffect, useCallback } from 'react';
import {
  Waves,
  Droplet,
  Gauge,
  Shield,
  Zap,
  Activity,
  Clock,
  RefreshCw,
  Plus,
  AlertTriangle,
  CheckCircle2,
  Calendar,
  LogOut,
  Bell,
  Cpu,
  Timer,
  FastForward,
  Square,
  Sliders,
  History,
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
import { ws } from '../services/ws';
import { useAuth } from '../context/AuthContext';
import { MobileNavDock, MobileTab } from '../components/MobileNavDock';
import { ScheduleManagerModal } from '../components/ScheduleManagerModal';
import { NotificationPreferencesModal } from '../components/NotificationPreferencesModal';
import { DeviceCommissioningModal } from '../components/DeviceCommissioningModal';
import { StartMotorModal } from '../components/StartMotorModal';
import { audioAlert } from '../utils/audioAlert';

interface PumpRunSession {
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

function formatDurationSecs(seconds: number): string {
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
  const [activeTab, setActiveTab] = useState<MobileTab>('HOME');

  const [site, setSite] = useState<Site | null>(null);
  const [station, setStation] = useState<Station | null>(null);
  const [controller, setController] = useState<Controller | null>(null);
  const [motor, setMotor] = useState<Motor | null>(null);
  const [motorsList, setMotorsList] = useState<Motor[]>([]);
  const [recentEvents, setRecentEvents] = useState<MotorEventResponse[]>([]);
  const [schedules, setSchedules] = useState<ScheduleResponse[]>([]);
  const [activeTimer, setActiveTimer] = useState<MotorTimerStatus | null>(null);
  const [remainingSeconds, setRemainingSeconds] = useState<number>(0);
  const [isExtending, setIsExtending] = useState<boolean>(false);
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState<boolean>(false);
  const [isNotificationModalOpen, setIsNotificationModalOpen] = useState<boolean>(false);
  const [isCommissionModalOpen, setIsCommissionModalOpen] = useState<boolean>(false);
  const [isStartModalOpen, setIsStartModalOpen] = useState<boolean>(false);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // History Section Filters & View State
  const [historyMotorFilter, setHistoryMotorFilter] = useState<string>('ALL');
  const [historyTypeFilter, setHistoryTypeFilter] = useState<string>('ALL');
  const [historyViewMode, setHistoryViewMode] = useState<'SESSIONS' | 'TIMELINE'>('SESSIONS');

  // Live telemetry state
  const [tankLevel, setTankLevel] = useState<number>(75.0);
  const [sumpLevel, setSumpLevel] = useState<number>(85.0);
  const [waterHeadMeters, setWaterHeadMeters] = useState<number>(24.5);
  const [flowRateLpm, setFlowRateLpm] = useState<number>(0.0);
  const [turbidity, setTurbidity] = useState<number>(6.0);
  const [ph, setPh] = useState<number>(7.2);
  const [currentAmps, setCurrentAmps] = useState<number>(0.0);
  const [voltage, setVoltage] = useState<number>(230.0);
  const [powerKw, setPowerKw] = useState<number>(0.0);

  // Hierarchy Refs for zero-latency caching
  const siteRef = React.useRef<Site | null>(null);
  const stationRef = React.useRef<Station | null>(null);
  const controllerRef = React.useRef<Controller | null>(null);
  const motorsListRef = React.useRef<Motor[]>([]);
  const motorRef = React.useRef<Motor | null>(null);
  const isFetchingRef = React.useRef<boolean>(false);
  const debounceSyncRef = React.useRef<any>(null);

  // Keep refs in sync with state
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
    motorsListRef.current = motorsList;
  }, [motorsList]);
  useEffect(() => {
    motorRef.current = motor;
  }, [motor]);

  // Derived state
  const isMotorRunning = motor?.status === 'ON';

  // High-performance background sync with smart hierarchy caching
  const loadData = useCallback(async (showVisualSpinner = false) => {
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;
    if (showVisualSpinner) setIsSyncing(true);

    try {
      let curSite = siteRef.current;
      let curStation = stationRef.current;
      let curController = controllerRef.current;
      let curMotors = motorsListRef.current;

      // 1. Initial Hierarchy Discovery (only executed once if not already cached)
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
        curController = controllers[0];
        setController(curController);
        controllerRef.current = curController;

        const motorResults = await Promise.all(controllers.map((c) => api.getMotors(c.id)));
        curMotors = motorResults.flat();
        if (curMotors && curMotors.length > 0) {
          setMotorsList(curMotors);
          motorsListRef.current = curMotors;
          if (!motorRef.current) {
            setMotor(curMotors[0]);
            motorRef.current = curMotors[0];
          }
        }
      }

      const activeTarget = motorRef.current || curMotors[0];
      const targetMotorId = activeTarget?.id;

      // 2. Parallel fetch only dynamic runtime metrics
      const [eventsRes, wqRes, schedRes, elecRes, flowRes, timerRes] =
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
        ]);

      // 1. Process Event History
      if (eventsRes.status === 'fulfilled' && eventsRes.value) {
        setRecentEvents(eventsRes.value);
      }

      // 2. Process Water Quality
      if (wqRes.status === 'fulfilled' && wqRes.value) {
        if (wqRes.value.turbidity_ntu !== undefined && wqRes.value.turbidity_ntu !== null) {
          setTurbidity(wqRes.value.turbidity_ntu);
        }
        if (wqRes.value.ph !== undefined && wqRes.value.ph !== null) {
          setPh(wqRes.value.ph);
        }
      }

      // 3. Process Schedules
      if (schedRes.status === 'fulfilled' && schedRes.value) {
        setSchedules(schedRes.value);
      }

      // 4. Process Electrical Metrics
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

      // 5. Process Flow Diagnostics
      if (flowRes.status === 'fulfilled' && flowRes.value) {
        if (flowRes.value.flow_rate_lpm !== undefined && flowRes.value.flow_rate_lpm !== null) {
          setFlowRateLpm(flowRes.value.flow_rate_lpm);
        }
      }

      // 6. Process Active Timer
      if (timerRes.status === 'fulfilled' && timerRes.value) {
        const timerVal = timerRes.value;
        if (timerVal.is_running && timerVal.remaining_seconds > 0) {
          setActiveTimer(timerVal);
          setRemainingSeconds(Math.max(0, Math.round(timerVal.remaining_seconds)));
        } else {
          setActiveTimer(null);
          setRemainingSeconds(0);
          if (timerVal.status === 'OFF' || !timerVal.is_running) {
            setMotor((prev) => (prev && prev.status === 'ON' && !timerVal.is_running ? { ...prev, status: 'OFF' } : prev));
            setMotorsList((prev) =>
              prev.map((m) => (m.id === targetMotorId && !timerVal.is_running ? { ...m, status: 'OFF' } : m))
            );
          }
        }
      }
    } catch {
      // Silent non-blocking fallback
    } finally {
      isFetchingRef.current = false;
      if (showVisualSpinner) setIsSyncing(false);
    }
  }, []);

  // Debounced non-blocking scheduler sync
  const debouncedSync = useCallback((delay = 300) => {
    if (debounceSyncRef.current) clearTimeout(debounceSyncRef.current);
    debounceSyncRef.current = setTimeout(() => {
      loadData(false);
    }, delay);
  }, [loadData]);

  // Handle Switching Active Motor Unit
  const handleSelectMotor = async (selected: Motor) => {
    if (motor?.id === selected.id) return;
    setMotor(selected);
    setIsSyncing(true);
    try {
      const [timerRes, eventsRes, elecRes, flowRes] = await Promise.allSettled([
        api.getMotorTimer(selected.id),
        station
          ? api.getStationEvents(station.id, { limit: 100 })
          : api.getMotorEvents(selected.id, { limit: 100 }),
        api.getElectricalMetrics(selected.id),
        api.getFlowDiagnostics(selected.id),
      ]);

      if (timerRes.status === 'fulfilled' && timerRes.value && timerRes.value.is_running) {
        setActiveTimer(timerRes.value);
        setRemainingSeconds(Math.max(0, Math.round(timerRes.value.remaining_seconds)));
      } else {
        setActiveTimer(null);
        setRemainingSeconds(0);
      }

      if (eventsRes.status === 'fulfilled' && eventsRes.value) {
        setRecentEvents(eventsRes.value);
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

      setToastMessage(`Switched active control to ${selected.name} (${selected.motor_code})`);
      setTimeout(() => setToastMessage(null), 2500);
    } catch {
      // non-blocking fallback
    } finally {
      setIsSyncing(false);
    }
  };

  // Derive pump run sessions from event history
  const runSessions: PumpRunSession[] = React.useMemo(() => {
    const sessions: PumpRunSession[] = [];
    const eventsByMotor: Record<string, MotorEventResponse[]> = {};

    // Group events by motor_id
    recentEvents.forEach((ev) => {
      const mId = ev.motor_id || (motor ? motor.id : 'default-motor');
      if (!eventsByMotor[mId]) eventsByMotor[mId] = [];
      eventsByMotor[mId].push(ev);
    });

    Object.keys(eventsByMotor).forEach((mId) => {
      const mEvents = [...eventsByMotor[mId]].sort(
        (a, b) => parseIsoDate(a.occurred_at).getTime() - parseIsoDate(b.occurred_at).getTime()
      );
      const motorObj = motorsList.find((m) => m.id === mId) || (motor?.id === mId ? motor : null);
      const mCode = motorObj?.motor_code || 'DEMO-MOTOR-001';
      const mName = motorObj?.name || 'Water Pump';

      for (let i = 0; i < mEvents.length; i++) {
        const ev = mEvents[i];
        if (ev.event_type === 'STARTED') {
          const nextStop = mEvents
            .slice(i + 1)
            .find(
              (e) =>
                e.event_type === 'STOPPED' ||
                e.event_type === 'FAULT' ||
                e.event_type === 'EMERGENCY_STOP'
            );
          const isCurrentlyRunning =
            !nextStop && (motorObj?.status === 'ON' || motorObj?.status === 'STARTING');

          let durSecs = 0;
          let stopTime: string | null = null;
          let sessionStatus: 'COMPLETED' | 'RUNNING' | 'TRIPPED' = 'COMPLETED';

          if (nextStop) {
            stopTime = nextStop.occurred_at;
            const diffSecs = Math.max(
              1,
              Math.round(
                (parseIsoDate(nextStop.occurred_at).getTime() - parseIsoDate(ev.occurred_at).getTime()) /
                  1000
              )
            );
            durSecs = nextStop.event_payload?.runtime_seconds || diffSecs;
            sessionStatus =
              nextStop.event_type === 'FAULT' || nextStop.event_type === 'EMERGENCY_STOP'
                ? 'TRIPPED'
                : 'COMPLETED';
          } else if (isCurrentlyRunning) {
            stopTime = null;
            durSecs = Math.max(
              1,
              Math.round((Date.now() - parseIsoDate(ev.occurred_at).getTime()) / 1000)
            );
            sessionStatus = 'RUNNING';
          } else {
            durSecs = ev.event_payload?.duration_seconds || 1800;
            stopTime = new Date(parseIsoDate(ev.occurred_at).getTime() + durSecs * 1000).toISOString();
            sessionStatus = 'COMPLETED';
          }

          let trigger: 'SCHEDULED' | 'MANUAL' | 'PROTECTION' | 'SYSTEM' = 'MANUAL';
          const desc = (ev.description || '').toLowerCase();
          const payloadStr = JSON.stringify(ev.event_payload || {}).toLowerCase();
          if (
            ev.source === 'AUTOMATION' ||
            desc.includes('schedule') ||
            payloadStr.includes('schedule') ||
            payloadStr.includes('timer')
          ) {
            trigger = 'SCHEDULED';
          } else if (
            ev.source === 'USER' ||
            desc.includes('manual') ||
            payloadStr.includes('manual')
          ) {
            trigger = 'MANUAL';
          } else if (desc.includes('safety') || desc.includes('trip') || desc.includes('fault')) {
            trigger = 'PROTECTION';
          } else {
            trigger = 'SCHEDULED';
          }

          const schedName =
            ev.event_payload?.schedule_name ||
            (desc.includes('schedule') ? ev.description?.replace(/^Schedule:\s*/i, '') : undefined);

          // Calculate precise reason why motor closed/stopped
          let stopReason = 'Normal Stop';
          let stopReasonCat: PumpRunSession['stopReasonCategory'] = 'NORMAL';
          let stopReasonDetails = 'Motor cycle ended';

          if (isCurrentlyRunning) {
            stopReason = 'Currently Running / Active';
            stopReasonCat = 'RUNNING';
            stopReasonDetails = 'Motor is actively running and pumping water in real-time.';
          } else if (nextStop) {
            const stopDesc = (nextStop.description || '').toLowerCase();
            const stopPayload = nextStop.event_payload || {};
            const stopReasonCode = String(stopPayload.reason || '').toUpperCase();
            const stopPayloadStr = JSON.stringify(stopPayload).toLowerCase();

            if (
              nextStop.event_type === 'EMERGENCY_STOP' ||
              stopReasonCode.includes('EMERGENCY') ||
              stopDesc.includes('emergency')
            ) {
              stopReasonCat = 'EMERGENCY_STOP';
              stopReason = 'Emergency Stop Activated';
              stopReasonDetails =
                nextStop.description || 'Immediate emergency safety stop command engaged.';
            } else if (
              stopReasonCode.includes('TANK_FULL') ||
              stopDesc.includes('tank full') ||
              stopDesc.includes('overhead tank') ||
              stopPayloadStr.includes('tank_full')
            ) {
              stopReasonCat = 'TANK_FULL';
              const lvl = stopPayload.water_level || stopPayload.level;
              stopReason = lvl ? `Tank Full Auto-Cutoff (${lvl}%)` : 'Tank Full Auto-Cutoff';
              stopReasonDetails =
                'Overhead storage tank reached high capacity threshold (>=95%). Auto-stopped to prevent overflow.';
            } else if (
              stopReasonCode.includes('TURBIDITY') ||
              stopDesc.includes('turbidity') ||
              stopPayloadStr.includes('turbidity')
            ) {
              stopReasonCat = 'TURBIDITY';
              const ntu = stopPayload.turbidity || stopPayload.value;
              stopReason = ntu
                ? `Turbidity Cutoff (${ntu} NTU)`
                : 'Turbidity Cutoff (Water Quality Protection)';
              stopReasonDetails =
                'Water turbidity exceeded purity safety limit (> 5.0 NTU). Pump auto-isolated.';
            } else if (
              stopReasonCode.includes('DRY_RUN') ||
              stopDesc.includes('dry run') ||
              stopDesc.includes('low flow') ||
              stopPayloadStr.includes('dry_run')
            ) {
              stopReasonCat = 'DRY_RUN';
              stopReason = 'Dry-Run Protection Trip';
              stopReasonDetails =
                'No water flow detected during motor run. Pump tripped to prevent motor overheating.';
            } else if (
              nextStop.event_type === 'FAULT' ||
              (nextStop.source as string) === 'SAFETY_INTERLOCK' ||
              stopReasonCode.includes('FAULT') ||
              stopDesc.includes('fault') ||
              stopDesc.includes('trip')
            ) {
              stopReasonCat = 'FAULT';
              stopReason = nextStop.description || 'Safety Interlock / Fault Cutoff';
              stopReasonDetails =
                'Safety interlock or electrical protection trip engaged.';
            } else if (
              stopReasonCode === 'TIMER_EXPIRED' ||
              stopReasonCode === 'SCHEDULE_COMPLETED' ||
              stopDesc.includes('timer expired') ||
              stopDesc.includes('schedule completed') ||
              (nextStop.source === 'AUTOMATION' && (schedName || trigger === 'SCHEDULED'))
            ) {
              stopReasonCat = 'SCHEDULE_END';
              stopReason = schedName
                ? `Schedule Finished: ${schedName}`
                : 'Timer / Scheduled Duration Completed';
              stopReasonDetails = `Target run time (${formatDurationSecs(
                durSecs
              )}) elapsed normally. Auto-shutdown complete.`;
            } else if (
              nextStop.source === 'USER' ||
              stopReasonCode === 'MANUAL_STOP' ||
              stopDesc.includes('manual') ||
              stopDesc.includes('operator')
            ) {
              stopReasonCat = 'MANUAL_STOP';
              stopReason = 'Manual Operator Stop';
              stopReasonDetails = 'Pump was stopped manually from dashboard or physical switch.';
            } else {
              if (trigger === 'SCHEDULED' || schedName) {
                stopReasonCat = 'SCHEDULE_END';
                stopReason = schedName ? `Schedule Concluded: ${schedName}` : 'Schedule Auto-Stop';
                stopReasonDetails = 'Target scheduled cycle completed.';
              } else {
                stopReasonCat = 'MANUAL_STOP';
                stopReason = nextStop.description || 'Normal Shutdown';
                stopReasonDetails = 'Motor cycle ended.';
              }
            }
          } else {
            if (trigger === 'SCHEDULED' || schedName) {
              stopReasonCat = 'SCHEDULE_END';
              stopReason = schedName ? `Schedule Completed: ${schedName}` : 'Schedule Completed';
              stopReasonDetails = 'Automated schedule cycle completed.';
            } else {
              stopReasonCat = 'MANUAL_STOP';
              stopReason = 'Cycle Completed';
              stopReasonDetails = 'Operation cycle concluded.';
            }
          }

          sessions.push({
            id: `session-${ev.id}`,
            motorId: mId,
            motorCode: mCode,
            motorName: mName,
            startTime: ev.occurred_at,
            stopTime: stopTime,
            durationSeconds: durSecs,
            triggerType: trigger,
            scheduleName: schedName,
            description: ev.description || undefined,
            isRunning: isCurrentlyRunning,
            status: sessionStatus,
            stopReason: stopReason,
            stopReasonCategory: stopReasonCat,
            stopReasonDetails: stopReasonDetails,
          });
        }
      }
    });

    // Fallback: If no paired started events exist yet but we have active motor
    if (sessions.length === 0 && (motor?.status === 'ON' || motor?.status === 'STARTING')) {
      sessions.push({
        id: 'active-session-now',
        motorId: motor.id,
        motorCode: motor.motor_code,
        motorName: motor.name,
        startTime: activeTimer?.started_at || new Date().toISOString(),
        stopTime: null,
        durationSeconds: activeTimer?.elapsed_seconds || 120,
        triggerType: activeTimer?.source === 'SCHEDULED' ? 'SCHEDULED' : 'MANUAL',
        scheduleName: activeTimer?.schedule_name || undefined,
        description: 'Currently Active Pump Run',
        isRunning: true,
        status: 'RUNNING',
        stopReason: 'Currently Running / Active',
        stopReasonCategory: 'RUNNING',
        stopReasonDetails: 'Motor is actively pumping water in real time.',
      });
    }

    return sessions.sort(
      (a, b) => parseIsoDate(b.startTime).getTime() - parseIsoDate(a.startTime).getTime()
    );
  }, [recentEvents, motorsList, motor, activeTimer]);

  // Aggregate Metrics for History Dashboard
  const historyMetrics = React.useMemo(() => {
    let totalSecs = 0;
    let scheduledSecs = 0;
    let scheduledCount = 0;
    let manualSecs = 0;
    let manualCount = 0;

    runSessions.forEach((s) => {
      totalSecs += s.durationSeconds;
      if (s.triggerType === 'SCHEDULED') {
        scheduledSecs += s.durationSeconds;
        scheduledCount += 1;
      } else if (s.triggerType === 'MANUAL') {
        manualSecs += s.durationSeconds;
        manualCount += 1;
      }
    });

    return {
      totalFormatted: formatDurationSecs(totalSecs),
      scheduledCount,
      scheduledFormatted: formatDurationSecs(scheduledSecs),
      manualCount,
      manualFormatted: formatDurationSecs(manualSecs),
    };
  }, [runSessions]);

  // Filtered Sessions
  const filteredSessions = React.useMemo(() => {
    return runSessions.filter((s) => {
      if (historyMotorFilter !== 'ALL' && s.motorId !== historyMotorFilter) return false;
      if (historyTypeFilter !== 'ALL' && s.triggerType !== historyTypeFilter) return false;
      return true;
    });
  }, [runSessions, historyMotorFilter, historyTypeFilter]);

  // Filtered Raw Events
  const filteredEvents = React.useMemo(() => {
    return recentEvents.filter((ev) => {
      if (historyMotorFilter !== 'ALL' && ev.motor_id !== historyMotorFilter) return false;
      return true;
    });
  }, [recentEvents, historyMotorFilter]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Subscribe to active station channel for instantaneous real-time history & command updates
  useEffect(() => {
    if (station?.id) {
      ws.subscribeChannels([`station:${station.id}`]);
    }
  }, [station?.id]);

  // Periodic background real-time sync (every 3 seconds) ensuring History is always live without page refresh
  useEffect(() => {
    const interval = setInterval(() => {
      debouncedSync(0);
    }, 3000);
    return () => clearInterval(interval);
  }, [debouncedSync]);

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

      // When scheduled session reaches final time (0), immediately close motor and switch power button back to START
      if (diff <= 0) {
        setActiveTimer(null);
        setRemainingSeconds(0);
        setMotor((prev) => (prev ? { ...prev, status: 'OFF' } : null));
        setMotorsList((prev) =>
          prev.map((m) => (m.id === motor?.id ? { ...m, status: 'OFF' } : m))
        );
        debouncedSync(100);
      }
    };
    updateTick();
    const interval = setInterval(updateTick, 1000);
    return () => clearInterval(interval);
  }, [activeTimer, motor?.status, motor?.id, debouncedSync]);

  // Live WebSocket updates
  useEffect(() => {
    if (!latestWsEvent) return;

    if (latestWsEvent.event === 'NOTIFICATION_RECEIVED') {
      const isWarning = latestWsEvent.event_type?.includes('WARNING') || latestWsEvent.severity === 'WARNING';
      audioAlert.playBuzzer(latestWsEvent.notification_id, isWarning ? 'WARNING' : latestWsEvent.severity);
      setToastMessage(`${latestWsEvent.title}: ${latestWsEvent.message}`);
      setTimeout(() => setToastMessage(null), 4000);

      setRecentEvents((prev) => [
        {
          id: latestWsEvent.notification_id,
          motor_id: latestWsEvent.motor_id || (motor?.id || ''),
          event_type: (latestWsEvent.event_type as any) || 'NOTIFICATION',
          source: 'SYSTEM',
          occurred_at: latestWsEvent.timestamp,
          created_at: latestWsEvent.timestamp,
          description: `${latestWsEvent.title}: ${latestWsEvent.message}`,
          metadata: latestWsEvent.metadata,
        },
        ...prev.slice(0, 10),
      ]);

      const targetId = latestWsEvent.motor_id || (latestWsEvent.metadata?.motor_id as string);
      if (latestWsEvent.event_type === 'SCHEDULE_STARTED') {
        setMotor((prev) => (prev && (!targetId || prev.id === targetId) ? { ...prev, status: 'ON' } : prev));
        setMotorsList((prev) =>
          prev.map((m) => (!targetId || m.id === targetId ? { ...m, status: 'ON' } : m))
        );
        debouncedSync(200);
      } else if (
        latestWsEvent.event_type === 'SCHEDULE_STOPPED' ||
        latestWsEvent.event_type === 'TIMER_EXPIRED' ||
        latestWsEvent.event_type?.includes('STOPPED') ||
        latestWsEvent.event_type?.includes('EXPIRED')
      ) {
        setMotor((prev) => (prev && (!targetId || prev.id === targetId) ? { ...prev, status: 'OFF' } : prev));
        setMotorsList((prev) =>
          prev.map((m) => (!targetId || m.id === targetId ? { ...m, status: 'OFF' } : m))
        );
        setActiveTimer(null);
        setRemainingSeconds(0);
        debouncedSync(100);
      } else if (
        latestWsEvent.event_type?.includes('SCHEDULE') ||
        latestWsEvent.event_type?.includes('TIMER')
      ) {
        debouncedSync(200);
      }
    } else if (latestWsEvent.event === 'SAFETY_ALERT') {
      audioAlert.playBuzzer(latestWsEvent.timestamp, 'CRITICAL');
      setToastMessage(`Safety Alert: ${latestWsEvent.description || latestWsEvent.event_type}`);
      setTimeout(() => setToastMessage(null), 4000);
      debouncedSync(200);
    } else if (latestWsEvent.event === 'TELEMETRY') {
      const code = (latestWsEvent.sensor_code || '').toLowerCase();
      const val = latestWsEvent.value;

      if (code.includes('level') || code.includes('tank')) {
        setTankLevel(val);
        setWaterHeadMeters(+(val * 0.32).toFixed(1));
      } else if (code.includes('sump') || code.includes('source')) {
        setSumpLevel(val);
      } else if (code.includes('flow')) {
        setFlowRateLpm(val);
      } else if (code.includes('turbidity')) {
        setTurbidity(val);
      } else if (code.includes('current')) {
        setCurrentAmps(val);
        setPowerKw(+((val * voltage * 0.85) / 1000).toFixed(2));
      } else if (code.includes('voltage')) {
        setVoltage(val);
      }
    } else if (latestWsEvent.event === 'MOTOR_STATE') {
      const targetId = latestWsEvent.motor_id;
      const newStatus = latestWsEvent.status;
      if (!motor || targetId === motor.id) {
        setMotor((prev) => (prev ? { ...prev, status: newStatus } : null));
        if (newStatus === 'OFF' || (newStatus as string) === 'STOPPED') {
          setActiveTimer(null);
          setRemainingSeconds(0);
        }
      }
      setMotorsList((prev) =>
        prev.map((m) => (m.id === targetId ? { ...m, status: newStatus } : m))
      );
      if (newStatus === 'OFF' || (newStatus as string) === 'STOPPED') {
        setActiveTimer(null);
        setRemainingSeconds(0);
      }
      debouncedSync(100);
    } else if (latestWsEvent.event === 'COMMAND_LIFECYCLE') {
      if (
        latestWsEvent.status === 'EXECUTED' ||
        latestWsEvent.status === 'FAILED' ||
        latestWsEvent.status === 'ACKNOWLEDGED'
      ) {
        debouncedSync(200);
      }
    }
  }, [latestWsEvent, motor, voltage, debouncedSync]);

  // Start / Stop Power Action with Scheduled Closing Duration Support
  const handlePowerToggle = async () => {
    if (!motor || !isOperator) return;

    if (isMotorRunning) {
      // Direct instant stop
      setIsProcessing(true);
      const prevStatus = motor.status;
      setMotor({ ...motor, status: 'OFF' });
      setMotorsList((prev) => prev.map((m) => (m.id === motor.id ? { ...m, status: 'OFF' } : m)));
      setActiveTimer(null);
      setRemainingSeconds(0);

      try {
        await api.stopMotor(motor.id);
        setToastMessage(`Pump (${motor.motor_code}) Stopped`);
        setTimeout(() => setToastMessage(null), 2500);
        debouncedSync(100);
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
      setTimeout(() => setToastMessage(null), 3500);
      debouncedSync(100);
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
      setTimeout(() => setToastMessage(null), 3500);
    } catch (err: any) {
      setToastMessage(err.message || 'Failed to extend schedule timer');
      setTimeout(() => setToastMessage(null), 3500);
    } finally {
      setIsExtending(false);
    }
  };

  const activeSchedulesCount = schedules.filter((s) => s.is_active).length;

  return (
    <div className="w-full max-w-lg mx-auto px-3.5 pt-2 pb-24 space-y-3 font-['Plus_Jakarta_Sans',sans-serif] selection:bg-cyan-500 selection:text-white">
      {/* Toast Alert */}
      {toastMessage && (
        <div className="fixed top-14 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-2xl bg-slate-900/95 border border-slate-700 text-white text-xs font-bold flex items-center gap-2 shadow-2xl backdrop-blur-md animate-bounce">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 1: HOME */}
      {/* ========================================================================= */}
      {activeTab === 'HOME' && (
        <>
          {/* Station Status Header Card */}
          <div className="mobile-card p-3.5 flex items-center justify-between gap-2.5">
            <div className="flex items-center gap-2.5 min-w-0 flex-1">
              <span className="relative flex h-2.5 w-2.5 flex-shrink-0">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-teal-600"></span>
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
              <span className="inline-flex items-center gap-1 px-2 py-1 rounded-xl bg-amber-50 border border-amber-200/80 text-[10px] font-bold text-amber-700 whitespace-nowrap">
                <AlertTriangle className="w-3 h-3 text-amber-500 flex-shrink-0" />
                <span>1m ago</span>
              </span>
              <button
                onClick={() => loadData(true)}
                title="Refresh Station Data"
                className="p-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors flex-shrink-0"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin text-teal-600' : ''}`} />
              </button>
            </div>
          </div>

          {/* ========================================================================= */}
          {/* MOTOR UNIT SELECTOR (Below Demo Station, Above Interlocks) */}
          {/* ========================================================================= */}
          {motorsList.length > 0 && (
            <div className="mobile-card p-3 space-y-2.5">
              <div className="flex items-center justify-between gap-1 text-[11px] font-black tracking-tight text-slate-700 uppercase">
                <div className="flex items-center gap-1.5 min-w-0">
                  <Sliders className="w-3.5 h-3.5 text-teal-600 flex-shrink-0" />
                  <span className="truncate">SELECT ACTIVE MOTOR</span>
                </div>
                <span className="px-2 py-0.5 rounded-lg bg-teal-50 border border-teal-200/80 text-[10px] font-bold text-teal-700">
                  {motorsList.length} Unit{motorsList.length !== 1 ? 's' : ''} Online
                </span>
              </div>

              {/* Motor Units Selector Grid */}
              <div className={`grid ${motorsList.length > 1 ? 'grid-cols-2' : 'grid-cols-1'} gap-2`}>
                {motorsList.map((m) => {
                  const isSelected = motor?.id === m.id;
                  const isRunning = m.status === 'ON' || m.status === 'STARTING';
                  return (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() => handleSelectMotor(m)}
                      className={`p-2.5 rounded-2xl border text-left flex flex-col justify-between transition-all duration-200 relative overflow-hidden cursor-pointer ${
                        isSelected
                          ? 'bg-gradient-to-br from-teal-500/10 via-teal-50/50 to-white border-teal-500/80 shadow-md shadow-teal-500/10 ring-2 ring-teal-500/20'
                          : 'bg-slate-50/80 hover:bg-slate-100/90 border-slate-200/80 text-slate-600 hover:border-slate-300'
                      }`}
                    >
                      {/* Active Indicator Top Accent */}
                      {isSelected && (
                        <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-teal-500 to-cyan-500" />
                      )}

                      <div className="flex items-start justify-between gap-1.5">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5">
                            <span
                              className={`w-2 h-2 rounded-full flex-shrink-0 ${
                                isRunning
                                  ? 'bg-emerald-500 animate-pulse shadow-xs'
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

                        <div className="flex items-center gap-1 flex-shrink-0">
                          <span
                            className={`px-1.5 py-0.5 rounded-md text-[9px] font-black uppercase tracking-wider ${
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
                      </div>

                      <div className="flex items-center justify-between pt-1.5 mt-1 border-t border-slate-100/80 text-[10px]">
                        <span className={`font-bold ${isSelected ? 'text-teal-700' : 'text-slate-400'}`}>
                          {isSelected ? '✓ ACTIVE CONTROL' : 'Tap to Select'}
                        </span>
                        <span className="text-[9px] text-slate-400 uppercase font-medium">
                          {m.motor_type?.replace('_', ' ') || 'PUMP'}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* SAFETY INTERLOCKS CARD (Directly below Motor Selector Section) */}
          {/* ========================================================================= */}
          <div className="mobile-card p-3.5 space-y-2.5">
            <div className="flex items-center justify-between gap-1 text-[12px] font-black tracking-tight text-emerald-600 uppercase">
              <div className="flex items-center gap-1.5 min-w-0">
                <Activity className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                <span className="truncate">INTERLOCKS</span>
              </div>
              <span className="text-[12px] font-bold text-emerald-600 flex-shrink-0">100% OK</span>
            </div>

            {/* 4 Green Bullet Checks (2x2 Grid) */}
            <div className="grid grid-cols-2 gap-2 text-[12px] font-bold text-slate-800">
              <div className="flex items-center gap-2 bg-slate-50/90 hover:bg-slate-100/80 px-3 py-2 rounded-xl border border-slate-100 transition-colors">
                <span className="w-2 h-2 rounded-full bg-emerald-500 flex-shrink-0 shadow-xs" />
                <span className="truncate">Overflow</span>
              </div>
              <div className="flex items-center gap-2 bg-slate-50/90 hover:bg-slate-100/80 px-3 py-2 rounded-xl border border-slate-100 transition-colors">
                <span className="w-2 h-2 rounded-full bg-emerald-500 flex-shrink-0 shadow-xs" />
                <span className="truncate">Dry-Run</span>
              </div>
              <div className="flex items-center gap-2 bg-slate-50/90 hover:bg-slate-100/80 px-3 py-2 rounded-xl border border-slate-100 transition-colors">
                <span className="w-2 h-2 rounded-full bg-emerald-500 flex-shrink-0 shadow-xs" />
                <span className="truncate">Turbidity</span>
              </div>
              <div className="flex items-center gap-2 bg-slate-50/90 hover:bg-slate-100/80 px-3 py-2 rounded-xl border border-slate-100 transition-colors">
                <span className="w-2 h-2 rounded-full bg-emerald-500 flex-shrink-0 shadow-xs" />
                <span className="truncate">E-Stop</span>
              </div>
            </div>

            <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] font-medium text-slate-500">
              <span>Authority:</span>
              <span className="text-teal-700 font-bold">Local ESP32</span>
            </div>
          </div>

          {/* ========================================================================= */}
          {/* SCHEDULED OPERATION LIVE COUNTDOWN & 1-MINUTE WARNING BANNER */}
          {/* ========================================================================= */}
          {isMotorRunning && activeTimer && activeTimer.is_running && remainingSeconds > 0 && (
            remainingSeconds <= 60 || activeTimer.is_warning_active ? (
              /* PROMINENT 1-MINUTE PRE-EXPIRATION WARNING CARD */
              <div className="p-4 rounded-3xl bg-gradient-to-r from-amber-500/15 via-rose-500/15 to-amber-500/15 border-2 border-amber-400/80 shadow-xl shadow-amber-500/10 space-y-3 backdrop-blur-md animate-pulse-flow">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="p-1.5 rounded-xl bg-amber-500 text-white animate-bounce">
                      <AlertTriangle className="w-4 h-4 stroke-[2.5]" />
                    </span>
                    <div>
                      <h3 className="text-xs font-black text-amber-900 uppercase tracking-wide">
                        ⚠️ Motor Will Stop in {remainingSeconds}s
                      </h3>
                      <p className="text-[11px] text-amber-800 font-medium">
                        {activeTimer.schedule_name || 'Scheduled Operation'} is about to finish.
                      </p>
                    </div>
                  </div>
                  <div className="px-3 py-1 rounded-xl bg-amber-500 text-white font-mono font-black text-sm shadow-md">
                    00:{String(remainingSeconds).padStart(2, '0')}
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => handleContinueTimer(900)}
                    disabled={isExtending || !isOperator}
                    className="flex-1 py-2.5 px-3 rounded-2xl bg-amber-600 hover:bg-amber-700 text-white text-xs font-black flex items-center justify-center gap-1.5 shadow-lg shadow-amber-600/25 transition-all active:scale-95 disabled:opacity-50"
                  >
                    <FastForward className="w-3.5 h-3.5 stroke-[3]" />
                    <span>{isExtending ? 'EXTENDING...' : 'CONTINUE (+15 MIN)'}</span>
                  </button>

                  <button
                    type="button"
                    onClick={handlePowerToggle}
                    disabled={isProcessing || !isOperator}
                    className="py-2.5 px-4 rounded-2xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-black flex items-center justify-center gap-1.5 shadow-lg shadow-rose-600/25 transition-all active:scale-95 disabled:opacity-50"
                  >
                    <Square className="w-3.5 h-3.5 fill-current" />
                    <span>STOP NOW</span>
                  </button>
                </div>
              </div>
            ) : (
              /* ACTIVE SCHEDULE COUNTDOWN CARD */
              <div className="mobile-card p-3.5 bg-gradient-to-r from-teal-500/10 via-cyan-500/10 to-teal-500/10 border-teal-300/80 shadow-lg shadow-teal-500/5 space-y-2.5">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="p-1.5 rounded-xl bg-teal-600 text-white shadow-sm">
                      <Timer className="w-4 h-4 animate-spin" />
                    </span>
                    <div className="min-w-0">
                      <div className="text-xs font-black text-teal-950 uppercase tracking-tight truncate">
                        Scheduled Operation Active
                      </div>
                      <div className="text-[10px] text-teal-700 font-semibold truncate">
                        {activeTimer.schedule_name || 'Timer Cycle'} &bull; Auto-stop at {new Date(activeTimer.end_time || '').toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 flex-shrink-0">
                    <div className="px-2.5 py-1 rounded-xl bg-teal-600 text-white font-mono font-black text-xs shadow-sm">
                      {Math.floor(remainingSeconds / 60)}:{String(remainingSeconds % 60).padStart(2, '0')}
                    </div>
                    {isOperator && (
                      <button
                        type="button"
                        onClick={() => handleContinueTimer(900)}
                        disabled={isExtending}
                        title="Add 15 Minutes to active run"
                        className="py-1 px-2 rounded-xl bg-teal-100 hover:bg-teal-200 text-teal-800 text-[10px] font-black flex items-center gap-1 border border-teal-300 transition-colors disabled:opacity-50"
                      >
                        <Plus className="w-2.5 h-2.5 stroke-[3]" />
                        <span>15m</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Progress bar */}
                <div className="w-full h-1.5 bg-teal-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-teal-500 to-cyan-500 rounded-full transition-all duration-1000"
                    style={{
                      width: `${Math.max(
                        0,
                        Math.min(
                          100,
                          ((activeTimer.duration_seconds - remainingSeconds) /
                            Math.max(1, activeTimer.duration_seconds)) *
                            100
                        )
                      )}%`,
                    }}
                  />
                </div>
              </div>
            )
          )}

          {/* 2-COLUMN METRIC CARDS GRID */}
          <div className="grid grid-cols-2 gap-2.5">
            {/* CARD 1: OVERHEAD TANK & HEAD */}
            <div className="mobile-card p-3 space-y-2 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between gap-1 text-[11px] font-black tracking-tight text-teal-700 uppercase">
                  <div className="flex items-center gap-1 min-w-0">
                    <Waves className="w-3.5 h-3.5 flex-shrink-0 text-teal-600" />
                    <span className="truncate">TANK LEVEL</span>
                  </div>
                  <span className="text-[10px] font-semibold text-slate-400 flex-shrink-0">1000L</span>
                </div>

                <div className="flex items-baseline justify-between mt-1">
                  <span className="text-2xl font-black text-slate-900 tracking-tight">
                    {tankLevel.toFixed(1)}%
                  </span>
                  <span className="px-1.5 py-0.5 rounded-md bg-teal-600 text-white text-[10px] font-bold">
                    {tankLevel.toFixed(0)}%
                  </span>
                </div>

                {/* Hydro-Teal Gradient Progress Bar */}
                <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden mt-1.5">
                  <div
                    className="h-full bg-gradient-to-r from-teal-500 to-cyan-500 rounded-full transition-all duration-500"
                    style={{ width: `${Math.min(100, tankLevel)}%` }}
                  />
                </div>

                <div className="text-[11px] text-slate-600 font-semibold mt-1">
                  Head: <span className="font-bold text-slate-900">{waterHeadMeters.toFixed(1)} m</span>
                </div>
              </div>

              <div className="pt-1.5 border-t border-slate-100 flex items-center justify-between text-[10px] font-medium text-slate-500">
                <span className="truncate">Cutoff: &ge;95%</span>
                <span className="text-emerald-600 font-bold flex-shrink-0">Adequate</span>
              </div>
            </div>

            {/* CARD 2: SUMP / SOURCE LEVEL */}
            <div className="mobile-card p-3 space-y-2 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between gap-1 text-[11px] font-black tracking-tight text-cyan-700 uppercase">
                  <div className="flex items-center gap-1 min-w-0">
                    <Droplet className="w-3.5 h-3.5 flex-shrink-0 text-cyan-600" />
                    <span className="truncate">SUMP LEVEL</span>
                  </div>
                  <span className="text-[10px] font-semibold text-slate-400 flex-shrink-0">5000L</span>
                </div>

                <div className="flex items-baseline justify-between mt-1">
                  <span className="text-2xl font-black text-slate-900 tracking-tight">
                    {sumpLevel.toFixed(1)}%
                  </span>
                  <span className="text-[10px] font-semibold text-slate-500">
                    ~{(sumpLevel * 50).toFixed(0)} L
                  </span>
                </div>

                {/* Cyan to Aqua Gradient Progress Bar */}
                <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden mt-1.5">
                  <div
                    className="h-full bg-gradient-to-r from-cyan-500 to-teal-400 rounded-full transition-all duration-500"
                    style={{ width: `${Math.min(100, sumpLevel)}%` }}
                  />
                </div>
              </div>

              <div className="pt-1.5 border-t border-slate-100 flex items-center justify-between text-[10px] font-medium text-slate-500">
                <span className="truncate">Dry-Run: &le;10%</span>
                <span className="text-emerald-600 font-bold flex-shrink-0">Source Safe</span>
              </div>
            </div>

            {/* CARD 3: WATER FLOW RATE */}
            <div className="mobile-card p-3 space-y-2 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between gap-1 text-[11px] font-black tracking-tight text-teal-700 uppercase">
                  <div className="flex items-center gap-1 min-w-0">
                    <Gauge className="w-3.5 h-3.5 flex-shrink-0 text-teal-600" />
                    <span className="truncate">FLOW RATE</span>
                  </div>
                  <span className="text-[10px] font-semibold text-slate-400 flex-shrink-0">Sensor</span>
                </div>

                <div className="flex items-baseline justify-between mt-1">
                  <span className="text-2xl font-black text-slate-900 tracking-tight">
                    {flowRateLpm.toFixed(1)} <span className="text-xs font-bold text-slate-400">L/m</span>
                  </span>
                  <span
                    className={`px-1.5 py-0.5 rounded-md text-[10px] font-bold ${
                      isMotorRunning
                        ? 'bg-emerald-100 text-emerald-700'
                        : 'bg-slate-100 text-slate-600'
                    }`}
                  >
                    {isMotorRunning ? 'Discharging' : 'Idle'}
                  </span>
                </div>

                <div className="text-[11px] text-slate-600 font-semibold mt-1">
                  Discharge: <span className="font-bold text-slate-900">{(flowRateLpm * 0.06).toFixed(2)} m&sup3;/h</span>
                </div>
              </div>

              <div className="pt-1.5 border-t border-slate-100 flex items-center justify-between text-[10px] font-medium text-slate-500">
                <span>Protection:</span>
                <span className="text-emerald-600 font-bold">Primed &bull; Active</span>
              </div>
            </div>

            {/* CARD 4: WATER QUALITY */}
            <div className="mobile-card p-3 space-y-2 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between gap-1 text-[11px] font-black tracking-tight text-amber-500 uppercase">
                  <div className="flex items-center gap-1 min-w-0">
                    <Shield className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />
                    <span className="truncate">WATER QUALITY</span>
                  </div>
                  <span className="px-1.5 py-0.5 rounded-md bg-emerald-50 text-emerald-600 border border-emerald-200 text-[10px] font-bold flex-shrink-0">
                    Clean
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-1.5 mt-1.5">
                  <div>
                    <div className="text-[10px] text-slate-400 font-medium">Turbidity</div>
                    <div className="text-base font-black text-slate-900">
                      {turbidity.toFixed(1)} <span className="text-[10px] text-slate-400 font-normal">NTU</span>
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] text-slate-400 font-medium">pH Level</div>
                    <div className="text-base font-black text-slate-900">
                      {ph.toFixed(1)} <span className="text-[10px] text-slate-400 font-normal">pH</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="pt-1.5 border-t border-slate-100 flex items-center justify-between text-[10px] font-medium text-slate-500">
                <span>Cutoff:</span>
                <span className="text-slate-700 font-semibold">&gt;25 NTU Auto-Trip</span>
              </div>
            </div>

            {/* CARD 5: ELECTRICAL LOAD (Full Width across 2 columns) */}
            <div className="mobile-card p-3 space-y-2 col-span-2 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between gap-1 text-[11px] font-black tracking-tight text-purple-600 uppercase">
                  <div className="flex items-center gap-1 min-w-0">
                    <Zap className="w-3.5 h-3.5 text-purple-600 flex-shrink-0" />
                    <span className="truncate">ELECTRICAL LOAD</span>
                  </div>
                  <span className="text-[10px] font-semibold text-slate-400 flex-shrink-0">230V Grid</span>
                </div>

                <div className="grid grid-cols-2 gap-2 mt-1.5">
                  <div className="bg-slate-50/90 p-2 rounded-xl border border-slate-100">
                    <div className="text-[10px] text-slate-400 font-medium">Current</div>
                    <div className="text-base font-black text-slate-900">
                      {currentAmps.toFixed(1)} <span className="text-xs font-semibold text-slate-400">A</span>
                    </div>
                  </div>
                  <div className="bg-slate-50/90 p-2 rounded-xl border border-slate-100">
                    <div className="text-[10px] text-slate-400 font-medium">Power</div>
                    <div className="text-base font-black text-slate-900">
                      {powerKw.toFixed(1)} <span className="text-xs font-semibold text-slate-400">kW</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="pt-1.5 border-t border-slate-100 flex items-center justify-between text-[10px] font-medium text-slate-500">
                <span>Overload:</span>
                <span className="text-emerald-600 font-bold">Safe &lt; 15A</span>
              </div>
            </div>
          </div>

          {/* BOTTOM ROW QUICK CARDS (Above Dock) */}
          <div className="grid grid-cols-2 gap-2.5 pt-0.5">
            {/* Quick Card 1: Daily Pump Schedules */}
            <div className="mobile-card p-3 flex flex-col justify-between space-y-2">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-teal-50 text-teal-700 flex items-center justify-center flex-shrink-0">
                  <Clock className="w-4 h-4" />
                </div>
                <div className="min-w-0">
                  <div className="text-xs font-bold text-slate-900 leading-tight truncate">
                    Pump Schedules
                  </div>
                  <div className="text-[10px] text-slate-400 font-medium truncate">
                    {activeSchedulesCount} active timer{activeSchedulesCount !== 1 ? 's' : ''}
                  </div>
                </div>
              </div>

              <button
                onClick={() => setIsScheduleModalOpen(true)}
                className="w-full py-1.5 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-[11px] font-bold flex items-center justify-center gap-1 shadow-md shadow-teal-600/20 transition-all"
              >
                <Plus className="w-3 h-3 stroke-[3]" />
                <span>Configure</span>
              </button>
            </div>

            {/* Quick Card 2: Latest Event */}
            <div className="mobile-card p-3 flex flex-col justify-between space-y-2">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center flex-shrink-0">
                  <Zap className="w-4 h-4" />
                </div>
                <div className="min-w-0">
                  <div className="text-xs font-bold text-slate-900 leading-tight truncate">
                    Latest Event
                  </div>
                  <div className="text-[10px] text-slate-400 font-medium truncate">
                    Ready &amp; Standby
                  </div>
                </div>
              </div>

              <div className="w-full text-center">
                <span
                  className={`inline-block w-full py-1 rounded-xl text-[10px] font-black uppercase tracking-wider ${
                    isMotorRunning
                      ? 'bg-emerald-100 text-emerald-700'
                      : 'bg-slate-100 text-slate-600'
                  }`}
                >
                  {isMotorRunning ? 'PUMP ON' : 'PUMP IDLE'}
                </span>
              </div>
            </div>
          </div>
        </>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: SCHEDULES (MATCHES SCREENSHOT 2 EXACTLY) */}
      {/* ========================================================================= */}
      {activeTab === 'SCHEDULES' && (
        <div className="space-y-3">
          {/* Header Title Bar */}
          <div className="flex items-center gap-3 pt-1">
            <div className="w-10 h-10 rounded-2xl bg-teal-50 text-teal-700 flex items-center justify-center shadow-xs">
              <Calendar className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-black text-slate-900 tracking-tight">SCHEDULES</h2>
                <span className="px-2 py-0.5 rounded-full bg-teal-100 text-teal-800 text-[10px] font-extrabold">
                  {activeSchedulesCount} Active
                </span>
              </div>
              <p className="text-xs text-slate-400 font-medium">Automated Daily Timer</p>
            </div>
          </div>

          {/* Daily Pump Schedules Card */}
          <div className="mobile-card p-4 flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-10 h-10 rounded-2xl bg-teal-50 text-teal-700 flex items-center justify-center flex-shrink-0">
                <Clock className="w-5 h-5" />
              </div>
              <div className="min-w-0">
                <h3 className="text-sm font-bold text-slate-900 truncate">Daily Pump Schedules</h3>
                <p className="text-xs text-slate-400 font-medium truncate">
                  {activeSchedulesCount} automated timer{activeSchedulesCount !== 1 ? 's' : ''} active
                </p>
              </div>
            </div>

            <button
              onClick={() => setIsScheduleModalOpen(true)}
              className="px-3.5 py-2 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold flex items-center gap-1.5 shadow-md shadow-teal-600/25 transition-all flex-shrink-0"
            >
              <Plus className="w-3.5 h-3.5 stroke-[3]" />
              <span>Configure</span>
            </button>
          </div>

          {/* Active Schedules List */}
          <div className="space-y-2">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 px-1">
              Configured Time Slots
            </h4>
            {schedules.length === 0 ? (
              <div className="mobile-card p-6 text-center text-xs text-slate-400 space-y-2">
                <Clock className="w-8 h-8 text-slate-300 mx-auto" />
                <p>No automated timer schedules created yet.</p>
                <button
                  onClick={() => setIsScheduleModalOpen(true)}
                  className="px-3 py-1.5 rounded-xl bg-teal-50 text-teal-700 font-bold text-xs hover:bg-teal-100"
                >
                  + Add First Schedule
                </button>
              </div>
            ) : (
              schedules.map((s) => {
                const targetMotor =
                  motorsList.find((m) => m.id === s.motor_id) ||
                  (motor && motor.id === s.motor_id ? motor : null);
                return (
                  <div
                    key={s.id}
                    className="mobile-card p-3.5 flex items-center justify-between"
                  >
                    <div className="flex items-center gap-2.5">
                      <span
                        className={`w-2 h-2 rounded-full ${
                          s.is_active ? 'bg-emerald-500' : 'bg-slate-300'
                        }`}
                      />
                      <div>
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="text-xs font-bold text-slate-900">{s.name}</span>
                          {targetMotor && (
                            <span className="px-1.5 py-0.5 rounded bg-teal-50 text-teal-800 text-[10px] font-bold border border-teal-200/60 font-mono flex items-center gap-0.5">
                              <Zap className="w-2.5 h-2.5 text-teal-600" />
                              {targetMotor.motor_code}
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-slate-400">
                          {s.start_time} &bull; {Math.round(s.duration_seconds / 60)} mins &bull; [
                          {s.days_of_week.join(', ')}]
                        </div>
                      </div>
                    </div>
                    <span
                      className={`px-2 py-0.5 rounded-lg text-[10px] font-bold ${
                        s.is_active
                          ? 'bg-emerald-50 text-emerald-700'
                          : 'bg-slate-100 text-slate-500'
                      }`}
                    >
                      {s.is_active ? 'Active' : 'Disabled'}
                    </span>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 3: HISTORY (RUN SESSIONS, DURATIONS & EVENT LOGS) */}
      {/* ========================================================================= */}
      {activeTab === 'HISTORY' && (
        <div className="space-y-3.5">
          {/* Header */}
          <div className="flex items-center justify-between pt-1">
            <div>
              <h2 className="text-lg font-black text-slate-900 tracking-tight leading-tight">
                PUMP RUN HISTORY
              </h2>
              <p className="text-[11px] text-slate-400 font-medium">
                Cycle durations, start / off times &amp; trigger analytics
              </p>
            </div>
            <button
              onClick={() => loadData(true)}
              disabled={isSyncing}
              className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors shadow-xs"
              title="Refresh History"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin text-teal-600' : ''}`} />
            </button>
          </div>

          {/* Aggregate Metrics Grid (Total Runtime, Scheduled Runs, Manual Starts) */}
          <div className="grid grid-cols-3 gap-2">
            {/* Total Runtime */}
            <div className="mobile-card p-3 space-y-1">
              <div className="flex items-center gap-1.5 text-indigo-600">
                <Timer className="w-3.5 h-3.5 shrink-0" />
                <span className="text-[10px] font-black uppercase tracking-wider text-slate-400 truncate">
                  Total Runtime
                </span>
              </div>
              <div className="text-sm font-black text-slate-900 truncate">
                {historyMetrics.totalFormatted}
              </div>
              <div className="text-[9px] text-slate-400 font-medium truncate">
                {runSessions.length} total cycle{runSessions.length !== 1 ? 's' : ''}
              </div>
            </div>

            {/* Scheduled Cycles */}
            <div className="mobile-card p-3 space-y-1">
              <div className="flex items-center gap-1.5 text-teal-600">
                <Calendar className="w-3.5 h-3.5 shrink-0" />
                <span className="text-[10px] font-black uppercase tracking-wider text-slate-400 truncate">
                  Scheduled
                </span>
              </div>
              <div className="text-sm font-black text-teal-800 truncate">
                {historyMetrics.scheduledCount} <span className="text-xs font-semibold text-slate-500">runs</span>
              </div>
              <div className="text-[9px] text-teal-700 font-medium truncate">
                {historyMetrics.scheduledFormatted}
              </div>
            </div>

            {/* Manual Starts */}
            <div className="mobile-card p-3 space-y-1">
              <div className="flex items-center gap-1.5 text-blue-600">
                <Zap className="w-3.5 h-3.5 shrink-0" />
                <span className="text-[10px] font-black uppercase tracking-wider text-slate-400 truncate">
                  Manual Starts
                </span>
              </div>
              <div className="text-sm font-black text-blue-800 truncate">
                {historyMetrics.manualCount} <span className="text-xs font-semibold text-slate-500">runs</span>
              </div>
              <div className="text-[9px] text-blue-700 font-medium truncate">
                {historyMetrics.manualFormatted}
              </div>
            </div>
          </div>

          {/* Motor Filter Selector */}
          {motorsList.length > 1 && (
            <div className="space-y-1.5">
              <div className="text-[10px] font-black uppercase tracking-wider text-slate-400 px-1">
                Filter by Motor Unit
              </div>
              <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
                <button
                  type="button"
                  onClick={() => setHistoryMotorFilter('ALL')}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all shrink-0 ${
                    historyMotorFilter === 'ALL'
                      ? 'bg-slate-900 text-white shadow-xs'
                      : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
                  }`}
                >
                  All Motors ({motorsList.length})
                </button>
                {motorsList.map((m) => {
                  const isSelected = historyMotorFilter === m.id;
                  return (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() => setHistoryMotorFilter(m.id)}
                      className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all shrink-0 flex items-center gap-1.5 font-mono ${
                        isSelected
                          ? 'bg-teal-600 text-white shadow-xs'
                          : 'bg-white text-slate-700 border border-slate-200 hover:bg-teal-50/50 hover:border-teal-200'
                      }`}
                    >
                      <Zap className={`w-3 h-3 ${isSelected ? 'text-teal-200' : 'text-teal-600'}`} />
                      <span>{m.motor_code}</span>
                      <span className={`text-[10px] font-normal ${isSelected ? 'text-teal-100' : 'text-slate-400'}`}>
                        ({m.name})
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Trigger Filter & View Mode Toggle */}
          <div className="flex items-center justify-between gap-2 flex-wrap pt-0.5">
            {/* Trigger Filter Chips */}
            <div className="flex items-center gap-1 overflow-x-auto scrollbar-none">
              <button
                type="button"
                onClick={() => setHistoryTypeFilter('ALL')}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all shrink-0 ${
                  historyTypeFilter === 'ALL'
                    ? 'bg-slate-800 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                All
              </button>
              <button
                type="button"
                onClick={() => setHistoryTypeFilter('SCHEDULED')}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all shrink-0 flex items-center gap-1 ${
                  historyTypeFilter === 'SCHEDULED'
                    ? 'bg-teal-600 text-white'
                    : 'bg-teal-50 text-teal-800 hover:bg-teal-100'
                }`}
              >
                <Calendar className="w-2.5 h-2.5" />
                <span>Scheduled</span>
              </button>
              <button
                type="button"
                onClick={() => setHistoryTypeFilter('MANUAL')}
                className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all shrink-0 flex items-center gap-1 ${
                  historyTypeFilter === 'MANUAL'
                    ? 'bg-blue-600 text-white'
                    : 'bg-blue-50 text-blue-800 hover:bg-blue-100'
                }`}
              >
                <Zap className="w-2.5 h-2.5" />
                <span>Manual</span>
              </button>
            </div>

            {/* View Mode Toggle */}
            <div className="flex items-center bg-slate-100 p-0.5 rounded-xl border border-slate-200/80 shrink-0">
              <button
                type="button"
                onClick={() => setHistoryViewMode('SESSIONS')}
                className={`px-2.5 py-1 rounded-lg text-[10px] font-extrabold transition-all flex items-center gap-1 ${
                  historyViewMode === 'SESSIONS'
                    ? 'bg-white text-slate-900 shadow-xs'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                <Timer className="w-3 h-3 text-teal-600" />
                <span>Run Cycles</span>
              </button>
              <button
                type="button"
                onClick={() => setHistoryViewMode('TIMELINE')}
                className={`px-2.5 py-1 rounded-lg text-[10px] font-extrabold transition-all flex items-center gap-1 ${
                  historyViewMode === 'TIMELINE'
                    ? 'bg-white text-slate-900 shadow-xs'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                <History className="w-3 h-3 text-slate-600" />
                <span>Raw Log</span>
              </button>
            </div>
          </div>

          {/* SESSIONS VIEW */}
          {historyViewMode === 'SESSIONS' && (
            <div className="space-y-2.5">
              {filteredSessions.length === 0 ? (
                <div className="mobile-card p-8 text-center text-xs text-slate-400 space-y-2">
                  <Timer className="w-8 h-8 text-slate-300 mx-auto" />
                  <p className="font-bold text-slate-700">No pump run cycles matching filter</p>
                  <p className="text-[11px] text-slate-400 max-w-xs mx-auto">
                    Motor start and stop events with calculated durations will appear here automatically.
                  </p>
                </div>
              ) : (
                filteredSessions.map((session) => {
                  const isSched = session.triggerType === 'SCHEDULED';
                  const isManual = session.triggerType === 'MANUAL';
                  const isRunning = session.isRunning || session.status === 'RUNNING';

                  const startDateObj = parseIsoDate(session.startTime);
                  const stopDateObj = session.stopTime ? parseIsoDate(session.stopTime) : null;

                  return (
                    <div
                      key={session.id}
                      className={`mobile-card p-3.5 space-y-2.5 border transition-all ${
                        isRunning
                          ? 'border-emerald-300 bg-emerald-50/30 ring-1 ring-emerald-400/20'
                          : 'border-slate-200/80 bg-white'
                      }`}
                    >
                      {/* Top Row: Target Motor Badge, Trigger Source, and Status */}
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          {/* Motor Tag */}
                          <span className="px-2 py-0.5 rounded-lg bg-slate-900 text-white text-[10px] font-black font-mono flex items-center gap-1">
                            <Zap className="w-2.5 h-2.5 text-teal-400" />
                            {session.motorCode}
                          </span>
                          <span className="text-xs font-bold text-slate-800 truncate max-w-[130px] sm:max-w-none">
                            {session.motorName}
                          </span>
                        </div>

                        {/* Trigger Pill */}
                        <div className="flex items-center gap-1.5">
                          <span
                            className={`px-2 py-0.5 rounded-lg text-[10px] font-extrabold flex items-center gap-1 border ${
                              isSched
                                ? 'bg-teal-50 text-teal-800 border-teal-200'
                                : isManual
                                ? 'bg-blue-50 text-blue-800 border-blue-200'
                                : 'bg-rose-50 text-rose-800 border-rose-200'
                            }`}
                          >
                            {isSched ? (
                              <Calendar className="w-2.5 h-2.5 text-teal-600" />
                            ) : isManual ? (
                              <Zap className="w-2.5 h-2.5 text-blue-600" />
                            ) : (
                              <Shield className="w-2.5 h-2.5 text-rose-600" />
                            )}
                            <span>{isSched ? 'SCHEDULED' : isManual ? 'MANUAL START' : 'AUTO-SAFETY'}</span>
                          </span>

                          {/* Running / Completed Pill */}
                          {isRunning ? (
                            <span className="px-2 py-0.5 rounded-lg text-[10px] font-black bg-emerald-50 text-emerald-700 border border-emerald-300 flex items-center gap-1 animate-pulse">
                              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                              <span>RUNNING</span>
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded-lg text-[10px] font-bold bg-slate-100 text-slate-600">
                              {session.status === 'TRIPPED' ? 'TRIPPED' : 'OFF'}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Middle Row: Start Time, Off Time, and Total Duration */}
                      <div className="grid grid-cols-3 gap-2 p-2.5 rounded-xl bg-slate-50/80 border border-slate-100 text-center items-center">
                        {/* Start Time */}
                        <div className="text-left space-y-0.5">
                          <div className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400 flex items-center gap-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                            <span>Started</span>
                          </div>
                          <div className="text-xs font-bold text-slate-900 font-mono">
                            {startDateObj.toLocaleTimeString([], {
                              hour: '2-digit',
                              minute: '2-digit',
                              second: '2-digit',
                            })}
                          </div>
                        </div>

                        {/* Stop Time */}
                        <div className="text-left space-y-0.5">
                          <div className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400 flex items-center gap-1">
                            <span
                              className={`w-1.5 h-1.5 rounded-full ${
                                isRunning ? 'bg-amber-500 animate-ping' : 'bg-slate-400'
                              }`}
                            />
                            <span>Off / Stopped</span>
                          </div>
                          <div className="text-xs font-bold text-slate-900 font-mono">
                            {stopDateObj
                              ? stopDateObj.toLocaleTimeString([], {
                                  hour: '2-digit',
                                  minute: '2-digit',
                                  second: '2-digit',
                                })
                              : 'In Progress...'}
                          </div>
                        </div>

                        {/* Total Duration */}
                        <div className="text-right space-y-0.5">
                          <div className="text-[9px] font-extrabold uppercase tracking-wider text-teal-700 flex items-center justify-end gap-1">
                            <Clock className="w-2.5 h-2.5" />
                            <span>Duration</span>
                          </div>
                          <div className="text-xs font-black text-teal-900 font-mono">
                            {formatDurationSecs(session.durationSeconds)}
                          </div>
                        </div>
                      </div>

                      {/* REASON MOTOR CLOSED / STOPPED SECTION */}
                      {!isRunning ? (
                        <div
                          className={`p-2.5 rounded-xl border flex items-start gap-2.5 transition-all ${
                            session.stopReasonCategory === 'SCHEDULE_END'
                              ? 'bg-teal-50/70 border-teal-200/80 text-teal-950'
                              : session.stopReasonCategory === 'MANUAL_STOP'
                              ? 'bg-blue-50/70 border-blue-200/80 text-blue-950'
                              : session.stopReasonCategory === 'TANK_FULL'
                              ? 'bg-amber-50/80 border-amber-200/80 text-amber-950'
                              : session.stopReasonCategory === 'TURBIDITY'
                              ? 'bg-purple-50/80 border-purple-200/80 text-purple-950'
                              : session.stopReasonCategory === 'DRY_RUN' ||
                                session.stopReasonCategory === 'FAULT' ||
                                session.stopReasonCategory === 'EMERGENCY_STOP'
                              ? 'bg-rose-50/80 border-rose-200/80 text-rose-950'
                              : 'bg-slate-50 border-slate-200 text-slate-900'
                          }`}
                        >
                          <div className="mt-0.5 shrink-0">
                            {session.stopReasonCategory === 'SCHEDULE_END' ? (
                              <CheckCircle2 className="w-4 h-4 text-teal-600" />
                            ) : session.stopReasonCategory === 'MANUAL_STOP' ? (
                              <Square className="w-4 h-4 text-blue-600" />
                            ) : session.stopReasonCategory === 'TANK_FULL' ? (
                              <Droplet className="w-4 h-4 text-amber-600" />
                            ) : session.stopReasonCategory === 'TURBIDITY' ? (
                              <Waves className="w-4 h-4 text-purple-600" />
                            ) : session.stopReasonCategory === 'DRY_RUN' ? (
                              <AlertTriangle className="w-4 h-4 text-rose-600" />
                            ) : session.stopReasonCategory === 'EMERGENCY_STOP' ? (
                              <Shield className="w-4 h-4 text-rose-600" />
                            ) : (
                              <CheckCircle2 className="w-4 h-4 text-slate-600" />
                            )}
                          </div>
                          <div className="space-y-0.5 min-w-0 flex-1">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className="text-[10px] font-black uppercase tracking-wider text-slate-500">
                                Reason Motor Closed:
                              </span>
                              <span
                                className={`px-2 py-0.5 rounded-md text-[10px] font-black tracking-tight border ${
                                  session.stopReasonCategory === 'SCHEDULE_END'
                                    ? 'bg-teal-100/80 text-teal-800 border-teal-300'
                                    : session.stopReasonCategory === 'MANUAL_STOP'
                                    ? 'bg-blue-100/80 text-blue-800 border-blue-300'
                                    : session.stopReasonCategory === 'TANK_FULL'
                                    ? 'bg-amber-100 text-amber-900 border-amber-300'
                                    : session.stopReasonCategory === 'TURBIDITY'
                                    ? 'bg-purple-100 text-purple-900 border-purple-300'
                                    : session.stopReasonCategory === 'DRY_RUN' ||
                                      session.stopReasonCategory === 'FAULT' ||
                                      session.stopReasonCategory === 'EMERGENCY_STOP'
                                    ? 'bg-rose-100 text-rose-900 border-rose-300'
                                    : 'bg-slate-200 text-slate-800 border-slate-300'
                                }`}
                              >
                                {session.stopReason}
                              </span>
                            </div>
                            {session.stopReasonDetails && (
                              <p className="text-[11px] text-slate-600 font-medium leading-relaxed">
                                {session.stopReasonDetails}
                              </p>
                            )}
                          </div>
                        </div>
                      ) : (
                        <div className="p-2 rounded-xl border border-emerald-200 bg-emerald-50/60 flex items-center gap-2 text-emerald-900">
                          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-ping shrink-0" />
                          <span className="text-[11px] font-bold">
                            Motor is actively running — Live session recording in real-time
                          </span>
                        </div>
                      )}

                      {/* Bottom Row: Context & Date */}
                      <div className="flex items-center justify-between text-[10px] text-slate-400 font-medium pt-1 border-t border-slate-100">
                        <span className="truncate">
                          {session.scheduleName
                            ? `Timer Schedule: ${session.scheduleName}`
                            : session.description ||
                              (isManual ? 'Manual Operator Trigger' : 'Automated Cycle')}
                        </span>
                        <span className="shrink-0 font-mono">
                          {startDateObj.toLocaleDateString([], {
                            month: 'short',
                            day: 'numeric',
                            year: 'numeric',
                          })}
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          )}

          {/* TIMELINE / RAW LOG VIEW */}
          {historyViewMode === 'TIMELINE' && (
            <div className="space-y-2">
              {filteredEvents.length === 0 ? (
                <div className="mobile-card p-6 text-center text-xs text-slate-400">
                  No event records logged yet.
                </div>
              ) : (
                filteredEvents.map((ev) => {
                  const motorObj = motorsList.find((m) => m.id === ev.motor_id) || motor;
                  return (
                    <div
                      key={ev.id}
                      className="mobile-card p-3 flex items-center justify-between text-xs gap-2"
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <span
                          className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                            ev.event_type === 'STARTED'
                              ? 'bg-emerald-500'
                              : ev.event_type === 'STOPPED'
                              ? 'bg-blue-500'
                              : 'bg-rose-500'
                          }`}
                        />
                        <div className="min-w-0 space-y-0.5">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="font-bold text-slate-900">{ev.event_type}</span>
                            {motorObj && (
                              <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 text-[10px] font-mono font-bold">
                                {motorObj.motor_code}
                              </span>
                            )}
                            <span
                              className={`px-1.5 py-0.2 rounded text-[9px] font-extrabold ${
                                ev.source === 'AUTOMATION'
                                  ? 'bg-teal-50 text-teal-700'
                                  : ev.source === 'USER'
                                  ? 'bg-blue-50 text-blue-700'
                                  : 'bg-slate-100 text-slate-500'
                              }`}
                            >
                              {ev.source}
                            </span>
                          </div>
                          <div className="text-[10px] text-slate-500 truncate font-medium">
                            {ev.description ||
                              (ev.event_payload?.reason
                                ? `Reason: ${ev.event_payload.reason}`
                                : 'Normal operation event')}
                          </div>
                        </div>
                      </div>
                      <span className="text-[10px] font-mono text-slate-500 shrink-0">
                        {parseIsoDate(ev.occurred_at).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                          second: '2-digit',
                        })}
                      </span>
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 4: SETTINGS */}
      {/* ========================================================================= */}
      {activeTab === 'SETTINGS' && (
        <div className="space-y-3">
          <h2 className="text-lg font-black text-slate-900 tracking-tight pt-1">
            SYSTEM SETTINGS
          </h2>

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

            <button
              type="button"
              onClick={() => setIsNotificationModalOpen(true)}
              className="w-full py-2.5 rounded-xl bg-amber-50 hover:bg-amber-100 text-amber-800 text-xs font-bold flex items-center justify-center gap-2 transition-colors border border-amber-200"
            >
              <Bell className="w-4 h-4 text-amber-600" />
              <span>Notification & Alert Channels</span>
            </button>

            {station && (
              <button
                type="button"
                onClick={() => setIsCommissionModalOpen(true)}
                className="w-full py-2.5 rounded-xl bg-teal-50 hover:bg-teal-100 text-teal-800 text-xs font-bold flex items-center justify-center gap-2 transition-colors border border-teal-200"
              >
                <Cpu className="w-4 h-4 text-teal-600" />
                <span>Pair / Commission New Controller</span>
              </button>
            )}

            {onAdminSwitch && (
              <button
                type="button"
                onClick={onAdminSwitch}
                className="w-full py-2.5 rounded-xl bg-blue-50 hover:bg-blue-100 text-blue-700 text-xs font-bold flex items-center justify-center gap-2 transition-colors border border-blue-200"
              >
                <Shield className="w-4 h-4" />
                <span>Switch to Admin Console</span>
              </button>
            )}

            <button
              type="button"
              onClick={logout}
              className="w-full py-2.5 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-700 text-xs font-bold flex items-center justify-center gap-2 transition-colors border border-rose-200"
            >
              <LogOut className="w-4 h-4" />
              <span>Sign Out</span>
            </button>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* BOTTOM NAVIGATION DOCK (FLOATING ELEVATED POWER BUTTON) */}
      {/* ========================================================================= */}
      <MobileNavDock
        activeTab={activeTab}
        onTabChange={(t) => {
          setActiveTab(t);
          loadData();
        }}
        isMotorRunning={isMotorRunning}
        isProcessing={isProcessing}
        onPowerToggle={handlePowerToggle}
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
    </div>
  );
};
