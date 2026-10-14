import React from 'react';
import {
  ArrowLeft,
  Shield,
  ShieldCheck,
  Zap,
  Droplet,
  Waves,
  RefreshCw,
  Cpu,
  Lock,
  CheckCircle2,
  Info,
} from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';

interface InterlocksScreenProps {
  onBack: () => void;
  tankLevel: number;
  tankStopThreshold: number;
  autoStopTankFull?: boolean;
  onToggleAutoStopTankFull?: (val: boolean) => void;
  sumpLevel: number;
  sumpDryRunThreshold: number;
  turbidity: number;
  turbidityStopThreshold: number;
  autoStopTurbidity?: boolean;
  onToggleAutoStopTurbidity?: (val: boolean) => void;
  currentAmps: number;
  voltage: number;
  onRefresh: () => void;
  isSyncing: boolean;
}

export const InterlocksScreen: React.FC<InterlocksScreenProps> = ({
  onBack,
  tankLevel,
  tankStopThreshold,
  autoStopTankFull = true,
  onToggleAutoStopTankFull,
  sumpLevel,
  sumpDryRunThreshold,
  turbidity,
  turbidityStopThreshold,
  autoStopTurbidity = true,
  onToggleAutoStopTurbidity,
  currentAmps,
  voltage,
  onRefresh,
  isSyncing,
}) => {
  const { t } = useLanguage();

  // Operational Process Cutoffs (Normal Standby Auto-Stop, NOT Hardware Faults)
  const isTankFull = tankLevel >= tankStopThreshold;
  const isTurbidityHigh = turbidity > turbidityStopThreshold;

  // Critical Hardware / Electrical Faults (Trips and Latches)
  const isDryRun = sumpLevel <= sumpDryRunThreshold;
  const isOvercurrent = currentAmps > 15;
  const isVoltageAbnormal = voltage < 180 || voltage > 260;

  const totalHardwareFaults = 4; // Dry run, Overcurrent, Voltage, E-Stop
  let hardwareHealthyCount = totalHardwareFaults;
  if (isDryRun) hardwareHealthyCount--;
  if (isOvercurrent) hardwareHealthyCount--;
  if (isVoltageAbnormal) hardwareHealthyCount--;

  const hasHardwareFault = hardwareHealthyCount < totalHardwareFaults;
  const hasOperationalCutoff = isTankFull || isTurbidityHigh;

  const healthScorePct = Math.round(
    ((hardwareHealthyCount + (!isTankFull ? 1 : 0) + (!isTurbidityHigh ? 1 : 0)) / 6) * 100
  );

  return (
    <div className="space-y-4 animate-fade-in font-sans pb-dock-clearance">
      {/* Top Header Bar */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-100">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-all cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>{t.backToHome}</span>
        </button>

        <div className="flex items-center gap-2">
          <span
            className={`px-2.5 py-1 rounded-xl text-[11px] font-black border ${
              hasHardwareFault
                ? 'bg-rose-50 border-rose-200 text-rose-700 animate-pulse'
                : hasOperationalCutoff
                ? 'bg-teal-50 border-teal-200 text-teal-800'
                : 'bg-emerald-50 border-emerald-200 text-emerald-700'
            }`}
          >
            {hasHardwareFault
              ? 'HARDWARE FAULT LATCHED'
              : hasOperationalCutoff
              ? 'OPERATIONAL STANDBY (NON-FAULT)'
              : t.allInterlocksHealthy}
          </span>
          <button
            type="button"
            onClick={onRefresh}
            className="p-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors cursor-pointer"
            title="Refresh Interlocks"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin text-blue-600' : ''}`} />
          </button>
        </div>
      </div>

      {/* Hero Overview */}
      <div className="mobile-card p-4 bg-white border border-slate-200 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className={`w-11 h-11 rounded-2xl flex items-center justify-center flex-shrink-0 text-white ${
                hasHardwareFault
                  ? 'bg-rose-600'
                  : hasOperationalCutoff
                  ? 'bg-teal-600'
                  : 'bg-blue-600'
              }`}
            >
              <Lock className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-base font-black text-slate-900 leading-tight">
                {t.interlocksTitle}
              </h2>
              <p className="text-xs text-slate-500 font-medium mt-0.5">
                Separating non-fault process auto-stops from physical hardware faults
              </p>
            </div>
          </div>
          <div className="text-right">
            <span
              className={`text-2xl font-black font-mono ${
                hasHardwareFault
                  ? 'text-rose-600'
                  : hasOperationalCutoff
                  ? 'text-teal-600'
                  : 'text-emerald-600'
              }`}
            >
              {healthScorePct}%
            </span>
            <div className="text-[10px] font-bold text-slate-400 uppercase">Health</div>
          </div>
        </div>
      </div>

      {/* Local Controller Authority Banner */}
      <div className="p-3 rounded-2xl bg-slate-900 text-white flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-blue-500/20 text-blue-300 flex items-center justify-center">
            <Cpu className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs font-black tracking-wide">Protection Authority: ESP32 Edge</div>
            <div className="text-[10px] text-slate-400">Autonomous cutoff &bull; 0ms latency</div>
          </div>
        </div>
        <span className="px-2 py-0.5 rounded-lg bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 text-[10px] font-bold">
          ARMED
        </span>
      </div>

      {/* SECTION 1: OPERATIONAL AUTO-STOP CUTOFFS (NON-FAULT OPTIONS) */}
      <div className="space-y-2.5 pt-1">
        <div className="flex items-center justify-between px-1">
          <div className="flex items-center gap-1.5">
            <Waves className="w-3.5 h-3.5 text-teal-600" />
            <h3 className="text-xs font-black uppercase tracking-wider text-slate-700">
              Operational Auto-Cutoff Options (Non-Fault)
            </h3>
          </div>
          <span className="text-[10px] font-black uppercase text-teal-700 bg-teal-50 px-2 py-0.5 rounded-lg border border-teal-200">
            2 Options Configurable
          </span>
        </div>

        {/* Option 1: Overhead Tank Overflow Cutoff */}
        <div className="mobile-card p-3.5 space-y-2 border-l-4 border-l-teal-500">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-start gap-2.5">
              <div
                className={`p-2 rounded-xl mt-0.5 ${
                  isTankFull ? 'bg-teal-100 text-teal-800' : 'bg-teal-50 text-teal-700'
                }`}
              >
                <Waves className="w-4 h-4" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-black text-slate-900">
                    1. Overhead Tank Overflow Cutoff
                  </span>
                  <span className="px-1.5 py-0.2 rounded text-[9px] font-extrabold bg-teal-100 text-teal-800 border border-teal-300">
                    NON-FAULT STANDBY
                  </span>
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  Current: <span className="font-bold text-slate-800">{tankLevel.toFixed(1)}%</span>{' '}
                  &bull; Cutoff Threshold: &ge;{tankStopThreshold}%
                </div>
              </div>
            </div>

            <div className="flex flex-col items-end gap-1">
              <span
                className={`px-2 py-0.5 rounded-xl text-[10px] font-black uppercase border ${
                  isTankFull
                    ? 'bg-teal-100 text-teal-900 border-teal-300'
                    : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                }`}
              >
                {isTankFull ? 'AUTO-STOPPED (TANK FULL)' : 'LEVEL SAFE (STANDBY OK)'}
              </span>
              {onToggleAutoStopTankFull && (
                <button
                  type="button"
                  onClick={() => onToggleAutoStopTankFull(!autoStopTankFull)}
                  className={`text-[10px] font-bold px-2 py-0.5 rounded-md transition-colors cursor-pointer border ${
                    autoStopTankFull
                      ? 'bg-slate-100 text-slate-700 border-slate-200 hover:bg-slate-200'
                      : 'bg-slate-200 text-slate-400 border-slate-300'
                  }`}
                >
                  {autoStopTankFull ? 'Option: ENABLED' : 'Option: DISABLED'}
                </button>
              )}
            </div>
          </div>

          <div className="text-[11px] text-slate-500 bg-slate-50 p-2 rounded-xl border border-slate-100 flex items-center gap-1.5">
            <Info className="w-3.5 h-3.5 text-teal-600 shrink-0" />
            <span>
              {isTankFull
                ? 'Tank filled to capacity. Motor is stopped into ready standby and will run normally when water level drops. Never latches a fault.'
                : 'When water reaches the threshold, the pump stops safely without latching a motor fault.'}
            </span>
          </div>
        </div>

        {/* Option 2: Water Clarity & Turbidity Cutoff */}
        <div className="mobile-card p-3.5 space-y-2 border-l-4 border-l-purple-500">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-start gap-2.5">
              <div
                className={`p-2 rounded-xl mt-0.5 ${
                  isTurbidityHigh ? 'bg-purple-100 text-purple-800' : 'bg-emerald-50 text-emerald-700'
                }`}
              >
                <ShieldCheck className="w-4 h-4" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-black text-slate-900">
                    2. Water Clarity &amp; Turbidity Cutoff
                  </span>
                  <span className="px-1.5 py-0.2 rounded text-[9px] font-extrabold bg-purple-100 text-purple-800 border border-purple-300">
                    NON-FAULT QUALITY PAUSE
                  </span>
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  Current: <span className="font-bold text-slate-800">{turbidity.toFixed(1)} NTU</span>{' '}
                  &bull; Max Limit: &gt;{turbidityStopThreshold} NTU
                </div>
              </div>
            </div>

            <div className="flex flex-col items-end gap-1">
              <span
                className={`px-2 py-0.5 rounded-xl text-[10px] font-black uppercase border ${
                  isTurbidityHigh
                    ? 'bg-purple-100 text-purple-900 border-purple-300'
                    : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                }`}
              >
                {isTurbidityHigh ? 'AUTO-CUTOFF (MUDDY WATER)' : 'WATER CLEAR (READY)'}
              </span>
              {onToggleAutoStopTurbidity && (
                <button
                  type="button"
                  onClick={() => onToggleAutoStopTurbidity(!autoStopTurbidity)}
                  className={`text-[10px] font-bold px-2 py-0.5 rounded-md transition-colors cursor-pointer border ${
                    autoStopTurbidity
                      ? 'bg-slate-100 text-slate-700 border-slate-200 hover:bg-slate-200'
                      : 'bg-slate-200 text-slate-400 border-slate-300'
                  }`}
                >
                  {autoStopTurbidity ? 'Option: ENABLED' : 'Option: DISABLED'}
                </button>
              )}
            </div>
          </div>

          <div className="text-[11px] text-slate-500 bg-slate-50 p-2 rounded-xl border border-slate-100 flex items-center gap-1.5">
            <Info className="w-3.5 h-3.5 text-purple-600 shrink-0" />
            <span>
              {isTurbidityHigh
                ? 'Source water is muddy or contaminated. Pumping is paused to protect drinking/overhead water. Standby resumes when water clarifies. Not a hardware motor fault.'
                : 'Protects overhead reservoir from pumping muddy water. Automatically pauses pumping into standby without fault latching.'}
            </span>
          </div>
        </div>
      </div>

      {/* SECTION 2: CRITICAL MOTOR & ELECTRICAL FAULT LATCHES */}
      <div className="space-y-2.5 pt-2">
        <div className="flex items-center justify-between px-1">
          <div className="flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5 text-rose-600" />
            <h3 className="text-xs font-black uppercase tracking-wider text-slate-700">
              Critical Motor &amp; Electrical Fault Latches
            </h3>
          </div>
          <span className="text-[10px] font-black uppercase text-rose-700 bg-rose-50 px-2 py-0.5 rounded-lg border border-rose-200">
            Hardware Protection
          </span>
        </div>

        {/* 1. Sump Dry-Run Protection */}
        <div className="mobile-card p-3.5 space-y-2 border-l-4 border-l-rose-500">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div
                className={`p-2 rounded-xl ${
                  isDryRun ? 'bg-rose-100 text-rose-700' : 'bg-cyan-50 text-cyan-700'
                }`}
              >
                <Droplet className="w-4 h-4" />
              </div>
              <div>
                <div className="text-xs font-black text-slate-900">
                  Sump Source Dry-Run Protection
                </div>
                <div className="text-[11px] text-slate-400">
                  Current: <span className="font-bold text-slate-700">{sumpLevel.toFixed(1)}%</span>{' '}
                  &bull; Min Cutoff: &le;{sumpDryRunThreshold}%
                </div>
              </div>
            </div>
            <span
              className={`px-2 py-1 rounded-xl text-[10px] font-black uppercase ${
                isDryRun
                  ? 'bg-rose-100 text-rose-800 border border-rose-300'
                  : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
              }`}
            >
              {isDryRun ? 'TRIPPED (DRY)' : 'SOURCE OK'}
            </span>
          </div>
        </div>

        {/* 2. Overcurrent & Motor Overload */}
        <div className="mobile-card p-3.5 space-y-2 border-l-4 border-l-rose-500">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div
                className={`p-2 rounded-xl ${
                  isOvercurrent ? 'bg-rose-100 text-rose-700' : 'bg-indigo-50 text-indigo-700'
                }`}
              >
                <Zap className="w-4 h-4" />
              </div>
              <div>
                <div className="text-xs font-black text-slate-900">
                  Overcurrent &amp; Motor Overload
                </div>
                <div className="text-[11px] text-slate-400">
                  Current:{' '}
                  <span className="font-bold text-slate-700">{currentAmps.toFixed(1)} A</span>{' '}
                  &bull; Trip Limit: &gt;15.0 A
                </div>
              </div>
            </div>
            <span
              className={`px-2 py-1 rounded-xl text-[10px] font-black uppercase ${
                isOvercurrent
                  ? 'bg-rose-100 text-rose-800 border border-rose-300'
                  : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
              }`}
            >
              {isOvercurrent ? 'OVERLOAD TRIP' : 'LOAD SAFE'}
            </span>
          </div>
        </div>

        {/* 3. Voltage Limits (Under/Over Voltage) */}
        <div className="mobile-card p-3.5 space-y-2 border-l-4 border-l-rose-500">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div
                className={`p-2 rounded-xl ${
                  isVoltageAbnormal ? 'bg-amber-100 text-amber-700' : 'bg-blue-50 text-blue-700'
                }`}
              >
                <Zap className="w-4 h-4" />
              </div>
              <div>
                <div className="text-xs font-black text-slate-900">Grid Voltage Stabilization</div>
                <div className="text-[11px] text-slate-400">
                  Current:{' '}
                  <span className="font-bold text-slate-700">{voltage.toFixed(0)} V</span> &bull;
                  Safe: 180V &ndash; 260V
                </div>
              </div>
            </div>
            <span
              className={`px-2 py-1 rounded-xl text-[10px] font-black uppercase ${
                isVoltageAbnormal
                  ? 'bg-amber-100 text-amber-800 border border-amber-300'
                  : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
              }`}
            >
              {isVoltageAbnormal ? 'GRID FAULT' : 'GRID STABLE'}
            </span>
          </div>
        </div>

        {/* 4. Hardware Emergency Stop (E-Stop) */}
        <div className="mobile-card p-3.5 space-y-2 border-l-4 border-l-rose-500">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-xl bg-emerald-50 text-emerald-700">
                <Shield className="w-4 h-4" />
              </div>
              <div>
                <div className="text-xs font-black text-slate-900">Local Physical E-Stop Circuit</div>
                <div className="text-[11px] text-slate-400">
                  Panel safety loop &bull; Normally Closed (NC) healthy
                </div>
              </div>
            </div>
            <span className="px-2 py-1 rounded-xl text-[10px] font-black uppercase bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3 text-emerald-600" /> CIRCUIT CLOSED / OK
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
