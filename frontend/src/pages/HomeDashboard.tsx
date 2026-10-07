import React, { useState, useEffect, useCallback } from 'react';
import {
  Home,
  Droplets,
  Power,
  ShieldCheck,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Octagon,
  RefreshCw,
  Activity,
} from 'lucide-react';
import {
  Site,
  Station,
  Controller,
  Motor,
  WsServerEvent,
  MotorEventResponse,
} from '../types';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { TelemetryFreshnessBadge } from '../components/common/TelemetryFreshnessBadge';
import { ControllerOfflineOverlay } from '../components/common/ControllerOfflineOverlay';
import { ErrorBoundary } from '../components/common/ErrorBoundary';
import { Badge } from '../components/common/Badge';

interface HomeDashboardProps {
  latestWsEvent?: WsServerEvent | null;
}

export const HomeDashboard: React.FC<HomeDashboardProps> = ({ latestWsEvent }) => {
  const { user, isOperator } = useAuth();
  const [site, setSite] = useState<Site | null>(null);
  const [station, setStation] = useState<Station | null>(null);
  const [controller, setController] = useState<Controller | null>(null);
  const [motor, setMotor] = useState<Motor | null>(null);
  const [recentEvents, setRecentEvents] = useState<MotorEventResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successToast, setSuccessToast] = useState<string | null>(null);

  // Live telemetry state for home
  const [tankLevel, setTankLevel] = useState<number>(75.0);
  const [sumpLevel] = useState<number>(85.0);
  const [turbidity, setTurbidity] = useState<number>(3.8);
  const [ph, setPh] = useState<number>(7.3);
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
          // Fallback to default/sim
        }
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to load home data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadHomeData();
  }, [loadHomeData]);

  // Handle real-time WebSocket events
  useEffect(() => {
    if (!latestWsEvent) return;

    if (latestWsEvent.event === 'TELEMETRY') {
      const { unit, value, occurred_at } = latestWsEvent;
      setLastTelemetryTime(occurred_at || new Date().toISOString());

      if (unit === '%' || unit === 'cm') {
        setTankLevel(Number(value));
      } else if (unit === 'NTU') {
        setTurbidity(Number(value));
      } else if (unit === 'pH') {
        setPh(Number(value));
      }
    } else if (latestWsEvent.event === 'MOTOR_STATE') {
      if (motor && latestWsEvent.motor_id === motor.id) {
        setMotor((prev) => (prev ? { ...prev, status: latestWsEvent.status } : prev));
        setIsProcessing(false);
      }
    } else if (latestWsEvent.event === 'COMMAND_LIFECYCLE') {
      if (motor && latestWsEvent.motor_id === motor.id) {
        if (latestWsEvent.status === 'EXECUTED') {
          setIsProcessing(false);
          setSuccessToast('Command successfully executed.');
          setTimeout(() => setSuccessToast(null), 4000);
        } else if (latestWsEvent.status === 'FAILED' || latestWsEvent.status === 'TIMEOUT') {
          setIsProcessing(false);
          setErrorMessage(`Command failed: ${latestWsEvent.error_message || 'Timeout'}`);
        }
      }
    }
  }, [latestWsEvent, motor]);

  // Home Motor Control Actions with Optimistic UI & Safe Rollback
  const handleStartPump = async () => {
    if (!motor || !isOperator || isProcessing) return;
    const previousStatus = motor.status;
    setIsProcessing(true);
    setErrorMessage(null);

    // Optimistic visual state
    setMotor({ ...motor, status: 'STARTING' });

    try {
      await api.startMotor(motor.id);
      setSuccessToast('Start command dispatched to pump.');
      setTimeout(() => setSuccessToast(null), 4000);
    } catch (err: any) {
      // Rollback optimistic state
      setMotor({ ...motor, status: previousStatus });
      setIsProcessing(false);
      setErrorMessage(`Pump start failed: ${err.message || 'Safety or network rejection'}`);
    }
  };

  const handleStopPump = async () => {
    if (!motor || !isOperator || isProcessing) return;
    const previousStatus = motor.status;
    setIsProcessing(true);
    setErrorMessage(null);

    // Optimistic visual state
    setMotor({ ...motor, status: 'STOPPING' });

    try {
      await api.stopMotor(motor.id);
      setSuccessToast('Stop command dispatched to pump.');
      setTimeout(() => setSuccessToast(null), 4000);
    } catch (err: any) {
      // Rollback optimistic state
      setMotor({ ...motor, status: previousStatus });
      setIsProcessing(false);
      setErrorMessage(`Pump stop failed: ${err.message || 'Network error'}`);
    }
  };

  const handleEmergencyStop = async () => {
    if (!motor || !isOperator) return;
    setIsProcessing(true);
    setErrorMessage(null);

    try {
      await api.emergencyStopMotor(motor.id);
      setMotor({ ...motor, status: 'STOPPING' });
      setSuccessToast('Emergency stop command dispatched.');
      setTimeout(() => setSuccessToast(null), 4000);
    } catch (err: any) {
      setIsProcessing(false);
      setErrorMessage(`Emergency stop failed: ${err.message}`);
    }
  };

  if (loading) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center gap-4">
        <Loader2 className="w-10 h-10 text-cyan-400 animate-spin" />
        <p className="text-slate-400 font-medium text-sm">Loading Home Sanctuary...</p>
      </div>
    );
  }

  const isRunning = motor?.status === 'ON';
  const isTransitioning = motor?.status === 'STARTING' || motor?.status === 'STOPPING' || isProcessing;
  const isFault = motor?.status === 'FAULT';
  const isControllerOffline = controller?.status === 'OFFLINE' || controller?.status === 'DECOMMISSIONED';

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 animate-fade-in">
      {/* Home Header Banner */}
      <div className="glass-panel p-6 sm:p-8 rounded-3xl border border-slate-800/80 bg-gradient-to-r from-slate-900/90 via-slate-900/60 to-cyan-950/30 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 shadow-2xl">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/30">
            <Home className="w-7 h-7 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
                {site?.name || 'My Home Sanctuary'}
              </h1>
              <Badge variant="info" size="sm">
                HOME MODE
              </Badge>
            </div>
            <p className="text-xs sm:text-sm text-slate-400 mt-1">
              Station: <span className="text-slate-200 font-semibold">{station?.name || 'Main Pump House'}</span> &bull;{' '}
              Role: <span className="text-cyan-400 font-bold">{user?.role}</span>
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <TelemetryFreshnessBadge occurredAt={lastTelemetryTime} />
          <button
            type="button"
            onClick={loadHomeData}
            title="Refresh Data"
            className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Controller Offline Warning if applicable */}
      {isControllerOffline && (
        <ControllerOfflineOverlay controller={controller} />
      )}

      {/* User Alerts & Toasts */}
      {errorMessage && (
        <div className="p-4 rounded-2xl bg-rose-950/80 border border-rose-800 text-rose-200 text-xs font-semibold flex items-center justify-between gap-3 shadow-lg">
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button
            onClick={() => setErrorMessage(null)}
            className="text-rose-300 hover:text-white font-bold text-sm px-2"
          >
            &times;
          </button>
        </div>
      )}

      {successToast && (
        <div className="p-4 rounded-2xl bg-emerald-950/80 border border-emerald-800 text-emerald-200 text-xs font-semibold flex items-center gap-2.5 shadow-lg">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
          <span>{successToast}</span>
        </div>
      )}

      {/* Main Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Card 1: Tank Water Level Hero Gauge */}
        <ErrorBoundary fallbackTitle="Tank Level Error">
          <div className="glass-panel p-6 rounded-3xl border border-slate-800 flex flex-col justify-between gap-6 shadow-xl relative overflow-hidden">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
                  <Droplets className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Overhead Water Tank</h3>
                  <p className="text-xs text-slate-400">Live storage capacity</p>
                </div>
              </div>
              <Badge variant={tankLevel >= 95 ? 'danger' : tankLevel <= 20 ? 'warning' : 'success'} size="md">
                {tankLevel >= 95 ? 'TANK FULL' : tankLevel <= 20 ? 'LOW WATER' : 'NORMAL'}
              </Badge>
            </div>

            {/* Visual Tank Percentage Meter */}
            <div className="flex flex-col items-center justify-center py-4">
              <div className="relative w-40 h-40 rounded-full border-4 border-slate-800 flex items-center justify-center bg-slate-900/60 shadow-inner">
                <div
                  className="absolute inset-0 rounded-full bg-gradient-to-t from-cyan-500/20 to-blue-600/10 transition-all duration-700"
                  style={{ height: `${Math.min(100, Math.max(0, tankLevel))}%`, bottom: 0, top: 'auto' }}
                />
                <div className="relative z-10 text-center">
                  <span className="text-4xl font-black text-white tracking-tight">{Math.round(tankLevel)}%</span>
                  <p className="text-[11px] text-cyan-400 font-bold uppercase tracking-wider mt-0.5">Stored Water</p>
                </div>
              </div>

              {/* Progress bar */}
              <div className="w-full bg-slate-800/80 rounded-full h-2.5 mt-6 overflow-hidden border border-slate-700/50">
                <div
                  className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(100, Math.max(0, tankLevel))}%` }}
                />
              </div>
            </div>

            <div className="flex items-center justify-between text-xs text-slate-400 pt-3 border-t border-slate-800/80">
              <span>Auto-stop cutoff: <b className="text-slate-200">95%</b></span>
              <span>Sump Source: <b className="text-emerald-400">{Math.round(sumpLevel)}%</b></span>
            </div>
          </div>
        </ErrorBoundary>

        {/* Card 2: One-Touch Motor Action */}
        <ErrorBoundary fallbackTitle="Pump Control Error">
          <div
            className={`glass-panel p-6 rounded-3xl border flex flex-col justify-between gap-6 shadow-xl transition-all duration-300 ${
              isRunning
                ? 'border-emerald-500/40 bg-emerald-950/10 shadow-emerald-500/10'
                : isFault
                ? 'border-rose-500/40 bg-rose-950/10 shadow-rose-500/10'
                : 'border-slate-800'
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div
                  className={`w-9 h-9 rounded-xl flex items-center justify-center border ${
                    isRunning
                      ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400'
                      : isFault
                      ? 'bg-rose-500/20 border-rose-500/40 text-rose-400'
                      : 'bg-slate-800 border-slate-700 text-slate-400'
                  }`}
                >
                  <Power className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">{motor?.name || 'Main Water Pump'}</h3>
                  <p className="text-xs text-slate-400">{motor?.motor_code || 'PUMP-01'}</p>
                </div>
              </div>

              <Badge
                variant={isRunning ? 'success' : isFault ? 'danger' : isTransitioning ? 'warning' : 'neutral'}
                dot
                size="md"
              >
                {motor?.status || 'OFF'}
              </Badge>
            </div>

            {/* Pump State Display */}
            <div className="text-center py-4">
              <div
                className={`w-24 h-24 mx-auto rounded-3xl flex items-center justify-center border-2 transition-all duration-500 shadow-2xl ${
                  isRunning
                    ? 'bg-emerald-500/20 border-emerald-400 shadow-emerald-500/30 text-emerald-300 animate-pulse'
                    : isFault
                    ? 'bg-rose-500/20 border-rose-500 shadow-rose-500/30 text-rose-400'
                    : 'bg-slate-900/80 border-slate-800 text-slate-500 shadow-inner'
                }`}
              >
                <Power className="w-12 h-12" />
              </div>
              <p className="text-sm font-bold text-slate-200 mt-3">
                {isRunning ? 'Pumping Water to Tank' : isFault ? 'Safety Trip Latched' : 'Pump in Standby'}
              </p>
            </div>

            {/* Controls */}
            <div className="space-y-3">
              {isOperator ? (
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={isRunning ? handleStopPump : handleStartPump}
                    disabled={isTransitioning || isFault || isControllerOffline}
                    className={`w-full py-3.5 px-6 rounded-2xl flex items-center justify-center gap-2 font-bold text-sm tracking-wider uppercase transition-all duration-300 shadow-xl border cursor-pointer ${
                      isRunning
                        ? 'bg-rose-600 hover:bg-rose-500 text-white border-rose-400/40 shadow-rose-600/25'
                        : 'bg-emerald-600 hover:bg-emerald-500 text-white border-emerald-400/40 shadow-emerald-600/25'
                    } disabled:opacity-40 disabled:cursor-not-allowed`}
                  >
                    {isTransitioning ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>PROCESSING...</span>
                      </>
                    ) : (
                      <>
                        <Power className="w-4 h-4" />
                        <span>{isRunning ? 'STOP PUMP' : 'START PUMP'}</span>
                      </>
                    )}
                  </button>

                  <button
                    type="button"
                    onClick={handleEmergencyStop}
                    disabled={isTransitioning || isControllerOffline}
                    className="p-3.5 rounded-2xl bg-rose-950/80 hover:bg-rose-900 text-rose-300 border border-rose-700/60 transition-colors shadow-lg"
                    title="Emergency Stop"
                  >
                    <Octagon className="w-5 h-5 text-rose-400" />
                  </button>
                </div>
              ) : (
                <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-center">
                  <p className="text-xs text-slate-400 italic">
                    Family Member Mode: Read-only observation enabled.
                  </p>
                </div>
              )}
            </div>
          </div>
        </ErrorBoundary>

        {/* Card 3: Water Quality & Purity Indicator */}
        <ErrorBoundary fallbackTitle="Water Quality Error">
          <div className="glass-panel p-6 rounded-3xl border border-slate-800 flex flex-col justify-between gap-6 shadow-xl">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-purple-500/10 border border-purple-500/30 flex items-center justify-center text-purple-400">
                  <Sparkles className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Water Purity</h3>
                  <p className="text-xs text-slate-400">Turbidity & pH safety</p>
                </div>
              </div>
              <Badge variant={turbidity > 25 ? 'danger' : turbidity > 15 ? 'warning' : 'success'} size="md">
                {turbidity > 25 ? 'UNSAFE' : turbidity > 15 ? 'FAIR' : 'EXCELLENT'}
              </Badge>
            </div>

            {/* Quality Metrics */}
            <div className="grid grid-cols-2 gap-4 py-2">
              <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 text-center">
                <span className="text-xs text-slate-400 font-semibold uppercase">Turbidity</span>
                <p className="text-2xl font-black text-white mt-1">{turbidity.toFixed(1)} <span className="text-xs font-normal text-slate-400">NTU</span></p>
                <span className="text-[10px] text-emerald-400 font-medium">&le; 25.0 Cutoff</span>
              </div>

              <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 text-center">
                <span className="text-xs text-slate-400 font-semibold uppercase">pH Level</span>
                <p className="text-2xl font-black text-white mt-1">{ph.toFixed(1)}</p>
                <span className="text-[10px] text-cyan-400 font-medium">Safe 6.5–8.5</span>
              </div>
            </div>

            <div className="p-3 rounded-2xl bg-emerald-500/10 border border-emerald-500/25 flex items-center gap-2.5 text-xs text-emerald-300">
              <ShieldCheck className="w-4 h-4 text-emerald-400 flex-shrink-0" />
              <span>Safe for residential consumption and household utilization.</span>
            </div>
          </div>
        </ErrorBoundary>
      </div>

      {/* Recent Activity Log */}
      <ErrorBoundary fallbackTitle="Activity Feed Error">
        <div className="glass-panel p-6 sm:p-8 rounded-3xl border border-slate-800 space-y-4 shadow-xl">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Activity className="w-5 h-5 text-cyan-400" />
              <h3 className="text-lg font-bold text-white tracking-tight">Recent Home Activity</h3>
            </div>
            <span className="text-xs text-slate-400">Latest automatic & manual events</span>
          </div>

          {recentEvents.length > 0 ? (
            <div className="divide-y divide-slate-800/60">
              {recentEvents.map((evt) => (
                <div key={evt.id} className="py-3 flex items-center justify-between gap-4 text-xs">
                  <div className="flex items-center gap-3">
                    <span className="w-2 h-2 rounded-full bg-cyan-400" />
                    <span className="font-semibold text-slate-200">{evt.event_type}</span>
                    <span className="text-slate-400">{evt.description || 'State updated'}</span>
                  </div>
                  <span className="text-slate-500 font-mono">
                    {new Date(evt.occurred_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="py-8 text-center text-xs text-slate-500 italic">
              No recent motor events recorded. System operating in steady state.
            </div>
          )}
        </div>
      </ErrorBoundary>
    </div>
  );
};
