import React, { useState } from 'react';
import {
  ArrowLeft,
  Droplet,
  RefreshCw,
  Save,
  CheckCircle2,
  Shield,
} from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';

interface WaterQualityScreenProps {
  onBack: () => void;
  turbidity: number;
  ph: number;
  turbidityStopThreshold: number;
  onUpdateTurbidityThreshold: (threshold: number) => Promise<void>;
  onRefresh: () => void;
  isSyncing: boolean;
}

export const WaterQualityScreen: React.FC<WaterQualityScreenProps> = ({
  onBack,
  turbidity,
  ph,
  turbidityStopThreshold: initialThreshold,
  onUpdateTurbidityThreshold,
  onRefresh,
  isSyncing,
}) => {
  const { t } = useLanguage();
  const [threshold, setThreshold] = useState<number>(initialThreshold);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [savedSuccess, setSavedSuccess] = useState<boolean>(false);

  const isTripped = turbidity > threshold;
  const isClean = turbidity < 10;

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await onUpdateTurbidityThreshold(threshold);
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
              isTripped
                ? 'bg-rose-50 border-rose-200 text-rose-700'
                : isClean
                ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                : 'bg-amber-50 border-amber-200 text-amber-700'
            }`}
          >
            {isTripped ? t.turbidityWarning : t.potableSafe}
          </span>
          <button
            type="button"
            onClick={onRefresh}
            className="p-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors cursor-pointer"
            title="Refresh Water Quality"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin text-blue-600' : ''}`} />
          </button>
        </div>
      </div>

      {/* Hero Overview */}
      <div className="mobile-card p-5 bg-white border border-slate-200 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-2xl bg-blue-600 text-white flex items-center justify-center flex-shrink-0">
              <Droplet className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-base font-black text-slate-900 leading-tight">{t.waterQualityTitle}</h2>
              <p className="text-xs text-slate-500 font-medium mt-0.5">
                {t.waterQualitySubtitle}
              </p>
            </div>
          </div>
        </div>

        {/* Dual Cards: Turbidity & pH */}
        <div className="grid grid-cols-2 gap-3">
          {/* Turbidity */}
          <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 space-y-1">
            <div className="text-[10px] font-black uppercase tracking-wider text-slate-400">Turbidity</div>
            <div className="text-2xl font-black text-slate-900 font-mono flex items-baseline gap-1">
              <span>{turbidity.toFixed(1)}</span>
              <span className="text-xs text-slate-400 font-normal">NTU</span>
            </div>
            <div className="text-[11px] font-bold text-emerald-600">
              {turbidity < 10 ? '✓ Potable / Clean' : 'Requires Filtration'}
            </div>
          </div>

          {/* pH Level */}
          <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 space-y-1">
            <div className="text-[10px] font-black uppercase tracking-wider text-slate-400">pH Balance</div>
            <div className="text-2xl font-black text-slate-900 font-mono flex items-baseline gap-1">
              <span>{ph.toFixed(1)}</span>
              <span className="text-xs text-slate-400 font-normal">pH</span>
            </div>
            <div className="text-[11px] font-bold text-blue-700">
              {ph >= 6.5 && ph <= 8.5 ? '✓ Balanced (Neutral)' : 'Abnormal pH'}
            </div>
          </div>
        </div>

        {/* Clarity Progress Bar */}
        <div className="space-y-1.5">
          <div className="flex justify-between text-[11px] text-slate-500 font-semibold">
            <span>Turbidity Murkiness Gauge</span>
            <span className="font-mono text-slate-700 font-bold">{turbidity.toFixed(1)} / {threshold} NTU Max</span>
          </div>
          <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                isTripped
                  ? 'bg-rose-500'
                  : turbidity > 15
                  ? 'bg-amber-500'
                  : 'bg-blue-600'
              }`}
              style={{ width: `${Math.min(100, (turbidity / 50) * 100)}%` }}
            />
          </div>
        </div>
      </div>

      {/* Turbidity Auto-Trip Threshold Card */}
      <div className="mobile-card p-4 space-y-3.5 border border-slate-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-xl bg-blue-50 text-blue-700">
              <Shield className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-xs font-black text-slate-900 uppercase tracking-tight">
                Turbidity Trip Cutoff
              </h3>
              <p className="text-[10px] text-slate-400">Trips pump if incoming muddy water exceeds limit</p>
            </div>
          </div>
          <span className="text-sm font-black text-blue-700 font-mono">{threshold} NTU</span>
        </div>

        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <input
              type="range"
              min="5"
              max="50"
              step="1"
              value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
              className="flex-1 accent-blue-600 cursor-pointer h-2 bg-slate-100 rounded-lg"
            />
            <input
              type="number"
              min="5"
              max="50"
              value={threshold}
              onChange={(e) => setThreshold(Math.max(5, Math.min(50, Number(e.target.value))))}
              className="w-14 px-2 py-1 text-xs font-black text-center font-mono rounded-lg border border-slate-200 bg-white"
            />
          </div>
          <div className="flex justify-between text-[10px] text-slate-400 font-medium">
            <span>5 NTU (Pure / Clear)</span>
            <span>50 NTU (Allow Higher Turbidity)</span>
          </div>
        </div>

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
          <span>{isSaving ? t.saving : savedSuccess ? t.savedSuccessfully : t.saveQualityThreshold}</span>
        </button>
      </div>
    </div>
  );
};
