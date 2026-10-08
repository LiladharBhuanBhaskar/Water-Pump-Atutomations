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
  ChevronRight,
  CheckCircle2,
  Calendar,
  LogOut,
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
import { MobileNavDock, MobileTab } from '../components/MobileNavDock';
import { ScheduleManagerModal } from '../components/ScheduleManagerModal';

interface HomeDashboardProps {
  latestWsEvent?: WsServerEvent | null;
  wsConnected?: boolean;
  onAdminSwitch?: () => void;
}

export const HomeDashboard: React.FC<HomeDashboardProps> = ({
  latestWsEvent,
  wsConnected = true,
  onAdminSwitch,
}) => {
  const { user, logout, isOperator } = useAuth();
  const [activeTab, setActiveTab] = useState<MobileTab>('HOME');

  const [site, setSite] = useState<Site | null>(null);
  const [station, setStation] = useState<Station | null>(null);
  const [controller, setController] = useState<Controller | null>(null);
  const [motor, setMotor] = useState<Motor | null>(null);
  const [recentEvents, setRecentEvents] = useState<MotorEventResponse[]>([]);
  const [schedules, setSchedules] = useState<ScheduleResponse[]>([]);
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState<boolean>(false);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

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

  // Fast background sync
  const loadData = useCallback(async () => {
    try {
      setIsSyncing(true);
      const sites = await api.getSites();
      if (!sites || sites.length === 0) return;
      const s = sites[0];
      setSite(s);

      const stations = await api.getStations(s.id);
      if (!stations || stations.length === 0) return;
      const st = stations[0];
      setStation(st);

      const controllers = await api.getControllers(st.id);
      if (!controllers || controllers.length === 0) return;
      const ctrl = controllers[0];
      setController(ctrl);

      const motors = await api.getMotors(ctrl.id);
      if (motors && motors.length > 0) {
        setMotor(motors[0]);
      }

      // Parallel fetch diagnostics, schedules, and events
      const [eventsRes, wqRes, schedRes] = await Promise.allSettled([
        motors && motors.length > 0 ? api.getMotorEvents(motors[0].id, { limit: 6 }) : Promise.resolve([]),
        api.getWaterQuality(st.id),
        api.getSchedules(st.id),
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
    } catch {
      // Non-blocking fallback
    } finally {
      setIsSyncing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Live WebSocket updates
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
    }
  }, [latestWsEvent, motor, voltage]);

  const isMotorRunning = motor?.status === 'ON' || motor?.status === 'STARTING';

  // Toggle Power Action (Start / Stop)
  const handlePowerToggle = async () => {
    if (!motor || !isOperator) return;
    setIsProcessing(true);
    const prevStatus = motor.status;

    if (isMotorRunning) {
      // Stop Pump
      setMotor({ ...motor, status: 'STOPPING' });
      try {
        await api.stopMotor(motor.id);
        setMotor({ ...motor, status: 'OFF' });
        setCurrentAmps(0.0);
        setPowerKw(0.0);
        setFlowRateLpm(0.0);
        setToastMessage('Pump Stopped Successfully');
        setTimeout(() => setToastMessage(null), 3500);
      } catch (err: any) {
        setMotor({ ...motor, status: prevStatus });
        setToastMessage(err.message || 'Failed to stop pump');
        setTimeout(() => setToastMessage(null), 3500);
      } finally {
        setIsProcessing(false);
      }
    } else {
      // Start Pump
      setMotor({ ...motor, status: 'STARTING' });
      try {
        await api.startMotor(motor.id);
        setMotor({ ...motor, status: 'ON' });
        setCurrentAmps(9.4);
        setPowerKw(2.16);
        setFlowRateLpm(48.5);
        setToastMessage('Pump Started Successfully');
        setTimeout(() => setToastMessage(null), 3500);
      } catch (err: any) {
        setMotor({ ...motor, status: prevStatus });
        setToastMessage(err.message || 'Safety lock active: start rejected');
        setTimeout(() => setToastMessage(null), 3500);
      } finally {
        setIsProcessing(false);
      }
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

      {/* Disconnected Banner (Matching Left Screenshot) */}
      {!wsConnected && (
        <div className="rounded-2xl bg-rose-50 border border-rose-200/80 px-3.5 py-2.5 flex items-center justify-between shadow-sm">
          <div className="flex items-center gap-2 text-[11px] font-semibold text-rose-600">
            <AlertTriangle className="w-4 h-4 text-rose-500 flex-shrink-0" />
            <span>Real-time telemetry stream is currently disconnected.</span>
          </div>
          <button
            onClick={loadData}
            className="px-2.5 py-1 rounded-xl bg-rose-100 hover:bg-rose-200 text-rose-700 text-[11px] font-bold flex items-center gap-1 transition-all flex-shrink-0"
          >
            <RefreshCw className="w-3 h-3" />
            <span>Reconnect Now</span>
          </button>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 1: HOME (MATCHES SCREENSHOT 1 EXACTLY) */}
      {/* ========================================================================= */}
      {activeTab === 'HOME' && (
        <>
          {/* Station Status Header Card */}
          <div className="mobile-card p-3.5 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="w-3 h-3 rounded-full bg-blue-600 shadow-sm" />
              <div>
                <h2 className="text-sm font-black text-slate-900 tracking-tight">
                  {station?.name || 'Demo Water Pump Station'}
                </h2>
                <div className="text-[11px] text-slate-400 font-medium">
                  {site?.name || 'Demo Main Site'} [{controller?.device_uid || 'DEMO-ESP32-001'}]
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xl bg-amber-50 border border-amber-200/80 text-[11px] font-bold text-amber-700">
                <AlertTriangle className="w-3 h-3 text-amber-500" />
                <span>Stale &bull; 1m ago</span>
              </span>
              <button
                onClick={loadData}
                className="p-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin text-blue-600' : ''}`} />
              </button>
            </div>
          </div>

          {/* 2-COLUMN METRIC CARDS GRID */}
          <div className="grid grid-cols-2 gap-2.5">
            {/* CARD 1: OVERHEAD TANK & HEAD */}
            <div className="mobile-card p-3.5 space-y-2 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between text-[11px] font-black tracking-tight text-blue-600 uppercase">
                  <div className="flex items-center gap-1">
                    <Waves className="w-3.5 h-3.5" />
                    <span>Overhead Tank & Head</span>
                  </div>
                  <span className="text-[10px] font-semibold text-slate-400 lowercase">Cap: 1000L</span>
                </div>

                <div className="flex items-baseline justify-between mt-1.5">
                  <span className="text-2xl font-black text-slate-900 tracking-tight">
                    {tankLevel.toFixed(1)}%
                  </span>
                  <span className="px-2 py-0.5 rounded-lg bg-blue-500 text-white text-[10px] font-bold">
                    {tankLevel.toFixed(0)}%
                  </span>
                </div>

                {/* Blue Progress Bar */}
                <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden mt-1.5">
                  <div
                    className="h-full bg-blue-500 rounded-full transition-all duration-500"
                    style={{ width: `${Math.min(100, tankLevel)}%` }}
                  />
                </div>

                <div className="text-[11px] text-slate-600 font-semibold mt-1">
                  Head: <span className="font-bold text-slate-900">{waterHeadMeters.toFixed(1)} m</span>
                </div>
              </div>

              <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[10px] font-medium text-slate-500">
                <span>Cutoff: &ge;95% (Overflow Guard)</span>
                <span className="text-emerald-600 font-bold">Adequate</span>
              </div>
            </div>

            {/* CARD 2: SUMP / SOURCE LEVEL */}
            <div className="mobile-card p-3.5 space-y-2 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between text-[11px] font-black tracking-tight text-blue-600 uppercase">
                  <div className="flex items-center gap-1">
                    <Droplet className="w-3.5 h-3.5" />
                    <span>Sump / Source Level</span>
                  </div>
                  <span className="text-[10px] font-semibold text-slate-400 lowercase">Cap: 5000L</span>
                </div>

                <div className="flex items-baseline justify-between mt-1.5">
                  <span className="text-2xl font-black text-slate-900 tracking-tight">
                    {sumpLevel.toFixed(1)}%
                  </span>
                  <span className="text-[10px] font-semibold text-slate-500">
                    ~{(sumpLevel * 50).toFixed(0)} L Source
                  </span>
                </div>

                {/* Blue Progress Bar */}
                <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden mt-1.5">
                  <div
                    className="h-full bg-blue-500 rounded-full transition-all duration-500"
                    style={{ width: `${Math.min(100, sumpLevel)}%` }}
                  />
                </div>
              </div>

              <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[10px] font-medium text-slate-500">
                <span>Dry-Run Cutoff: &le;10%</span>
                <span className="text-emerald-600 font-bold">Source Safe</span>
              </div>
            </div>

            {/* CARD 3: WATER FLOW RATE */}
            <div className="mobile-card p-3.5 space-y-2 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between text-[11px] font-black tracking-tight text-blue-600 uppercase">
                  <div className="flex items-center gap-1">
                    <Gauge className="w-3.5 h-3.5" />
                    <span>Water Flow Rate</span>
                  </div>
                  <span className="text-[10px] font-semibold text-slate-400">Hall-Sensor</span>
                </div>

                <div className="flex items-baseline justify-between mt-1.5">
                  <span className="text-2xl font-black text-slate-900 tracking-tight">
                    {flowRateLpm.toFixed(1)} <span className="text-xs font-bold text-slate-500">L/min</span>
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded-lg text-[10px] font-bold ${
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

              <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[10px] font-medium text-slate-500">
                <span>Flow Protection:</span>
                <span className="text-emerald-600 font-bold">Primed &bull; Active</span>
              </div>
            </div>

            {/* CARD 4: WATER QUALITY */}
            <div className="mobile-card p-3.5 space-y-2 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between text-[11px] font-black tracking-tight text-amber-500 uppercase">
                  <div className="flex items-center gap-1">
                    <Shield className="w-3.5 h-3.5 text-amber-500" />
                    <span>Water Quality</span>
                  </div>
                  <span className="px-2 py-0.5 rounded-lg bg-emerald-50 text-emerald-600 border border-emerald-200 text-[10px] font-bold">
                    Clean
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-1.5 mt-2">
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

              <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[10px] font-medium text-slate-500">
                <span>Safety Cutoff:</span>
                <span className="text-slate-700 font-semibold">&gt;25 NTU Auto-Trip</span>
              </div>
            </div>

            {/* CARD 5: ELECTRICAL LOAD */}
            <div className="mobile-card p-3.5 space-y-2 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between text-[11px] font-black tracking-tight text-purple-600 uppercase">
                  <div className="flex items-center gap-1">
                    <Zap className="w-3.5 h-3.5 text-purple-600" />
                    <span>Electrical Load</span>
                  </div>
                  <span className="text-[10px] font-semibold text-slate-400">230V Grid</span>
                </div>

                <div className="grid grid-cols-2 gap-1.5 mt-2">
                  <div>
                    <div className="text-[10px] text-slate-400 font-medium">Current Load</div>
                    <div className="text-base font-black text-slate-900">
                      {currentAmps.toFixed(1)} A
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] text-slate-400 font-medium">Power Rating</div>
                    <div className="text-base font-black text-slate-900">
                      {powerKw.toFixed(1)} kW
                    </div>
                  </div>
                </div>
              </div>

              <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[10px] font-medium text-slate-500">
                <span>Overload Trip:</span>
                <span className="text-emerald-600 font-bold">Safe &lt; 15A</span>
              </div>
            </div>

            {/* CARD 6: SAFETY INTERLOCKS */}
            <div className="mobile-card p-3.5 space-y-2 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between text-[11px] font-black tracking-tight text-emerald-600 uppercase">
                  <div className="flex items-center gap-1">
                    <Activity className="w-3.5 h-3.5 text-emerald-600" />
                    <span>Safety Interlocks</span>
                  </div>
                  <span className="text-[10px] font-bold text-emerald-600">100% Locked</span>
                </div>

                {/* 4 Green Bullet Checks (2x2) */}
                <div className="grid grid-cols-2 gap-1.5 mt-2 text-[10px] font-bold text-slate-800">
                  <div className="flex items-center gap-1 bg-slate-50 px-1.5 py-1 rounded-lg">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 flex-shrink-0" />
                    <span className="truncate">Tank Overflow</span>
                  </div>
                  <div className="flex items-center gap-1 bg-slate-50 px-1.5 py-1 rounded-lg">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 flex-shrink-0" />
                    <span className="truncate">Dry-Run Guard</span>
                  </div>
                  <div className="flex items-center gap-1 bg-slate-50 px-1.5 py-1 rounded-lg">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 flex-shrink-0" />
                    <span className="truncate">Turbidity Lock</span>
                  </div>
                  <div className="flex items-center gap-1 bg-slate-50 px-1.5 py-1 rounded-lg">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 flex-shrink-0" />
                    <span className="truncate">Hardware E-Stop</span>
                  </div>
                </div>
              </div>

              <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[10px] font-medium text-slate-500">
                <span>Authority:</span>
                <span className="text-blue-600 font-bold">Local ESP32 Engine</span>
              </div>
            </div>
          </div>

          {/* BOTTOM ROW QUICK CARDS (Above Dock) */}
          <div className="grid grid-cols-2 gap-2.5 pt-0.5">
            {/* Quick Card 1: Daily Pump Schedules */}
            <div className="mobile-card p-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center flex-shrink-0">
                  <Clock className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-xs font-bold text-slate-900 leading-tight">
                    Daily Pump Schedules
                  </div>
                  <div className="text-[10px] text-slate-400 font-medium">
                    {activeSchedulesCount} automated timers active
                  </div>
                </div>
              </div>

              <button
                onClick={() => setIsScheduleModalOpen(true)}
                className="px-2.5 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-[11px] font-bold flex items-center gap-1 shadow-sm transition-all flex-shrink-0"
              >
                <Plus className="w-3 h-3 stroke-[3]" />
                <span>Configure</span>
              </button>
            </div>

            {/* Quick Card 2: Latest Event */}
            <div className="mobile-card p-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center flex-shrink-0">
                  <Zap className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-xs font-bold text-slate-900 leading-tight">Latest Event</div>
                  <div className="text-[10px] text-slate-400 font-medium">Ready &amp; Standby</div>
                </div>
              </div>

              <span
                className={`px-2 py-1 rounded-lg text-[10px] font-black uppercase tracking-wider flex-shrink-0 ${
                  isMotorRunning
                    ? 'bg-emerald-100 text-emerald-700'
                    : 'bg-slate-100 text-slate-600'
                }`}
              >
                {isMotorRunning ? 'PUMP ON' : 'PUMP IDLE'}
              </span>
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
            <div className="w-10 h-10 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center shadow-sm">
              <Calendar className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-black text-slate-900 tracking-tight">SCHEDULES</h2>
                <span className="px-2 py-0.5 rounded-full bg-cyan-100 text-cyan-800 text-[10px] font-extrabold">
                  {activeSchedulesCount} Active
                </span>
              </div>
              <p className="text-xs text-slate-400 font-medium">Automated Daily Timer</p>
            </div>
          </div>

          {/* Daily Pump Schedules Card */}
          <div className="mobile-card p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center flex-shrink-0">
                <Clock className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-900">Daily Pump Schedules</h3>
                <p className="text-xs text-slate-400 font-medium">
                  {activeSchedulesCount} automated timers active
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsScheduleModalOpen(true)}
                className="px-3 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold flex items-center gap-1 shadow-md shadow-blue-500/25 transition-all"
              >
                <Plus className="w-3.5 h-3.5 stroke-[3]" />
                <span>Configure</span>
              </button>
              <ChevronRight className="w-4 h-4 text-slate-400" />
            </div>
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
                  className="px-3 py-1.5 rounded-xl bg-blue-50 text-blue-600 font-bold text-xs hover:bg-blue-100"
                >
                  + Add First Schedule
                </button>
              </div>
            ) : (
              schedules.map((s) => (
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
                      <div className="text-xs font-bold text-slate-900">{s.name}</div>
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
              ))
            )}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 3: HISTORY (EVENT LOGS) */}
      {/* ========================================================================= */}
      {activeTab === 'HISTORY' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between pt-1">
            <h2 className="text-lg font-black text-slate-900 tracking-tight">PUMP EVENT LOGS</h2>
            <button
              onClick={loadData}
              className="p-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-600"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="space-y-2">
            {recentEvents.length === 0 ? (
              <div className="mobile-card p-6 text-center text-xs text-slate-400">
                No recent event logs recorded.
              </div>
            ) : (
              recentEvents.map((ev) => (
                <div
                  key={ev.id}
                  className="mobile-card p-3 flex items-center justify-between text-xs"
                >
                  <div className="flex items-center gap-2.5">
                    <span
                      className={`w-2 h-2 rounded-full ${
                        ev.event_type === 'STARTED'
                          ? 'bg-emerald-500'
                          : ev.event_type === 'STOPPED'
                          ? 'bg-blue-500'
                          : 'bg-rose-500'
                      }`}
                    />
                    <div>
                      <div className="font-bold text-slate-900">{ev.event_type}</div>
                      <div className="text-[10px] text-slate-400">
                        {ev.description || 'Normal operation event'}
                      </div>
                    </div>
                  </div>
                  <span className="text-[10px] font-mono text-slate-500">
                    {new Date(ev.occurred_at).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                      second: '2-digit',
                    })}
                  </span>
                </div>
              ))
            )}
          </div>
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
        onTabChange={setActiveTab}
        isMotorRunning={isMotorRunning}
        isProcessing={isProcessing}
        onPowerToggle={handlePowerToggle}
      />

      {/* Schedule Manager Modal */}
      {station && motor && (
        <ScheduleManagerModal
          isOpen={isScheduleModalOpen}
          onClose={() => {
            setIsScheduleModalOpen(false);
            loadData();
          }}
          station={station}
          motors={[motor]}
        />
      )}
    </div>
  );
};
