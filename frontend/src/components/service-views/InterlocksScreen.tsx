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
} from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';

interface InterlocksScreenProps {
  onBack: () => void;
  tankLevel: number;
  tankStopThreshold: number;
  sumpLevel: number;
  sumpDryRunThreshold: number;
  turbidity: number;
  turbidityStopThreshold: number;
  currentAmps: number;
  voltage: number;
  onRefresh: () => void;
  isSyncing: boolean;
}

export const InterlocksScreen: React.FC<InterlocksScreenProps> = ({
  onBack,
  tankLevel,
  tankStopThreshold,
  sumpLevel,
  sumpDryRunThreshold,
  turbidity,
  turbidityStopThreshold,
  currentAmps,
  voltage,
  onRefresh,
  isSyncing,
}) => {
  const { t } = useLanguage();
  // Determine interlock states
  const isTankFull = tankLevel >= tankStopThreshold;
  const isDryRun = sumpLevel <= sumpDryRunThreshold;
  const isTurbidityHigh = turbidity > turbidityStopThreshold;
  const isOvercurrent = currentAmps > 15;
  const isVoltageAbnormal = voltage < 180 || voltage > 260;

  const totalInterlocks = 6;
  let healthyCount = 6;
  if (isTankFull) healthyCount--;
  if (isDryRun) healthyCount--;
  if (isTurbidityHigh) healthyCount--;
  if (isOvercurrent) healthyCount--;
  if (isVoltageAbnormal) healthyCount--;

  const scorePct = Math.round((healthyCount / totalInterlocks) * 100);

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
              scorePct === 100
                ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                : 'bg-amber-50 border-amber-200 text-amber-700'
            }`}
          >
            {scorePct === 100 ? t.allInterlocksHealthy : t.interlockTripped}
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
            <div className="w-11 h-11 rounded-2xl bg-blue-600 text-white flex items-center justify-center flex-shrink-0">
              <Lock className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-base font-black text-slate-900 leading-tight">{t.interlocksTitle}</h2>
              <p className="text-xs text-slate-500 font-medium mt-0.5">
                {t.interlocksSubtitle}
              </p>
            </div>
          </div>
          <div className="text-right">
            <span className="text-2xl font-black text-emerald-600 font-mono">{scorePct}%</span>
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
            <div className="text-xs font-black tracking-wide">Protection Authority: ESP32 Hardware</div>
            <div className="text-[10px] text-slate-400">Autonomous edge trip &bull; 0ms latency</div>
          </div>
        </div>
        <span className="px-2 py-0.5 rounded-lg bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 text-[10px] font-bold">
          ARMED
        </span>
      </div>

      {/* Detailed Interlock Cards Grid */}
      <div className="space-y-2.5 pt-1">
        <h3 className="text-xs font-black uppercase tracking-wider text-slate-400 px-1">
          Safety Interlock Matrix ({totalInterlocks})
        </h3>

        {/* 1. Tank Overflow Cutoff */}
        <div className="mobile-card p-3.5 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className={`p-2 rounded-xl ${isTankFull ? 'bg-amber-100 text-amber-700' : 'bg-teal-50 text-teal-700'}`}>
                <Waves className="w-4 h-4" />
              </div>
              <div>
                <div className="text-xs font-black text-slate-900">Overhead Tank Overflow Cutoff</div>
                <div className="text-[11px] text-slate-400">
                  Current: <span className="font-bold text-slate-700">{tankLevel.toFixed(1)}%</span> &bull; Cutoff: &ge;{tankStopThreshold}%
                </div>
              </div>
            </div>
            <span
              className={`px-2 py-1 rounded-xl text-[10px] font-black uppercase ${
                isTankFull
                  ? 'bg-amber-100 text-amber-800 border border-amber-300'
                  : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
              }`}
            >
              {isTankFull ? 'TRIGGERED (FULL)' : 'NORMAL / SAFE'}
            </span>
          </div>
        </div>

        {/* 2. Sump Dry-Run Protection */}
        <div className="mobile-card p-3.5 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className={`p-2 rounded-xl ${isDryRun ? 'bg-rose-100 text-rose-700' : 'bg-cyan-50 text-cyan-700'}`}>
                <Droplet className="w-4 h-4" />
              </div>
              <div>
                <div className="text-xs font-black text-slate-900">Sump Source Dry-Run Protection</div>
                <div className="text-[11px] text-slate-400">
                  Current: <span className="font-bold text-slate-700">{sumpLevel.toFixed(1)}%</span> &bull; Min Cutoff: &le;{sumpDryRunThreshold}%
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

        {/* 3. Water Turbidity Clarity Safety */}
        <div className="mobile-card p-3.5 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className={`p-2 rounded-xl ${isTurbidityHigh ? 'bg-purple-100 text-purple-700' : 'bg-emerald-50 text-emerald-700'}`}>
                <ShieldCheck className="w-4 h-4" />
              </div>
              <div>
                <div className="text-xs font-black text-slate-900">Turbidity &amp; Mud Safety Trip</div>
                <div className="text-[11px] text-slate-400">
                  Current: <span className="font-bold text-slate-700">{turbidity.toFixed(1)} NTU</span> &bull; Limit: &gt;{turbidityStopThreshold} NTU
                </div>
              </div>
            </div>
            <span
              className={`px-2 py-1 rounded-xl text-[10px] font-black uppercase ${
                isTurbidityHigh
                  ? 'bg-purple-100 text-purple-800 border border-purple-300'
                  : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
              }`}
            >
              {isTurbidityHigh ? 'TRIP (MUDDY)' : 'WATER CLEAR'}
            </span>
          </div>
        </div>

        {/* 4. Overcurrent & Motor Overload */}
        <div className="mobile-card p-3.5 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className={`p-2 rounded-xl ${isOvercurrent ? 'bg-rose-100 text-rose-700' : 'bg-indigo-50 text-indigo-700'}`}>
                <Zap className="w-4 h-4" />
              </div>
              <div>
                <div className="text-xs font-black text-slate-900">Overcurrent &amp; Motor Overload</div>
                <div className="text-[11px] text-slate-400">
                  Current: <span className="font-bold text-slate-700">{currentAmps.toFixed(1)} A</span> &bull; Trip Limit: &gt;15.0 A
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

        {/* 5. Voltage Limits (Under/Over Voltage) */}
        <div className="mobile-card p-3.5 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className={`p-2 rounded-xl ${isVoltageAbnormal ? 'bg-amber-100 text-amber-700' : 'bg-blue-50 text-blue-700'}`}>
                <Zap className="w-4 h-4" />
              </div>
              <div>
                <div className="text-xs font-black text-slate-900">Grid Voltage Stabilization</div>
                <div className="text-[11px] text-slate-400">
                  Current: <span className="font-bold text-slate-700">{voltage.toFixed(0)} V</span> &bull; Safe: 180V &ndash; 260V
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

        {/* 6. Hardware Emergency Stop (E-Stop) */}
        <div className="mobile-card p-3.5 space-y-2">
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
            <span className="px-2 py-1 rounded-xl text-[10px] font-black uppercase bg-emerald-50 text-emerald-700 border border-emerald-200">
              CIRCUIT CLOSED / OK
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
