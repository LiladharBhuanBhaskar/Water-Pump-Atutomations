import React, { useState, useEffect, useCallback } from 'react';
import {
  Play,
  Square,
  Calendar,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  RefreshCw,
  Activity,
  Zap,
  Clock,
  Waves,
  ChevronRight,
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
  const [loading, setLoading] = useState<boolean>(true);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successToast, setSuccessToast] = useState<string | null>(null);

  // Live telemetry state for home
  const [tankLevel, setTankLevel] = useState<number>(75.0);
  const [sumpLevel, setSumpLevel] = useState<number>(85.0);
  const [turbidity, setTurbidity] = useState<number>(3.8);
  const [ph, setPh] = useState<number>(7.3);
  const [currentAmps, setCurrentAmps] = useState<number>(0.0);
  const [voltage, setVoltage] = useState<number>(230.0);
  const [lastTelemetryTime, setLastTelemetryTime] = useState<string>(new Date().toISOString());

  // Load Home Context (First Site & Station belonging to user)
  const loadHomeData = useCallback(async () => {
    try {
      setLoading(true);
      setErrorMessage(null);
      const sites = await api.getSites();
      if (sites.length === 0) {
        setLoading(false);
        return;
      }
      const homeSite = sites[0];
      setSite(homeSite);

      const stations = await api.getStations(homeSite.id);
      if (stations.length === 0) {
        setLoading(false);
        return;
      }
      const homeStation = stations[0];
      setStation(homeStation);

      const controllers = await api.getControllers(homeStation.id);
      if (controllers.length > 0) {
        const homeCtrl = controllers[0];
        setController(homeCtrl);

        const motors = await api.getMotors(homeCtrl.id);
        if (motors.length > 0) {
          const homeMotor = motors[0];
          setMotor(homeMotor);

          // Fetch recent events for this motor
          try {
            const events = await api.getMotorEvents(homeMotor.id, { limit: 5 });
            setRecentEvents(events);
          } catch {
            // Non-critical
          }
        }

        // Fetch water quality diagnostics
        try {
          const wq = await api.getWaterQuality(homeStation.id);
          if (wq.turbidity_ntu !== undefined && wq.turbidity_ntu !== null) {
            setTurbidity(wq.turbidity_ntu);
          }
          if (wq.ph !== undefined && wq.ph !== null) {
            setPh(wq.ph);
          }
        } catch {
          // Fallback to defaults
        }

        // Fetch schedules
        try {
          const schedList = await api.getSchedules(homeStation.id);
          setSchedules(schedList);
        } catch {
          // Fallback
        }
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed loading water pump data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadHomeData();
  }, [loadHomeData]);

  // Handle live WebSocket updates
  useEffect(() => {
    if (!latestWsEvent) return;

    if (latestWsEvent.event === 'TELEMETRY') {
      const sensorCode = (latestWsEvent.sensor_code || '').toLowerCase();
      const val = latestWsEvent.value;

      if (sensorCode.includes('level') || sensorCode.includes('tank')) {
        setTankLevel(val);
      } else if (sensorCode.includes('turbidity')) {
        setTurbidity(val);
      } else if (sensorCode.includes('current')) {
        setCurrentAmps(val);
      } else if (sensorCode.includes('voltage')) {
        setVoltage(val);
      } else if (sensorCode.includes('sump')) {
        setSumpLevel(val);
      }
      setLastTelemetryTime(latestWsEvent.occurred_at || new Date().toISOString());
    } else if (latestWsEvent.event === 'MOTOR_STATE') {
      if (motor && latestWsEvent.motor_id === motor.id) {
        setMotor((prev) => (prev ? { ...prev, status: latestWsEvent.status } : null));
        if (latestWsEvent.status === 'ON') {
          setCurrentAmps(9.2);
        } else {
          setCurrentAmps(0.0);
        }
      }
    } else if (latestWsEvent.event === 'SAFETY_ALERT') {
      loadHomeData();
    }
  }, [latestWsEvent, motor, loadHomeData]);

  // Motor Action Handlers with optimistic UI updates
  const handleStartPump = async () => {
    if (!motor || !isOperator) return;
    setIsProcessing(true);
    setErrorMessage(null);
    const prevStatus = motor.status;

    // Optimistic UI state
    setMotor({ ...motor, status: 'STARTING' });

    try {
      await api.startMotor(motor.id);
      setSuccessToast('Pump Start command dispatched successfully!');
      setTimeout(() => setSuccessToast(null), 4000);
      setMotor({ ...motor, status: 'ON' });
      setCurrentAmps(9.4);
    } catch (err: any) {
      // Rollback on failure
      setMotor({ ...motor, status: prevStatus });
      setErrorMessage(err.message || 'Failed to start motor. Safety lock may be active.');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleStopPump = async () => {
    if (!motor || !isOperator) return;
    setIsProcessing(true);
    setErrorMessage(null);
    const prevStatus = motor.status;

    // Optimistic UI state
    setMotor({ ...motor, status: 'STOPPING' });

    try {
      await api.stopMotor(motor.id);
      setSuccessToast('Pump stopped successfully.');
      setTimeout(() => setSuccessToast(null), 4000);
      setMotor({ ...motor, status: 'OFF' });
      setCurrentAmps(0.0);
    } catch (err: any) {
      setMotor({ ...motor, status: prevStatus });
      setErrorMessage(err.message || 'Failed to stop motor.');
    } finally {
      setIsProcessing(false);
    }
  };

  const isMotorRunning = motor?.status === 'ON' || motor?.status === 'STARTING';
  const isMotorFaulted = motor?.status === 'FAULT';

  if (loading) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center space-y-4">
        <Loader2 className="w-10 h-10 text-cyan-400 animate-spin" />
        <p className="text-slate-400 text-sm font-medium">Connecting to Smart Water Pump...</p>
      </div>
    );
  }

  return (
    <div className="w-full max-w-xl mx-auto px-4 py-5 space-y-5 pb-24 selection:bg-cyan-500 selection:text-black">
      {/* Toast Notification */}
      {successToast && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 px-4 py-3 rounded-2xl bg-emerald-950/90 border border-emerald-500/50 text-emerald-200 text-xs font-semibold flex items-center gap-2 shadow-2xl backdrop-blur-xl animate-bounce">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{successToast}</span>
        </div>
      )}

      {/* Error Banner */}
      {errorMessage && (
        <div className="p-4 rounded-2xl bg-rose-950/80 border border-rose-800/80 text-rose-200 text-xs flex items-center justify-between gap-3 shadow-lg">
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="w-5 h-5 text-rose-400 flex-shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button
            onClick={() => setErrorMessage(null)}
            className="text-xs text-rose-400 hover:text-white font-bold p-1"
          >
            &times;
          </button>
        </div>
      )}

      {/* App Header & Station Overview */}
      <div className="flex items-center justify-between bg-slate-900/60 p-4 rounded-3xl border border-slate-800/80 backdrop-blur-md">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider text-cyan-400">
              {station?.name || 'Main Water Pump'}
            </span>
            <span className="w-1.5 h-1.5 rounded-full bg-slate-600" />
            <span className="text-xs text-slate-400">{site?.name || 'Site #1'}</span>
            {controller?.device_uid && (
              <span className="hidden sm:inline-block text-[10px] font-mono text-slate-500">
                ({controller.device_uid})
              </span>
            )}
          </div>
          <h2 className="text-xl font-black text-white tracking-tight flex items-center gap-2">
            Smart Pump Control
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <TelemetryFreshnessBadge occurredAt={lastTelemetryTime} />
          <button
            onClick={loadHomeData}
            title="Refresh Status"
            className="p-2 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* HERO SECTION: Visual Water Tank Level Gauge */}
      <div className="relative rounded-3xl bg-gradient-to-b from-slate-900 via-slate-900/90 to-slate-950 border border-slate-800/90 p-6 shadow-2xl overflow-hidden">
        {/* Subtle Background Glows */}
        <div
          className={`absolute -top-24 -right-24 w-60 h-60 rounded-full blur-3xl pointer-events-none transition-all duration-700 ${
            isMotorRunning ? 'bg-emerald-500/20' : isMotorFaulted ? 'bg-rose-500/20' : 'bg-cyan-500/15'
          }`}
        />

        <div className="relative z-10 flex flex-col sm:flex-row items-center justify-between gap-6">
          {/* Visual Tank Cylinder */}
          <div className="relative w-36 h-48 rounded-3xl border-4 border-slate-700/80 bg-slate-950/80 overflow-hidden shadow-inner flex flex-col justify-end p-1.5">
            {/* Water Wave Fill */}
            <div
              className={`w-full rounded-2xl transition-all duration-1000 relative overflow-hidden flex items-center justify-center ${
                tankLevel >= 90
                  ? 'bg-gradient-to-t from-blue-700 to-cyan-400'
                  : tankLevel <= 20
                  ? 'bg-gradient-to-t from-rose-700 to-amber-500'
                  : 'bg-gradient-to-t from-blue-600 to-cyan-400'
              }`}
              style={{ height: `${Math.max(10, Math.min(100, tankLevel))}%` }}
            >
              {/* Dynamic Wave SVG */}
              <div className="absolute inset-0 opacity-40 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-white via-transparent to-transparent animate-pulse" />
              <div className="text-center font-black text-white text-lg drop-shadow-md z-10">
                {tankLevel.toFixed(0)}%
              </div>
            </div>

            {/* Level Markings */}
            <div className="absolute left-2 top-3 text-[9px] font-mono text-slate-500">100%</div>
            <div className="absolute left-2 top-1/2 -translate-y-1/2 text-[9px] font-mono text-slate-500">50%</div>
            <div className="absolute left-2 bottom-3 text-[9px] font-mono text-slate-500">0%</div>
          </div>

          {/* Tank Level Data & Status */}
          <div className="flex-1 space-y-3 text-center sm:text-left">
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
                Overhead Water Tank
              </div>
              <div className="text-3xl font-black text-white tracking-tight flex items-center justify-center sm:justify-start gap-2 mt-0.5">
                <span>{tankLevel.toFixed(1)}%</span>
                <span className="text-sm font-semibold text-slate-400">
                  (~{(tankLevel * 10).toFixed(0)} / 1000 L)
                </span>
              </div>
            </div>

            {/* Status Pill */}
            <div className="flex items-center justify-center sm:justify-start gap-2">
              <span
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold ${
                  tankLevel >= 95
                    ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                    : tankLevel <= 20
                    ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                    : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                }`}
              >
                <Waves className="w-3.5 h-3.5" />
                {tankLevel >= 95
                  ? 'Tank Full (Overflow Guard)'
                  : tankLevel <= 20
                  ? 'Water Level Low'
                  : 'Water Level Adequate'}
              </span>
            </div>

            {/* Sump / Source Status Bar */}
            <div className="pt-2 border-t border-slate-800/80 space-y-1">
              <div className="flex justify-between text-xs text-slate-400 font-medium">
                <span>Sump / Source Level</span>
                <span className="font-bold text-slate-200">{sumpLevel.toFixed(0)}%</span>
              </div>
              <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full transition-all duration-500"
                  style={{ width: `${sumpLevel}%` }}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* THE 3 MAIN HERO ACTION BUTTONS (Start Pump, Stop Pump, Schedule Pump) */}
      {/* ========================================================================= */}
      <div className="space-y-2">
        <p className="text-xs font-bold uppercase tracking-wider text-slate-400 px-1">
          Pump Operations
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {/* BUTTON 1: 🟢 START PUMP */}
          <button
            type="button"
            onClick={handleStartPump}
            disabled={isProcessing || isMotorRunning || !isOperator}
            className={`relative group p-4 sm:p-5 rounded-3xl border text-left transition-all duration-300 flex flex-col justify-between overflow-hidden shadow-xl ${
              isMotorRunning
                ? 'bg-emerald-950/40 border-emerald-800/50 cursor-not-allowed opacity-80'
                : 'bg-gradient-to-br from-emerald-600 via-emerald-700 to-teal-800 hover:from-emerald-500 hover:to-teal-700 border-emerald-400/50 hover:shadow-emerald-500/30 hover:scale-[1.02] active:scale-[0.98]'
            }`}
          >
            <div className="flex items-center justify-between w-full mb-3">
              <div className="w-12 h-12 rounded-2xl bg-emerald-400/20 backdrop-blur-md flex items-center justify-center text-white border border-emerald-300/30 shadow-md">
                {isProcessing ? (
                  <Loader2 className="w-6 h-6 animate-spin text-white" />
                ) : (
                  <Play className="w-6 h-6 fill-white text-white" />
                )}
              </div>
              {isMotorRunning && (
                <span className="flex h-3 w-3 relative">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                </span>
              )}
            </div>
            <div>
              <div className="text-lg font-black text-white tracking-tight">START PUMP</div>
              <div className="text-xs text-emerald-100/80 font-medium">
                {isMotorRunning ? 'Pump Running' : 'One-Touch Start'}
              </div>
            </div>
          </button>

          {/* BUTTON 2: 🔴 STOP PUMP */}
          <button
            type="button"
            onClick={handleStopPump}
            disabled={isProcessing || !isOperator}
            className="relative group p-4 sm:p-5 rounded-3xl bg-gradient-to-br from-rose-600 via-rose-700 to-red-900 hover:from-rose-500 hover:to-red-800 border border-rose-400/50 text-left transition-all duration-300 flex flex-col justify-between overflow-hidden shadow-xl hover:shadow-rose-500/30 hover:scale-[1.02] active:scale-[0.98]"
          >
            <div className="flex items-center justify-between w-full mb-3">
              <div className="w-12 h-12 rounded-2xl bg-rose-400/20 backdrop-blur-md flex items-center justify-center text-white border border-rose-300/30 shadow-md">
                <Square className="w-6 h-6 fill-white text-white" />
              </div>
              <span className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded-md bg-rose-950/70 border border-rose-400/30 text-rose-200">
                E-Stop Ready
              </span>
            </div>
            <div>
              <div className="text-lg font-black text-white tracking-tight">STOP PUMP</div>
              <div className="text-xs text-rose-100/80 font-medium">Immediate Shutdown</div>
            </div>
          </button>

          {/* BUTTON 3: 📅 SCHEDULE PUMP */}
          <button
            type="button"
            onClick={() => setIsScheduleModalOpen(true)}
            className="relative group p-4 sm:p-5 rounded-3xl bg-gradient-to-br from-cyan-600 via-blue-700 to-indigo-900 hover:from-cyan-500 hover:to-indigo-800 border border-cyan-400/50 text-left transition-all duration-300 flex flex-col justify-between overflow-hidden shadow-xl hover:shadow-cyan-500/30 hover:scale-[1.02] active:scale-[0.98]"
          >
            <div className="flex items-center justify-between w-full mb-3">
              <div className="w-12 h-12 rounded-2xl bg-cyan-400/20 backdrop-blur-md flex items-center justify-center text-white border border-cyan-300/30 shadow-md">
                <Calendar className="w-6 h-6 text-white" />
              </div>
              {schedules.filter((s) => s.is_active).length > 0 && (
                <span className="text-[10px] font-extrabold px-2 py-0.5 rounded-full bg-cyan-400 text-slate-950">
                  {schedules.filter((s) => s.is_active).length} Active
                </span>
              )}
            </div>
            <div>
              <div className="text-lg font-black text-white tracking-tight">SCHEDULES</div>
              <div className="text-xs text-cyan-100/80 font-medium">Auto Timer & Days</div>
            </div>
          </button>
        </div>
      </div>

      {/* Live Motor & Power Status Card */}
      <div className="grid grid-cols-2 gap-3">
        <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800/80 space-y-1.5 backdrop-blur-md">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-400">
            <Activity className="w-4 h-4 text-cyan-400" />
            <span>Pump Motor State</span>
          </div>
          <div className="text-lg font-extrabold text-white flex items-center gap-2">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                isMotorRunning ? 'bg-emerald-400 animate-ping' : 'bg-slate-500'
              }`}
            />
            <span>{motor?.status || 'IDLE'}</span>
          </div>
          <div className="text-[11px] text-slate-500">
            {isMotorRunning ? 'Motor is actively running' : 'Motor is on standby'}
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800/80 space-y-1.5 backdrop-blur-md">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-400">
            <Zap className="w-4 h-4 text-amber-400" />
            <span>Electrical Load</span>
          </div>
          <div className="text-lg font-extrabold text-white">
            {currentAmps > 0 ? `${currentAmps.toFixed(1)} A` : '0.0 A'}
          </div>
          <div className="text-[11px] text-slate-500">
            {voltage.toFixed(0)}V &bull; {currentAmps > 15 ? 'High Load' : 'Normal Grid'}
          </div>
        </div>
      </div>

      {/* Water Purity & Safety Clearance Card */}
      <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800/80 space-y-3 backdrop-blur-md">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-xl bg-cyan-500/20 text-cyan-400">
              <ShieldCheck className="w-4 h-4" />
            </div>
            <div>
              <div className="text-xs font-bold text-white">Water Quality & Safety Interlocks</div>
              <div className="text-[11px] text-slate-400">Autonomous Edge Safety Active</div>
            </div>
          </div>
          <span
            className={`text-xs font-bold px-2.5 py-1 rounded-full border ${
              turbidity < 10
                ? 'bg-emerald-950/80 border-emerald-500/40 text-emerald-300'
                : 'bg-amber-950/80 border-amber-500/40 text-amber-300'
            }`}
          >
            {turbidity < 10 ? 'Purity: Crystal Clear' : 'Purity: Caution'}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs pt-1 border-t border-slate-800/80">
          <div className="flex justify-between p-2 rounded-xl bg-slate-950/50">
            <span className="text-slate-400">Turbidity:</span>
            <span className="font-mono font-bold text-white">{turbidity.toFixed(1)} NTU</span>
          </div>
          <div className="flex justify-between p-2 rounded-xl bg-slate-950/50">
            <span className="text-slate-400">pH Level:</span>
            <span className="font-mono font-bold text-white">{ph.toFixed(1)} pH</span>
          </div>
        </div>
      </div>

      {/* Active Schedules Preview Card */}
      <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800/80 space-y-3 backdrop-blur-md">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-indigo-400" />
            <span className="text-xs font-bold text-white uppercase tracking-wider">
              Automated Timer Schedules
            </span>
          </div>
          <button
            onClick={() => setIsScheduleModalOpen(true)}
            className="text-xs text-cyan-400 hover:text-cyan-300 font-bold flex items-center gap-1"
          >
            <span>Manage</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>

        {schedules.length === 0 ? (
          <div className="text-center py-4 text-xs text-slate-500">
            No automated schedules configured. Tap "SCHEDULES" above to set a timer.
          </div>
        ) : (
          <div className="space-y-2">
            {schedules.slice(0, 3).map((sched) => (
              <div
                key={sched.id}
                className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950/50 border border-slate-800/60 text-xs"
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      sched.is_active ? 'bg-cyan-400' : 'bg-slate-600'
                    }`}
                  />
                  <div>
                    <div className="font-bold text-white">{sched.name}</div>
                    <div className="text-[10px] text-slate-400">
                      {sched.start_time} &bull; {Math.round(sched.duration_seconds / 60)} mins
                    </div>
                  </div>
                </div>
                <Badge variant={sched.is_active ? 'success' : 'neutral'}>
                  {sched.is_active ? 'Active' : 'Disabled'}
                </Badge>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recent Activity Timeline */}
      {recentEvents.length > 0 && (
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 space-y-2.5 backdrop-blur-md">
          <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">
            Recent Pump Activity
          </div>
          <div className="space-y-2">
            {recentEvents.slice(0, 3).map((ev) => (
              <div
                key={ev.id}
                className="flex items-center justify-between text-xs p-2 rounded-xl bg-slate-950/40"
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      ev.event_type === 'STARTED'
                        ? 'bg-emerald-400'
                        : ev.event_type === 'STOPPED'
                        ? 'bg-blue-400'
                        : 'bg-rose-400'
                    }`}
                  />
                  <span className="font-semibold text-slate-200">{ev.event_type}</span>
                </div>
                <span className="text-[10px] text-slate-500 font-mono">
                  {new Date(ev.occurred_at).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

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
