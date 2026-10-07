import React from 'react';
import { AlertTriangle, ShieldAlert, CheckCircle2, Clock, Activity, RefreshCw } from 'lucide-react';
import { FlowDiagnosticsResponse } from '../types';

interface FlowDiagnosticsCardProps {
  motorName?: string;
  data?: FlowDiagnosticsResponse | null;
  loading?: boolean;
  onRefresh?: () => void;
}

export const FlowDiagnosticsCard: React.FC<FlowDiagnosticsCardProps> = ({
  motorName,
  data,
  loading = false,
  onRefresh,
}) => {
  const flowLpm = data?.flow_rate_lpm ?? null;
  const flowM3h = data?.flow_rate_m3h ?? null;
  const status = data?.status ?? 'NORMAL';
  const isStartupGrace = data?.is_startup_grace_period ?? false;
  const shouldTrip = data?.should_trip ?? false;
  const tripReason = data?.trip_reason ?? null;
  const motorStatus = data?.motor_status ?? 'OFF';

  // Determine variant
  let statusBadge = {
    bg: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
    text: 'FLOW NORMAL / HEALTHY',
    icon: CheckCircle2,
  };

  if (isStartupGrace) {
    statusBadge = {
      bg: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
      text: 'STARTUP GRACE PERIOD ACTIVE',
      icon: Clock,
    };
  } else if (status === 'DRY_RUN' || shouldTrip) {
    statusBadge = {
      bg: 'bg-rose-500/20 text-rose-300 border-rose-500/30',
      text: 'DRY-RUN / NO FLOW TRIP',
      icon: ShieldAlert,
    };
  } else if (status === 'BURST') {
    statusBadge = {
      bg: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
      text: 'PIPE BURST / EXCESSIVE FLOW',
      icon: AlertTriangle,
    };
  }

  const StatusIcon = statusBadge.icon;

  return (
    <div className="glass-panel p-6 rounded-3xl border border-slate-800 relative overflow-hidden flex flex-col justify-between space-y-6">
      {/* Glow */}
      <div
        className={`absolute -right-12 -top-12 w-44 h-44 rounded-full blur-3xl pointer-events-none opacity-20 transition-all duration-700 ${
          status === 'DRY_RUN' || shouldTrip
            ? 'bg-rose-500'
            : status === 'BURST'
            ? 'bg-purple-500'
            : isStartupGrace
            ? 'bg-cyan-500'
            : 'bg-blue-500'
        }`}
      />

      {/* Header */}
      <div className="flex items-start justify-between gap-2 z-10">
        <div className="flex items-center gap-3">
          <div
            className={`p-3 rounded-2xl ${
              status === 'DRY_RUN' || shouldTrip
                ? 'bg-rose-500/20 text-rose-400'
                : status === 'BURST'
                ? 'bg-purple-500/20 text-purple-400'
                : isStartupGrace
                ? 'bg-cyan-500/20 text-cyan-400'
                : 'bg-blue-500/20 text-blue-400'
            }`}
          >
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white tracking-wide">
              {motorName ? `${motorName} — Flow Diagnostics` : 'Flow Diagnostics'}
            </h3>
            <p className="text-xs text-slate-400">Dry-Run & Pipe Burst Protection</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className={`px-3 py-1 rounded-full text-xs font-bold border flex items-center gap-1.5 ${statusBadge.bg}`}>
            <StatusIcon className={`w-3.5 h-3.5 ${isStartupGrace ? 'animate-spin' : ''}`} />
            <span>{statusBadge.text}</span>
          </div>
          {onRefresh && (
            <button
              onClick={onRefresh}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
              title="Refresh Flow Diagnostics"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            </button>
          )}
        </div>
      </div>

      {/* Dual Flow Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 z-10">
        {/* L/min */}
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-300">Volumetric Rate (L/min)</span>
            <span className="text-[11px] font-mono text-cyan-400 font-bold">LPM</span>
          </div>
          <div className="text-2xl font-extrabold text-white font-mono">
            {flowLpm !== null ? `${flowLpm.toFixed(1)} L/min` : '0.0 L/min'}
          </div>
          <div className="text-[11px] text-slate-400 flex items-center justify-between">
            <span>Motor: <span className="text-white font-bold">{motorStatus}</span></span>
            {isStartupGrace && <span className="text-cyan-400 font-semibold">Priming Grace Active</span>}
          </div>
        </div>

        {/* m3/h */}
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-300">Bulk Flow (m³/h)</span>
            <span className="text-[11px] font-mono text-cyan-400 font-bold">M3/H</span>
          </div>
          <div className="text-2xl font-extrabold text-white font-mono">
            {flowM3h !== null ? `${flowM3h.toFixed(2)} m³/h` : '0.00 m³/h'}
          </div>
          <div className="text-[11px] text-slate-400 flex items-center justify-between">
            <span>Status: <span className="text-white font-bold">{status}</span></span>
            {flowLpm && flowLpm > 0 && <span className="text-emerald-400 font-semibold">Flowing</span>}
          </div>
        </div>
      </div>

      {/* Trip banner */}
      {tripReason && (
        <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-800/80 text-rose-200 text-xs flex items-center gap-2 z-10">
          <ShieldAlert className="w-4 h-4 text-rose-400 flex-shrink-0" />
          <span>{tripReason}</span>
        </div>
      )}

      {/* Footer Info */}
      <div className="flex items-center justify-between text-[11px] text-slate-400 border-t border-slate-800/60 pt-3 z-10">
        <span>Protection Mode: Automatic Dry-Run Interlock</span>
        {data?.flow_updated_at && (
          <span>Updated: {new Date(data.flow_updated_at).toLocaleTimeString()}</span>
        )}
      </div>
    </div>
  );
};
