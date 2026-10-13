import React from 'react';
import {
  ArrowLeft,
  Zap,
  RefreshCw,
} from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';

interface ElectricalLoadScreenProps {
  onBack: () => void;
  currentAmps: number;
  voltage: number;
  powerKw: number;
  isMotorRunning: boolean;
  onRefresh: () => void;
  isSyncing: boolean;
}

export const ElectricalLoadScreen: React.FC<ElectricalLoadScreenProps> = ({
  onBack,
  currentAmps,
  voltage,
  powerKw,
  isMotorRunning,
  onRefresh,
  isSyncing,
}) => {
  const { t, language } = useLanguage();
  const isOverload = currentAmps > 15;
  const isVoltageNormal = voltage >= 180 && voltage <= 260;
  const loadPct = Math.min(100, Math.round((currentAmps / 15) * 100));

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
              !isMotorRunning
                ? 'bg-slate-100 border-slate-200 text-slate-600'
                : isOverload
                ? 'bg-rose-50 border-rose-200 text-rose-700'
                : 'bg-blue-50 border-blue-200 text-blue-700'
            }`}
          >
            {!isMotorRunning
              ? (language === 'hi' ? 'मोटर बंद है' : 'STANDBY')
              : isOverload
              ? t.loadWarning
              : t.operatingNormal}
          </span>
          <button
            type="button"
            onClick={onRefresh}
            className="p-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors cursor-pointer"
            title="Refresh Electrical Load"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin text-blue-600' : ''}`} />
          </button>
        </div>
      </div>

      {/* Hero Card */}
      <div className="mobile-card p-5 bg-white border border-slate-200 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-2xl bg-blue-600 text-white flex items-center justify-center flex-shrink-0">
              <Zap className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-base font-black text-slate-900 leading-tight">{t.electricalTitle}</h2>
              <p className="text-xs text-slate-500 font-medium mt-0.5">
                {t.electricalSubtitle}
              </p>
            </div>
          </div>
          <span className="px-2.5 py-1 rounded-xl bg-blue-50 border border-blue-200 text-xs font-black text-blue-900">
            230V 1-Phase
          </span>
        </div>

        {/* 4 Metrics Grid */}
        <div className="grid grid-cols-2 gap-2.5">
          {/* Current */}
          <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 space-y-1">
            <div className="text-[10px] font-black uppercase tracking-wider text-slate-400">{t.motorCurrent}</div>
            <div className="text-2xl font-black text-slate-900 font-mono">
              {currentAmps.toFixed(1)} <span className="text-xs text-slate-400 font-normal">A</span>
            </div>
            <div className="text-[10px] font-bold text-slate-500">Trip at &gt;15.0 A</div>
          </div>

          {/* Voltage */}
          <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 space-y-1">
            <div className="text-[10px] font-black uppercase tracking-wider text-slate-400">{t.lineVoltage}</div>
            <div className="text-2xl font-black text-slate-900 font-mono">
              {voltage.toFixed(0)} <span className="text-xs text-slate-400 font-normal">V</span>
            </div>
            <div className="text-[10px] font-bold text-emerald-600">
              {isVoltageNormal ? '✓ Stable Range' : 'Abnormal Grid'}
            </div>
          </div>

          {/* Power kW */}
          <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 space-y-1">
            <div className="text-[10px] font-black uppercase tracking-wider text-slate-400">{t.activePowerKw}</div>
            <div className="text-2xl font-black text-slate-900 font-mono">
              {powerKw.toFixed(2)} <span className="text-xs text-slate-400 font-normal">kW</span>
            </div>
            <div className="text-[10px] font-bold text-blue-700">{t.powerFactor}: 0.85</div>
          </div>

          {/* Thermal Load */}
          <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 space-y-1">
            <div className="text-[10px] font-black uppercase tracking-wider text-slate-400">Thermal Load</div>
            <div className="text-2xl font-black text-slate-900 font-mono">
              {loadPct}%
            </div>
            <div className="text-[10px] font-bold text-emerald-600">
              {loadPct < 85 ? '✓ Normal Thermal' : 'High Load'}
            </div>
          </div>
        </div>

        {/* Load Progress Bar */}
        <div className="space-y-1.5">
          <div className="flex justify-between text-[11px] text-slate-500 font-semibold">
            <span>Motor Thermal Load Ratio</span>
            <span className="font-mono text-blue-900 font-bold">{loadPct}% / 100% Rated</span>
          </div>
          <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                isOverload
                  ? 'bg-rose-500'
                  : 'bg-blue-600'
              }`}
              style={{ width: `${Math.min(100, loadPct)}%` }}
            />
          </div>
        </div>
      </div>

      {/* Grid Protection Status */}
      <div className="mobile-card p-4 space-y-3">
        <h3 className="text-xs font-black uppercase tracking-wider text-slate-400 px-1">
          Electrical Protection Safeguards
        </h3>

        <div className="space-y-2 text-xs">
          <div className="p-3 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-between">
            <span className="font-semibold text-slate-700">CT Current Transformer Sensor</span>
            <span className="font-bold text-emerald-600">Healthy (0 &ndash; 30A)</span>
          </div>
          <div className="p-3 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-between">
            <span className="font-semibold text-slate-700">Under/Overvoltage Protection</span>
            <span className="font-bold text-emerald-600">Armed (180V &ndash; 260V)</span>
          </div>
        </div>
      </div>
    </div>
  );
};
