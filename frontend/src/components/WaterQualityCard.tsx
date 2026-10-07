import React from 'react';
import { Droplet, AlertTriangle, ShieldAlert, CheckCircle2, RefreshCw } from 'lucide-react';
import { WaterQualityResponse } from '../types';

interface WaterQualityCardProps {
  data?: WaterQualityResponse | null;
  loading?: boolean;
  onRefresh?: () => void;
}

export const WaterQualityCard: React.FC<WaterQualityCardProps> = ({
  data,
  loading = false,
  onRefresh,
}) => {
  const turbidity = data?.turbidity_ntu ?? null;
  const ph = data?.ph ?? null;
  const status = data?.status ?? 'SAFE';
  const shouldTrip = data?.should_trip ?? false;
  const tripReason = data?.trip_reason ?? null;
  const threshold = data?.threshold_used ?? 5.0;

  // Determine variant
  let statusBadge = {
    bg: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
    text: 'OPTIMAL / SAFE',
    icon: CheckCircle2,
  };

  if (shouldTrip || status === 'UNSAFE') {
    statusBadge = {
      bg: 'bg-rose-500/20 text-rose-300 border-rose-500/30',
      text: 'CRITICAL CONTAMINATION TRIP',
      icon: ShieldAlert,
    };
  } else if (status === 'WARNING') {
    statusBadge = {
      bg: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
      text: 'ELEVATED TURBIDITY WARNING',
      icon: AlertTriangle,
    };
  }

  const StatusIcon = statusBadge.icon;

  return (
    <div className="glass-panel p-6 rounded-3xl border border-slate-800 relative overflow-hidden flex flex-col justify-between space-y-6">
      {/* Glow */}
      <div
        className={`absolute -right-12 -top-12 w-44 h-44 rounded-full blur-3xl pointer-events-none opacity-20 transition-all duration-700 ${
          shouldTrip ? 'bg-rose-500' : status === 'WARNING' ? 'bg-amber-500' : 'bg-teal-500'
        }`}
      />

      {/* Header */}
      <div className="flex items-start justify-between gap-2 z-10">
        <div className="flex items-center gap-3">
          <div
            className={`p-3 rounded-2xl ${
              shouldTrip
                ? 'bg-rose-500/20 text-rose-400'
                : status === 'WARNING'
                ? 'bg-amber-500/20 text-amber-400'
                : 'bg-teal-500/20 text-teal-400'
            }`}
          >
            <Droplet className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white tracking-wide">Water Quality Diagnostics</h3>
            <p className="text-xs text-slate-400">Turbidity & pH Chemical Safety</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className={`px-3 py-1 rounded-full text-xs font-bold border flex items-center gap-1.5 ${statusBadge.bg}`}>
            <StatusIcon className="w-3.5 h-3.5" />
            <span>{statusBadge.text}</span>
          </div>
          {onRefresh && (
            <button
              onClick={onRefresh}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
              title="Refresh Water Quality"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            </button>
          )}
        </div>
      </div>

      {/* Main Diagnostics Display */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 z-10">
        {/* Turbidity Metric */}
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-300">Turbidity (Clarity)</span>
            <span className="text-[11px] font-mono text-cyan-400 font-bold">
              Limit: &le;{threshold} NTU
            </span>
          </div>

          <div className="flex items-baseline justify-between">
            <div className="text-2xl font-extrabold text-white font-mono">
              {turbidity !== null ? `${turbidity.toFixed(2)} NTU` : 'N/A'}
            </div>
            {turbidity !== null && (
              <span
                className={`text-xs font-bold ${
                  turbidity > threshold
                    ? 'text-rose-400'
                    : turbidity > threshold * 0.8
                    ? 'text-amber-400'
                    : 'text-emerald-400'
                }`}
              >
                {turbidity > threshold ? 'TURBIDITY TRIP' : turbidity > threshold * 0.8 ? 'NEAR LIMIT' : 'EXCELLENT'}
              </span>
            )}
          </div>

          {/* Turbidity Visual Scale */}
          <div className="w-full bg-slate-800 h-2.5 rounded-full overflow-hidden relative">
            <div
              className={`h-full transition-all duration-700 ${
                turbidity && turbidity > threshold
                  ? 'bg-rose-500'
                  : turbidity && turbidity > threshold * 0.8
                  ? 'bg-amber-500'
                  : 'bg-emerald-500'
              }`}
              style={{ width: `${Math.min(100, ((turbidity ?? 0) / (threshold * 2)) * 100)}%` }}
            />
          </div>
        </div>

        {/* pH Metric */}
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-300">pH Level</span>
            <span className="text-[11px] font-mono text-cyan-400 font-bold">
              Safe: 6.5 – 8.5
            </span>
          </div>

          <div className="flex items-baseline justify-between">
            <div className="text-2xl font-extrabold text-white font-mono">
              {ph !== null ? `${ph.toFixed(2)} pH` : 'N/A'}
            </div>
            {ph !== null && (
              <span
                className={`text-xs font-bold ${
                  ph < 6.5 || ph > 8.5 ? 'text-rose-400' : 'text-emerald-400'
                }`}
              >
                {ph < 6.5 ? 'ACIDIC' : ph > 8.5 ? 'ALKALINE' : 'NEUTRAL / SAFE'}
              </span>
            )}
          </div>

          {/* pH Visual Scale */}
          <div className="w-full bg-slate-800 h-2.5 rounded-full overflow-hidden relative">
            <div
              className={`h-full transition-all duration-700 ${
                ph && (ph < 6.5 || ph > 8.5) ? 'bg-rose-500' : 'bg-teal-400'
              }`}
              style={{ width: `${Math.min(100, Math.max(0, (((ph ?? 7) - 4) / 6) * 100))}%` }}
            />
          </div>
        </div>
      </div>

      {/* Trip Reason Banner if any */}
      {tripReason && (
        <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-800/80 text-rose-200 text-xs flex items-center gap-2 z-10">
          <ShieldAlert className="w-4 h-4 text-rose-400 flex-shrink-0" />
          <span>{tripReason}</span>
        </div>
      )}

      {/* Footer Info */}
      <div className="flex items-center justify-between text-[11px] text-slate-400 border-t border-slate-800/60 pt-3 z-10">
        <span>Chemical Safety Authority: Backend Validated</span>
        {data?.turbidity_updated_at && (
          <span>Updated: {new Date(data.turbidity_updated_at).toLocaleTimeString()}</span>
        )}
      </div>
    </div>
  );
};
