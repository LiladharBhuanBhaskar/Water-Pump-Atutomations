import React, { useState } from 'react';
import {
  ArrowLeft,
  Waves,
  RefreshCw,
  Save,
  CheckCircle2,
  Layers,
} from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';

interface TankLevelScreenProps {
  onBack: () => void;
  tankLevel: number;
  waterHeadMeters: number;
  tankStopThreshold: number;
  onUpdateTankThreshold: (threshold: number) => Promise<void>;
  autoStopTankFull: boolean;
  onToggleAutoStop: (enabled: boolean) => Promise<void>;
  onRefresh: () => void;
  isSyncing: boolean;
}

export const TankLevelScreen: React.FC<TankLevelScreenProps> = ({
  onBack,
  tankLevel,
  waterHeadMeters,
  tankStopThreshold: initialThreshold,
  onUpdateTankThreshold,
  autoStopTankFull,
  onToggleAutoStop,
  onRefresh,
  isSyncing,
}) => {
  const { t } = useLanguage();
  const [threshold, setThreshold] = useState<number>(initialThreshold);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [savedSuccess, setSavedSuccess] = useState<boolean>(false);

  const isFull = tankLevel >= threshold;
  const approxLiters = Math.round((tankLevel / 100) * 1000);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await onUpdateTankThreshold(threshold);
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } finally {
      setIsSaving(false);
    }
  };

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
              isFull
                ? 'bg-amber-50 border-amber-200 text-amber-700'
                : 'bg-blue-50 border-blue-200 text-blue-700'
            }`}
          >
            {isFull ? t.tankFull : t.tankFilling}
          </span>
          <button
            type="button"
            onClick={onRefresh}
            className="p-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors cursor-pointer"
            title="Refresh Tank Level"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin text-blue-600' : ''}`} />
          </button>
        </div>
      </div>

      {/* Main Tank Visualizer & Metrics Card */}
      <div className="mobile-card p-5 bg-white border border-slate-200 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-2xl bg-blue-600 text-white flex items-center justify-center flex-shrink-0">
              <Waves className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-base font-black text-slate-900 leading-tight">{t.overheadTankTitle}</h2>
              <p className="text-xs text-slate-500 font-medium mt-0.5">
                {t.overheadTankSubtitle}
              </p>
            </div>
          </div>
          <span className="px-2.5 py-1 rounded-xl bg-blue-50 border border-blue-200 text-xs font-black text-blue-900">
            1000L Tank
          </span>
        </div>

        {/* Big Visual Gauge Section */}
        <div className="flex items-center justify-between p-4 rounded-2xl bg-slate-50 border border-slate-200">
          <div>
            <div className="text-[10px] font-black uppercase tracking-wider text-slate-400">Current Storage</div>
            <div className="text-3xl font-black text-slate-900 tracking-tight font-mono mt-0.5">
              {tankLevel.toFixed(1)}%
            </div>
            <div className="text-xs font-bold text-blue-700 mt-0.5">
              &asymp; {approxLiters} Liters stored
            </div>
          </div>

          {/* Graphical Tank Column */}
          <div className="w-16 h-28 bg-white rounded-2xl p-1.5 border border-slate-200 relative overflow-hidden flex flex-col justify-end">
            <div
              className="w-full rounded-xl bg-blue-600 transition-all duration-700 relative overflow-hidden"
              style={{ height: `${Math.min(100, Math.max(5, tankLevel))}%` }}
            >
              {/* Wave shimmer */}
              <div className="absolute inset-0 bg-white/20 animate-pulse" />
            </div>

            {/* Threshold Line */}
            <div
              className="absolute left-0 right-0 border-t-2 border-dashed border-rose-500 z-10"
              style={{ bottom: `${threshold}%` }}
              title={`Auto-Cutoff: ${threshold}%`}
            />
          </div>
        </div>

        {/* 3 Sub-Metrics */}
        <div className="grid grid-cols-3 gap-2 text-center pt-1">
          <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200">
            <div className="text-[10px] text-slate-400 font-bold uppercase">Water Head</div>
            <div className="text-xs font-black text-slate-900 font-mono mt-0.5">
              {waterHeadMeters.toFixed(1)} m
            </div>
          </div>
          <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200">
            <div className="text-[10px] text-slate-400 font-bold uppercase">Cutoff Level</div>
            <div className="text-xs font-black text-blue-700 font-mono mt-0.5">
              &ge;{threshold}%
            </div>
          </div>
          <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200">
            <div className="text-[10px] text-slate-400 font-bold uppercase">Fill Status</div>
            <div className="text-xs font-black text-emerald-700 mt-0.5">
              {isFull ? 'Target Met' : 'Adequate'}
            </div>
          </div>
        </div>
      </div>

      {/* Threshold Configuration Card */}
      <div className="mobile-card p-4 space-y-3.5 border border-slate-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-xl bg-blue-50 text-blue-700">
              <Layers className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-xs font-black text-slate-900 uppercase tracking-tight">
                Auto-Stop Threshold
              </h3>
              <p className="text-[10px] text-slate-400">Stop motor when overhead tank fills</p>
            </div>
          </div>
          <span className="text-sm font-black text-blue-700 font-mono">{threshold}%</span>
        </div>

        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <input
              type="range"
              min="70"
              max="100"
              step="1"
              value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
              className="flex-1 accent-blue-600 cursor-pointer h-2 bg-slate-100 rounded-lg"
            />
            <input
              type="number"
              min="70"
              max="100"
              value={threshold}
              onChange={(e) => setThreshold(Math.max(70, Math.min(100, Number(e.target.value))))}
              className="w-14 px-2 py-1 text-xs font-black text-center font-mono rounded-lg border border-slate-200 bg-white"
            />
          </div>
          <div className="flex justify-between text-[10px] text-slate-400 font-medium">
            <span>{t.earlyStop}</span>
            <span>{t.maxFull}</span>
          </div>
        </div>

        {/* Auto-Stop Toggle */}
        <label className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 border border-slate-200/60 cursor-pointer">
          <div>
            <div className="text-xs font-bold text-slate-800">{t.tankFullRuleTitle}</div>
            <div className="text-[10px] text-slate-400">{t.tankFullRuleDesc} (&ge; {threshold}%)</div>
          </div>
          <input
            type="checkbox"
            checked={autoStopTankFull}
            onChange={(e) => onToggleAutoStop(e.target.checked)}
            className="w-4 h-4 accent-blue-600 rounded cursor-pointer"
          />
        </label>

        {/* Save Button */}
        <button
          type="button"
          onClick={handleSave}
          disabled={isSaving}
          className="w-full py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-black flex items-center justify-center gap-1.5 transition-all cursor-pointer disabled:opacity-50"
        >
          {isSaving ? (
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
          ) : savedSuccess ? (
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-300" />
          ) : (
            <Save className="w-3.5 h-3.5" />
          )}
          <span>{isSaving ? t.saving : savedSuccess ? t.savedSuccessfully : t.saveTankThreshold}</span>
        </button>
      </div>
    </div>
  );
};
