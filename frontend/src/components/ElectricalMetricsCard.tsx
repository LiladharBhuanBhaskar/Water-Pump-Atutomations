import React from 'react';
import { Zap, AlertTriangle, ShieldAlert, CheckCircle2, RefreshCw } from 'lucide-react';
import { ElectricalMetricsResponse } from '../types';

interface ElectricalMetricsCardProps {
  motorName?: string;
  data?: ElectricalMetricsResponse | null;
  loading?: boolean;
  onRefresh?: () => void;
}

export const ElectricalMetricsCard: React.FC<ElectricalMetricsCardProps> = ({
  motorName,
  data,
  loading = false,
  onRefresh,
}) => {
  const current = data?.current_a ?? null;
  const voltage = data?.voltage_v ?? null;
  const power = data?.power_kw ?? null;
  const loadPercentage = data?.load_percentage ?? null;
  const status = data?.status ?? 'NORMAL';
  const shouldTrip = data?.should_trip ?? false;
  const tripReason = data?.trip_reason ?? null;
  const motorStatus = data?.motor_status ?? 'OFF';
  const powerFactor = data?.power_factor ?? 0.85;

  // Determine variant
  let statusBadge = {
    bg: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
    text: 'LOAD BALANCED / NORMAL',
    icon: CheckCircle2,
  };

  if (status === 'OVERCURRENT' || shouldTrip) {
    statusBadge = {
      bg: 'bg-rose-500/20 text-rose-300 border-rose-500/30',
      text: 'OVERLOAD / OVERCURRENT TRIP',
      icon: ShieldAlert,
    };
  } else if (status === 'UNDERVOLTAGE' || status === 'OVERVOLTAGE') {
    statusBadge = {
      bg: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
      text: `${status.replace('_', ' ')} ALERT`,
      icon: AlertTriangle,
    };
  } else if (status === 'UNDERCURRENT') {
    statusBadge = {
      bg: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
      text: 'UNDERCURRENT / LOW LOAD',
      icon: AlertTriangle,
    };
  }

  const StatusIcon = statusBadge.icon;
  const safeLoad = Math.min(150, Math.max(0, loadPercentage ?? 0));

  return (
    <div className="glass-panel p-6 rounded-3xl border border-slate-800 relative overflow-hidden flex flex-col justify-between space-y-6">
      {/* Glow */}
      <div
        className={`absolute -right-12 -top-12 w-44 h-44 rounded-full blur-3xl pointer-events-none opacity-20 transition-all duration-700 ${
          status === 'OVERCURRENT' || shouldTrip
            ? 'bg-rose-500'
            : status === 'UNDERVOLTAGE' || status === 'OVERVOLTAGE'
            ? 'bg-amber-500'
            : 'bg-amber-400'
        }`}
      />

      {/* Header */}
      <div className="flex items-start justify-between gap-2 z-10">
        <div className="flex items-center gap-3">
          <div
            className={`p-3 rounded-2xl ${
              status === 'OVERCURRENT' || shouldTrip
                ? 'bg-rose-500/20 text-rose-400'
                : status === 'UNDERVOLTAGE' || status === 'OVERVOLTAGE'
                ? 'bg-amber-500/20 text-amber-400'
                : 'bg-amber-500/20 text-amber-400'
            }`}
          >
            <Zap className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white tracking-wide">
              {motorName ? `${motorName} — Electrical Metrics` : 'Electrical Metrics'}
            </h3>
            <p className="text-xs text-slate-400">Current, Voltage & Thermal Load Protection</p>
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
              title="Refresh Electrical Metrics"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            </button>
          )}
        </div>
      </div>

      {/* Electrical Grid Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 z-10">
        {/* Current */}
        <div className="p-3.5 rounded-2xl bg-slate-900/60 border border-slate-800/80 space-y-1">
          <span className="text-[11px] font-semibold text-slate-400">Current</span>
          <div className="text-xl font-extrabold text-white font-mono">
            {current !== null ? `${current.toFixed(1)} A` : '0.0 A'}
          </div>
          <span className="text-[10px] text-slate-500 font-mono">Line Current</span>
        </div>

        {/* Voltage */}
        <div className="p-3.5 rounded-2xl bg-slate-900/60 border border-slate-800/80 space-y-1">
          <span className="text-[11px] font-semibold text-slate-400">Voltage</span>
          <div className="text-xl font-extrabold text-white font-mono">
            {voltage !== null ? `${voltage.toFixed(0)} V` : '230 V'}
          </div>
          <span className="text-[10px] text-slate-500 font-mono">Nominal RMS</span>
        </div>

        {/* Power */}
        <div className="p-3.5 rounded-2xl bg-slate-900/60 border border-slate-800/80 space-y-1">
          <span className="text-[11px] font-semibold text-slate-400">Est. Power</span>
          <div className="text-xl font-extrabold text-white font-mono">
            {power !== null ? `${power.toFixed(2)} kW` : '0.00 kW'}
          </div>
          <span className="text-[10px] text-slate-500 font-mono">PF: {powerFactor.toFixed(2)}</span>
        </div>

        {/* Load % */}
        <div className="p-3.5 rounded-2xl bg-slate-900/60 border border-slate-800/80 space-y-1">
          <span className="text-[11px] font-semibold text-slate-400">Thermal Load</span>
          <div className="text-xl font-extrabold text-white font-mono">
            {loadPercentage !== null ? `${loadPercentage.toFixed(0)}%` : '0%'}
          </div>
          <span
            className={`text-[10px] font-bold ${
              loadPercentage && loadPercentage > 100 ? 'text-rose-400' : 'text-emerald-400'
            }`}
          >
            {loadPercentage && loadPercentage > 100 ? 'OVERLOAD' : 'NOMINAL'}
          </span>
        </div>
      </div>

      {/* Load Progress Bar */}
      <div className="space-y-1.5 z-10">
        <div className="flex justify-between text-[11px] text-slate-400">
          <span>Operating Load Ratio</span>
          <span className="font-mono">{loadPercentage !== null ? `${loadPercentage.toFixed(1)}%` : '0%'} / 100% Rated</span>
        </div>
        <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden relative">
          <div
            className={`h-full transition-all duration-700 ${
              loadPercentage && loadPercentage > 100
                ? 'bg-gradient-to-r from-amber-500 to-rose-500'
                : 'bg-gradient-to-r from-cyan-500 to-emerald-400'
            }`}
            style={{ width: `${Math.min(100, safeLoad)}%` }}
          />
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
        <div className="flex items-center gap-2">
          <span>Motor State:</span>
          <span className="font-bold text-white font-mono">{motorStatus}</span>
        </div>
        {data?.current_updated_at && (
          <span>Updated: {new Date(data.current_updated_at).toLocaleTimeString()}</span>
        )}
      </div>
    </div>
  );
};
