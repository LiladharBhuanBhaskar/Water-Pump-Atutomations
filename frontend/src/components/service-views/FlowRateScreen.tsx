import React from 'react';
import {
  ArrowLeft,
  Gauge,
  RefreshCw,
  Droplets,
} from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';

interface FlowRateScreenProps {
  onBack: () => void;
  flowRateLpm: number;
  isMotorRunning: boolean;
  onRefresh: () => void;
  isSyncing: boolean;
}

export const FlowRateScreen: React.FC<FlowRateScreenProps> = ({
  onBack,
  flowRateLpm,
  isMotorRunning,
  onRefresh,
  isSyncing,
}) => {
  const { t, language } = useLanguage();
  const m3PerHour = (flowRateLpm * 0.06).toFixed(2);
  const isFlowing = flowRateLpm > 0.5;

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
              isFlowing
                ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                : isMotorRunning
                ? 'bg-amber-50 border-amber-200 text-amber-700'
                : 'bg-slate-100 border-slate-200 text-slate-600'
            }`}
          >
            {isFlowing
              ? t.flowActive
              : isMotorRunning
              ? (language === 'hi' ? 'मोटर चालू • प्रवाह नहीं' : 'PUMP ON • NO FLOW')
              : t.flowStatic}
          </span>
          <button
            type="button"
            onClick={onRefresh}
            className="p-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors cursor-pointer"
            title="Refresh Flow Rate"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin text-blue-600' : ''}`} />
          </button>
        </div>
      </div>

      {/* Main Flow Banner */}
      <div className="mobile-card p-5 bg-white border border-slate-200 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-2xl bg-blue-600 text-white flex items-center justify-center flex-shrink-0">
              <Gauge className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-base font-black text-slate-900 leading-tight">{t.flowTitle}</h2>
              <p className="text-xs text-slate-500 font-medium mt-0.5">
                {t.flowSubtitle}
              </p>
            </div>
          </div>
        </div>

        {/* Big Flow Value Card */}
        <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 flex items-center justify-between">
          <div>
            <div className="text-[10px] font-black uppercase tracking-wider text-slate-400">{t.currentDischarge}</div>
            <div className="text-3xl font-black text-slate-900 tracking-tight font-mono mt-0.5 flex items-baseline gap-1.5">
              <span>{flowRateLpm.toFixed(1)}</span>
              <span className="text-sm font-bold text-slate-400">L/min</span>
            </div>
            <div className="text-xs font-bold text-blue-700 mt-0.5">
              &asymp; {m3PerHour} m&sup3; per hour
            </div>
          </div>

          <div
            className={`w-16 h-16 rounded-2xl flex items-center justify-center ${
              isFlowing
                ? 'bg-emerald-100 text-emerald-600 animate-pulse'
                : 'bg-slate-200 text-slate-500'
            }`}
          >
            <Droplets className="w-8 h-8" />
          </div>
        </div>

        {/* Gauge Bar */}
        <div className="space-y-1.5">
          <div className="flex justify-between text-[11px] text-slate-500 font-semibold">
            <span>Flow Capacity (0 &ndash; 120 LPM)</span>
            <span className="font-mono text-blue-800 font-bold">{Math.round((flowRateLpm / 120) * 100)}% Rated</span>
          </div>
          <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-600 rounded-full transition-all duration-500"
              style={{ width: `${Math.min(100, (flowRateLpm / 120) * 100)}%` }}
            />
          </div>
        </div>

        {/* 3 Metrics */}
        <div className="grid grid-cols-3 gap-2 text-center pt-1">
          <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200">
            <div className="text-[10px] text-slate-400 font-bold uppercase">Discharge m&sup3;/h</div>
            <div className="text-xs font-black text-slate-900 font-mono mt-0.5">
              {m3PerHour}
            </div>
          </div>
          <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200">
            <div className="text-[10px] text-slate-400 font-bold uppercase">Pipe Primed</div>
            <div className="text-xs font-black text-emerald-700 mt-0.5">
              100% OK
            </div>
          </div>
          <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200">
            <div className="text-[10px] text-slate-400 font-bold uppercase">Dry Pipe Trip</div>
            <div className="text-xs font-black text-blue-700 mt-0.5">
              Armed
            </div>
          </div>
        </div>
      </div>

      {/* Diagnostics Card */}
      <div className="mobile-card p-4 space-y-3">
        <h3 className="text-xs font-black uppercase tracking-wider text-slate-400 px-1">
          Flow Sensor Diagnostics
        </h3>

        <div className="space-y-2 text-xs">
          <div className="p-3 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-between">
            <span className="font-semibold text-slate-700">Pulse Flow Meter (Hall Effect)</span>
            <span className="font-bold text-emerald-600">Active (Pin #14)</span>
          </div>
          <div className="p-3 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-between">
            <span className="font-semibold text-slate-700">Cavitation / Air-Lock Guard</span>
            <span className="font-bold text-emerald-600">Normal</span>
          </div>
        </div>
      </div>
    </div>
  );
};
