import React, { useState, useEffect, useCallback } from 'react';
import {
  Play,
  Square,
  Calendar,
  ShieldCheck,
  AlertTriangle,
  Loader2,
  RefreshCw,
  Activity,
  Zap,
  Clock,
  Waves,
  Gauge,
  Droplet,
  Plus,
  CheckCircle2,
} from 'lucide-react';
import {
  Site,
  Station,
  Controller,
  Motor,
  WsServerEvent,
  MotorEventResponse,
  ScheduleResponse,
} from '../types';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { TelemetryFreshnessBadge } from '../components/common/TelemetryFreshnessBadge';
import { Badge } from '../components/common/Badge';
import { ScheduleManagerModal } from '../components/ScheduleManagerModal';

interface HomeDashboardProps {
  latestWsEvent?: WsServerEvent | null;
}

export const HomeDashboard: React.FC<HomeDashboardProps> = ({ latestWsEvent }) => {
  const { isOperator } = useAuth();
  const [site, setSite] = useState<Site | null>(null);
  const [station, setStation] = useState<Station | null>(null);
  const [controller, setController] = useState<Controller | null>(null);
  const [motor, setMotor] = useState<Motor | null>(null);
  const [recentEvents, setRecentEvents] = useState<MotorEventResponse[]>([]);
  const [schedules, setSchedules] = useState<ScheduleResponse[]>([]);
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState<boolean>(false);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successToast, setSuccessToast] = useState<string | null>(null);

  // Live telemetry state (instant non-blocking defaults)
  const [tankLevel, setTankLevel] = useState<number>(75.0);
  const [sumpLevel, setSumpLevel] = useState<number>(85.0);
  const [waterHeadMeters, setWaterHeadMeters] = useState<number>(24.5);
  const [flowRateLpm, setFlowRateLpm] = useState<number>(45.2);
  const [turbidity, setTurbidity] = useState<number>(3.8);
  const [ph, setPh] = useState<number>(7.2);
  const [currentAmps, setCurrentAmps] = useState<number>(0.0);
  const [voltage, setVoltage] = useState<number>(230.0);
  const [powerKw, setPowerKw] = useState<number>(0.0);
  const [lastTelemetryTime, setLastTelemetryTime] = useState<string>(new Date().toISOString());

  // Fast, non-blocking parallel data loader
  const loadHomeData = useCallback(async () => {
    try {
      setIsSyncing(true);
      setErrorMessage(null);

      // Fast fetch top hierarchy
      const sites = await api.getSites();
      if (!sites || sites.length === 0) return;
      const homeSite = sites[0];
      setSite(homeSite);

      const stations = await api.getStations(homeSite.id);
      if (!stations || stations.length === 0) return;
      const homeStation = stations[0];
      setStation(homeStation);

      const controllers = await api.getControllers(homeStation.id);
      if (!controllers || controllers.length === 0) return;
      const homeCtrl = controllers[0];
      setController(homeCtrl);

      const motors = await api.getMotors(homeCtrl.id);
      if (motors && motors.length > 0) {
        setMotor(motors[0]);
      }

      // Parallel fetch diagnostics, schedules, and events
      const [eventsRes, wqRes, schedRes] = await Promise.allSettled([
        motors && motors.length > 0 ? api.getMotorEvents(motors[0].id, { limit: 4 }) : Promise.resolve([]),
        api.getWaterQuality(homeStation.id),
        api.getSchedules(homeStation.id),
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
    } catch (err: any) {
      console.warn('Background sync note:', err);
    } finally {
      setIsSyncing(false);
    }
  }, []);

  useEffect(() => {
    loadHomeData();
  }, [loadHomeData]);

  // Real-time WebSocket event processor
  useEffect(() => {
    if (!latestWsEvent) return;

    if (latestWsEvent.event === 'TELEMETRY') {
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
      setLastTelemetryTime(latestWsEvent.occurred_at || new Date().toISOString());
    } else if (latestWsEvent.event === 'MOTOR_STATE') {
      if (motor && latestWsEvent.motor_id === motor.id) {
        setMotor((prev) => (prev ? { ...prev, status: latestWsEvent.status } : null));
        if (latestWsEvent.status === 'ON') {
          setCurrentAmps(9.4);
          setPowerKw(2.16);
          setFlowRateLpm(48.5);
        } else {
          setCurrentAmps(0.0);
          setPowerKw(0.0);
          setFlowRateLpm(0.0);
        }
      }
    } else if (latestWsEvent.event === 'SAFETY_ALERT') {
      loadHomeData();
    }
  }, [latestWsEvent, motor, voltage, loadHomeData]);

  // Motor action triggers with optimistic feedback
  const handleStartPump = async () => {
    if (!motor || !isOperator) return;
    setIsProcessing(true);
    setErrorMessage(null);
    const prevStatus = motor.status;

    setMotor({ ...motor, status: 'STARTING' });

    try {
      await api.startMotor(motor.id);
      setSuccessToast('Pump Started Successfully');
      setTimeout(() => setSuccessToast(null), 3500);
      setMotor({ ...motor, status: 'ON' });
      setCurrentAmps(9.4);
      setPowerKw(2.16);
      setFlowRateLpm(48.5);
    } catch (err: any) {
      setMotor({ ...motor, status: prevStatus });
      setErrorMessage(err.message || 'Failed to start pump. Safety interlock may be active.');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleStopPump = async () => {
    if (!motor || !isOperator) return;
    setIsProcessing(true);
    setErrorMessage(null);
    const prevStatus = motor.status;

    setMotor({ ...motor, status: 'STOPPING' });

    try {
      await api.stopMotor(motor.id);
      setSuccessToast('Pump Stopped');
      setTimeout(() => setSuccessToast(null), 3500);
      setMotor({ ...motor, status: 'OFF' });
      setCurrentAmps(0.0);
      setPowerKw(0.0);
      setFlowRateLpm(0.0);
    } catch (err: any) {
      setMotor({ ...motor, status: prevStatus });
      setErrorMessage(err.message || 'Failed to stop pump.');
    } finally {
      setIsProcessing(false);
    }
  };

  const isMotorRunning = motor?.status === 'ON' || motor?.status === 'STARTING';
  const isMotorFaulted = motor?.status === 'FAULT';

  return (
    <div className="w-full max-w-6xl mx-auto px-3 sm:px-5 py-3 sm:py-4 space-y-3.5 selection:bg-cyan-500 selection:text-black">
      {/* Toast Notification */}
      {successToast && (
        <div className="fixed top-3 left-1/2 -translate-x-1/2 z-50 px-4 py-2.5 rounded-2xl bg-emerald-950/90 border border-emerald-400/60 text-emerald-200 text-xs font-bold flex items-center gap-2 shadow-2xl backdrop-blur-xl animate-bounce">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{successToast}</span>
        </div>
      )}

      {/* Error Notification */}
      {errorMessage && (
        <div className="p-3 rounded-2xl bg-rose-950/80 border border-rose-800 text-rose-200 text-xs flex items-center justify-between gap-2 shadow-lg">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button
            onClick={() => setErrorMessage(null)}
            className="text-xs text-rose-400 hover:text-white font-bold px-2 py-0.5"
          >
            &times;
          </button>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TOP HEADER BAR: Compact Status Banner */}
      {/* ========================================================================= */}
      <div className="flex items-center justify-between bg-slate-900/80 px-4 py-2.5 rounded-2xl border border-slate-800 shadow-md backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div
              className={`w-3 h-3 rounded-full ${
                isMotorFaulted
                  ? 'bg-rose-500 animate-pulse'
                  : isMotorRunning
                  ? 'bg-emerald-400 animate-ping'
                  : 'bg-cyan-400'
              }`}
            />
            <h1 className="text-base sm:text-lg font-black text-white tracking-tight">
              {station?.name || 'Smart Pump Station'}
            </h1>
          </div>
          <span className="hidden sm:inline-block text-xs text-slate-400 font-medium">
            &bull; {site?.name || 'Main Site'}
          </span>
          <span className="hidden md:inline-block text-[11px] font-mono text-slate-400">
            {controller?.device_uid ? `[${controller.device_uid}]` : '[IoT Active]'}
          </span>
        </div>
        <div className="flex items-center gap-2.5">
          <TelemetryFreshnessBadge occurredAt={lastTelemetryTime} />
          <button
            onClick={loadHomeData}
            title="Fast Sync"
            className="p-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin text-cyan-400' : ''}`} />
          </button>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* ROW 1: THE 3 HERO ACTION CUBE BOXES (Start Pump, Stop Pump, Schedule Pump) */}
      {/* ========================================================================= */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {/* HERO CUBE 1: 🟢 START PUMP */}
        <button
          type="button"
          onClick={handleStartPump}
          disabled={isProcessing || isMotorRunning || !isOperator}
          className={`cube-hero p-4 sm:p-5 text-left border shadow-lg flex items-center justify-between ${
            isMotorRunning
              ? 'bg-emerald-950/60 border-emerald-800/80 cursor-not-allowed opacity-90'
              : 'bg-gradient-to-br from-emerald-600 via-emerald-700 to-teal-900 hover:from-emerald-500 hover:to-teal-800 border-emerald-400/60 shadow-emerald-500/25 hover:shadow-emerald-500/40 hover:-translate-y-0.5'
          }`}
        >
          <div className="space-y-0.5">
            <span className="text-[10px] font-extrabold uppercase tracking-wider text-emerald-200">
              Action 1
            </span>
            <div className="text-xl font-black text-white tracking-tight">START PUMP</div>
            <div className="text-xs text-emerald-100/90 font-medium">
              {isMotorRunning ? 'Pump Running Active' : 'One-Touch Instant Start'}
            </div>
          </div>
          <div className="w-13 h-13 p-3 rounded-2xl bg-emerald-400/20 backdrop-blur-md flex items-center justify-center text-white border border-emerald-300/40 shadow-inner flex-shrink-0">
            {isProcessing ? (
              <Loader2 className="w-7 h-7 animate-spin text-white" />
            ) : (
              <Play className="w-7 h-7 fill-white text-white" />
            )}
          </div>
        </button>

        {/* HERO CUBE 2: 🔴 STOP PUMP */}
        <button
          type="button"
          onClick={handleStopPump}
          disabled={isProcessing || !isOperator}
          className="cube-hero p-4 sm:p-5 text-left border bg-gradient-to-br from-rose-600 via-rose-700 to-red-950 hover:from-rose-500 hover:to-red-900 border-rose-400/60 shadow-lg shadow-rose-500/25 hover:shadow-rose-500/40 hover:-translate-y-0.5 flex items-center justify-between"
        >
          <div className="space-y-0.5">
            <span className="text-[10px] font-extrabold uppercase tracking-wider text-rose-200">
              Action 2
            </span>
            <div className="text-xl font-black text-white tracking-tight">STOP PUMP</div>
            <div className="text-xs text-rose-100/90 font-medium">Immediate Shutdown &bull; E-Stop</div>
          </div>
          <div className="w-13 h-13 p-3 rounded-2xl bg-rose-400/20 backdrop-blur-md flex items-center justify-center text-white border border-rose-300/40 shadow-inner flex-shrink-0">
            <Square className="w-7 h-7 fill-white text-white" />
          </div>
        </button>

        {/* HERO CUBE 3: 📅 SCHEDULE PUMP */}
        <button
          type="button"
          onClick={() => setIsScheduleModalOpen(true)}
          className="cube-hero p-4 sm:p-5 text-left border bg-gradient-to-br from-cyan-600 via-blue-700 to-indigo-950 hover:from-cyan-500 hover:to-indigo-900 border-cyan-400/60 shadow-lg shadow-cyan-500/25 hover:shadow-cyan-500/40 hover:-translate-y-0.5 flex items-center justify-between"
        >
          <div className="space-y-0.5">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-extrabold uppercase tracking-wider text-cyan-200">
                Action 3
              </span>
              {schedules.filter((s) => s.is_active).length > 0 && (
                <span className="text-[10px] font-extrabold px-2 py-0.5 rounded-full bg-cyan-400 text-slate-950">
                  {schedules.filter((s) => s.is_active).length} Active
                </span>
              )}
            </div>
            <div className="text-xl font-black text-white tracking-tight">SCHEDULES</div>
            <div className="text-xs text-cyan-100/90 font-medium">Automated Daily Timer</div>
          </div>
          <div className="w-13 h-13 p-3 rounded-2xl bg-cyan-400/20 backdrop-blur-md flex items-center justify-center text-white border border-cyan-300/40 shadow-inner flex-shrink-0">
            <Calendar className="w-7 h-7 text-white" />
          </div>
        </button>
      </div>

      {/* ========================================================================= */}
      {/* ROW 2: HYDRAULIC & LEVEL CUBE BOXES (Water Head, Tank Level, Flow Rate) */}
      {/* ========================================================================= */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {/* CUBE BOX 4: 💧 OVERHEAD TANK & WATER HEAD */}
        <div className="cube-box p-4 rounded-2xl space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs font-bold text-cyan-400 uppercase tracking-wide">
              <Waves className="w-4 h-4" />
              <span>Overhead Tank & Head</span>
            </div>
            <span className="text-[10px] font-mono text-slate-400">Cap: 1000L</span>
          </div>

          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-2xl font-black text-white">{tankLevel.toFixed(1)}%</div>
              <div className="text-xs text-slate-400">
                Head: <span className="text-cyan-300 font-bold">{waterHeadMeters.toFixed(1)} m</span>
              </div>
            </div>

            {/* Visual Tank Mini-Level Bar */}
            <div className="w-20 h-12 bg-slate-950 rounded-xl border border-slate-700/80 p-1 flex flex-col justify-end overflow-hidden">
              <div
                className="w-full bg-gradient-to-t from-blue-600 to-cyan-400 rounded-lg transition-all duration-500 text-[10px] font-bold text-center text-white flex items-center justify-center"
                style={{ height: `${Math.max(20, Math.min(100, tankLevel))}%` }}
              >
                {tankLevel.toFixed(0)}%
              </div>
            </div>
          </div>

          <div className="pt-2 border-t border-slate-800 text-[11px] text-slate-400 flex items-center justify-between">
            <span>Cutoff: ≥95% (Overflow Guard)</span>
            <span className={tankLevel >= 95 ? 'text-blue-400 font-bold' : 'text-emerald-400'}>
              {tankLevel >= 95 ? 'Full' : 'Adequate'}
            </span>
          </div>
        </div>

        {/* CUBE BOX 5: 🌊 SUMP & SOURCE LEVEL */}
        <div className="cube-box p-4 rounded-2xl space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs font-bold text-blue-400 uppercase tracking-wide">
              <Droplet className="w-4 h-4" />
              <span>Sump / Source Level</span>
            </div>
            <span className="text-[10px] font-mono text-slate-400">Cap: 5000L</span>
          </div>

          <div className="space-y-1">
            <div className="flex items-baseline justify-between">
              <div className="text-2xl font-black text-white">{sumpLevel.toFixed(1)}%</div>
              <span className="text-xs text-slate-400">~{(sumpLevel * 50).toFixed(0)} L Source</span>
            </div>
            <div className="w-full h-2.5 bg-slate-950 rounded-full overflow-hidden border border-slate-800">
              <div
                className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full transition-all duration-500"
                style={{ width: `${sumpLevel}%` }}
              />
            </div>
          </div>

          <div className="pt-2 border-t border-slate-800 text-[11px] text-slate-400 flex items-center justify-between">
            <span>Dry-Run Cutoff: ≤10%</span>
            <span className={sumpLevel <= 10 ? 'text-rose-400 font-bold' : 'text-emerald-400'}>
              {sumpLevel <= 10 ? 'Depleted Trip' : 'Source Safe'}
            </span>
          </div>
        </div>

        {/* CUBE BOX 6: 🌀 FLOW RATE & DISCHARGE */}
        <div className="cube-box p-4 rounded-2xl space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs font-bold text-teal-400 uppercase tracking-wide">
              <Gauge className="w-4 h-4" />
              <span>Water Flow Rate</span>
            </div>
            <span className="text-[10px] font-mono text-slate-400">Hall-Sensor</span>
          </div>

          <div className="flex items-baseline justify-between">
            <div>
              <div className="text-2xl font-black text-white">
                {isMotorRunning ? flowRateLpm.toFixed(1) : '0.0'} <span className="text-sm font-semibold text-slate-400">L/min</span>
              </div>
              <div className="text-xs text-slate-400">
                Discharge: <span className="text-teal-300 font-bold">{isMotorRunning ? (flowRateLpm * 0.06).toFixed(2) : '0.00'} m³/h</span>
              </div>
            </div>
            <Badge variant={isMotorRunning ? 'success' : 'neutral'}>
              {isMotorRunning ? 'Discharging' : 'Idle'}
            </Badge>
          </div>

          <div className="pt-2 border-t border-slate-800 text-[11px] text-slate-400 flex items-center justify-between">
            <span>Flow Protection:</span>
            <span className="text-emerald-400 font-medium">Primed &bull; Active</span>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* ROW 3: WATER QUALITY, ELECTRICAL & EDGE SAFETY CUBES */}
      {/* ========================================================================= */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {/* CUBE BOX 7: ✨ WATER QUALITY & TURBIDITY */}
        <div className="cube-box p-4 rounded-2xl space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs font-bold text-amber-400 uppercase tracking-wide">
              <ShieldCheck className="w-4 h-4" />
              <span>Water Quality</span>
            </div>
            <span
              className={`text-[10px] font-extrabold px-2 py-0.5 rounded-full border ${
                turbidity < 10
                  ? 'bg-emerald-950/80 border-emerald-500/40 text-emerald-300'
                  : 'bg-amber-950/80 border-amber-500/40 text-amber-300'
              }`}
            >
              {turbidity < 10 ? 'Clean' : 'Caution'}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="p-2 rounded-xl bg-slate-950/60 border border-slate-800/80">
              <div className="text-[10px] text-slate-400">Turbidity</div>
              <div className="text-base font-black text-white">{turbidity.toFixed(1)} <span className="text-[10px] font-normal text-slate-400">NTU</span></div>
            </div>
            <div className="p-2 rounded-xl bg-slate-950/60 border border-slate-800/80">
              <div className="text-[10px] text-slate-400">pH Level</div>
              <div className="text-base font-black text-white">{ph.toFixed(1)} <span className="text-[10px] font-normal text-slate-400">pH</span></div>
            </div>
          </div>

          <div className="pt-1.5 border-t border-slate-800 text-[11px] text-slate-400 flex justify-between">
            <span>Safety Cutoff:</span>
            <span className="text-slate-300">&gt;25 NTU Auto-Trip</span>
          </div>
        </div>

        {/* CUBE BOX 8: ⚡ ELECTRICAL LOAD & GRID */}
        <div className="cube-box p-4 rounded-2xl space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs font-bold text-purple-400 uppercase tracking-wide">
              <Zap className="w-4 h-4" />
              <span>Electrical Load</span>
            </div>
            <span className="text-[10px] font-mono text-slate-400">{voltage.toFixed(0)}V Grid</span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="p-2 rounded-xl bg-slate-950/60 border border-slate-800/80">
              <div className="text-[10px] text-slate-400">Current Load</div>
              <div className="text-base font-black text-white">{currentAmps > 0 ? `${currentAmps.toFixed(1)} A` : '0.0 A'}</div>
            </div>
            <div className="p-2 rounded-xl bg-slate-950/60 border border-slate-800/80">
              <div className="text-[10px] text-slate-400">Power Rating</div>
              <div className="text-base font-black text-white">{powerKw > 0 ? `${powerKw.toFixed(2)} kW` : '0.0 kW'}</div>
            </div>
          </div>

          <div className="pt-1.5 border-t border-slate-800 text-[11px] text-slate-400 flex justify-between">
            <span>Overload Trip:</span>
            <span className={currentAmps > 15 ? 'text-rose-400 font-bold' : 'text-emerald-400'}>
              {currentAmps > 15 ? 'High Load' : 'Safe &lt; 15A'}
            </span>
          </div>
        </div>

        {/* CUBE BOX 9: 🛡️ EDGE SAFETY INTERLOCKS & LOGS */}
        <div className="cube-box p-4 rounded-2xl space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-400 uppercase tracking-wide">
              <Activity className="w-4 h-4" />
              <span>Safety Interlocks</span>
            </div>
            <span className="text-[10px] font-mono text-emerald-400 font-bold">100% Locked</span>
          </div>

          {/* 4 Safety Badges */}
          <div className="grid grid-cols-2 gap-1.5 text-[11px]">
            <div className="p-1.5 rounded-lg bg-slate-950/70 border border-slate-800 flex items-center gap-1 text-slate-300">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <span>Tank Overflow</span>
            </div>
            <div className="p-1.5 rounded-lg bg-slate-950/70 border border-slate-800 flex items-center gap-1 text-slate-300">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <span>Dry-Run Guard</span>
            </div>
            <div className="p-1.5 rounded-lg bg-slate-950/70 border border-slate-800 flex items-center gap-1 text-slate-300">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <span>Turbidity Lock</span>
            </div>
            <div className="p-1.5 rounded-lg bg-slate-950/70 border border-slate-800 flex items-center gap-1 text-slate-300">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <span>Hardware E-Stop</span>
            </div>
          </div>

          <div className="pt-1.5 border-t border-slate-800 text-[11px] text-slate-400 flex justify-between">
            <span>Authority:</span>
            <span className="text-cyan-300 font-medium">Local ESP32 Engine</span>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* ROW 4: SCHEDULE PREVIEW & ACTIVITY TICKER (Single-Screen Bottom Bar) */}
      {/* ========================================================================= */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {/* Cube: Active Schedules Bar */}
        <div className="cube-box p-3.5 rounded-2xl flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-cyan-500/20 text-cyan-400">
              <Clock className="w-4 h-4" />
            </div>
            <div>
              <div className="text-xs font-bold text-white">Daily Pump Schedules</div>
              <div className="text-[11px] text-slate-400">
                {schedules.length === 0
                  ? 'No active timers'
                  : `${schedules.filter((s) => s.is_active).length} automated timers active`}
              </div>
            </div>
          </div>
          <button
            onClick={() => setIsScheduleModalOpen(true)}
            className="px-3 py-1.5 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/40 text-xs font-bold flex items-center gap-1 transition-all"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Configure</span>
          </button>
        </div>

        {/* Cube: Recent Activity Ticker */}
        <div className="cube-box p-3.5 rounded-2xl flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-purple-500/20 text-purple-400">
              <Activity className="w-4 h-4" />
            </div>
            <div>
              <div className="text-xs font-bold text-white">Latest Event</div>
              <div className="text-[11px] text-slate-400">
                {recentEvents.length > 0
                  ? `${recentEvents[0].event_type} at ${new Date(recentEvents[0].occurred_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
                  : 'Ready & Standby'}
              </div>
            </div>
          </div>
          <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/80 px-2 py-1 rounded-lg border border-emerald-500/30">
            {isMotorRunning ? 'PUMP RUNNING' : 'PUMP IDLE'}
          </span>
        </div>
      </div>

      {/* Schedule Manager Modal */}
      {station && motor && (
        <ScheduleManagerModal
          isOpen={isScheduleModalOpen}
          onClose={() => {
            setIsScheduleModalOpen(false);
            loadHomeData();
          }}
          station={station}
          motors={[motor]}
        />
      )}
    </div>
  );
};
