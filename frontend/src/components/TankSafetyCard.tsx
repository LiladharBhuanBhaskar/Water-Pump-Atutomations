import React from 'react';
import { Waves, AlertTriangle, ShieldCheck, CheckCircle2, ShieldAlert } from 'lucide-react';
import { MotorStatus } from '../types';

interface TankSafetyCardProps {
  overheadLevel?: number | null; // percentage or cm
  sumpLevel?: number | null; // percentage or cm
  overheadThreshold?: number | null; // e.g. 95%
  sumpThreshold?: number | null; // e.g. 15%
  isTankFull?: boolean;
  isSourceDepleted?: boolean;
  motorStatus?: MotorStatus;
  lastUpdated?: string | null;
}

export const TankSafetyCard: React.FC<TankSafetyCardProps> = ({
  overheadLevel = 72,
  sumpLevel = 84,
  overheadThreshold = 95,
  sumpThreshold = 15,
  isTankFull = false,
  isSourceDepleted = false,
  motorStatus,
  lastUpdated,
}) => {
  const safeOverheadThresh = overheadThreshold ?? 95;
  const safeSumpThresh = sumpThreshold ?? 15;

  // Determine overall safety state
  let stateVariant: 'normal' | 'warning' | 'full' | 'depleted' = 'normal';
  let statusText = 'NORMAL / SAFE';
  let badgeColor = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30';

  if (isSourceDepleted || (sumpLevel !== null && sumpLevel !== undefined && sumpLevel < safeSumpThresh)) {
    stateVariant = 'depleted';
    statusText = 'SOURCE DEPLETED / SAFETY TRIP';
    badgeColor = 'bg-rose-500/20 text-rose-300 border-rose-500/30';
  } else if (isTankFull || (overheadLevel !== null && overheadLevel !== undefined && overheadLevel >= safeOverheadThresh)) {
    stateVariant = 'full';
    statusText = 'TANK FULL / AUTO-STOP';
    badgeColor = 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30';
  } else if (
    (sumpLevel !== null && sumpLevel !== undefined && sumpLevel < safeSumpThresh + 10) ||
    (overheadLevel !== null && overheadLevel !== undefined && overheadLevel > safeOverheadThresh - 5)
  ) {
    stateVariant = 'warning';
    statusText = 'SAFETY WARNING';
    badgeColor = 'bg-amber-500/20 text-amber-300 border-amber-500/30';
  }

  const safeOverhead = Math.min(100, Math.max(0, overheadLevel ?? 0));
  const safeSump = Math.min(100, Math.max(0, sumpLevel ?? 0));

  return (
    <div className="glass-panel p-6 rounded-3xl border border-slate-800 relative overflow-hidden flex flex-col justify-between space-y-6">
      {/* Background ambient glow */}
      <div
        className={`absolute -right-12 -top-12 w-44 h-44 rounded-full blur-3xl pointer-events-none opacity-20 transition-all duration-700 ${
          stateVariant === 'depleted'
            ? 'bg-rose-500'
            : stateVariant === 'full'
            ? 'bg-indigo-500'
            : stateVariant === 'warning'
            ? 'bg-amber-500'
            : 'bg-cyan-500'
        }`}
      />

      {/* Header */}
      <div className="flex items-start justify-between gap-2 z-10">
        <div className="flex items-center gap-3">
          <div
            className={`p-3 rounded-2xl ${
              stateVariant === 'depleted'
                ? 'bg-rose-500/20 text-rose-400'
                : stateVariant === 'full'
                ? 'bg-indigo-500/20 text-indigo-400'
                : stateVariant === 'warning'
                ? 'bg-amber-500/20 text-amber-400'
                : 'bg-cyan-500/20 text-cyan-400'
            }`}
          >
            <Waves className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-base font-bold text-white tracking-wide">Tank Safety & Water Levels</h3>
            <p className="text-xs text-slate-400">Overhead & Sump Level Monitoring</p>
          </div>
        </div>

        <div className={`px-3 py-1 rounded-full text-xs font-bold border flex items-center gap-1.5 ${badgeColor}`}>
          {stateVariant === 'normal' && <CheckCircle2 className="w-3.5 h-3.5" />}
          {stateVariant === 'warning' && <AlertTriangle className="w-3.5 h-3.5" />}
          {stateVariant === 'full' && <ShieldCheck className="w-3.5 h-3.5" />}
          {stateVariant === 'depleted' && <ShieldAlert className="w-3.5 h-3.5" />}
          <span>{statusText}</span>
        </div>
      </div>

      {/* Dual Tank Gauges */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 z-10">
        {/* Overhead Tank */}
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-300">Overhead Tank</span>
            <span className="text-[11px] font-mono text-cyan-400 font-bold">
              Threshold: {safeOverheadThresh}%
            </span>
          </div>

          <div className="flex items-baseline justify-between">
            <div className="text-2xl font-extrabold text-white font-mono">
              {overheadLevel !== null && overheadLevel !== undefined ? `${overheadLevel.toFixed(1)}%` : 'N/A'}
            </div>
            {overheadLevel !== null && overheadLevel !== undefined && (
              <span className={`text-xs font-bold ${overheadLevel >= safeOverheadThresh ? 'text-indigo-400' : 'text-slate-400'}`}>
                {overheadLevel >= safeOverheadThresh ? 'AUTO-STOP REACHED' : 'FILLING'}
              </span>
            )}
          </div>

          {/* Level Progress Bar */}
          <div className="w-full bg-slate-800 h-3 rounded-full overflow-hidden relative">
            <div
              className={`h-full transition-all duration-700 ${
                overheadLevel && overheadLevel >= safeOverheadThresh
                  ? 'bg-gradient-to-r from-cyan-500 to-indigo-500'
                  : 'bg-gradient-to-r from-blue-600 to-cyan-400'
              }`}
              style={{ width: `${safeOverhead}%` }}
            />
            {/* Cutoff Marker */}
            <div
              className="absolute top-0 bottom-0 w-0.5 bg-rose-400/80"
              style={{ left: `${safeOverheadThresh}%` }}
              title={`Auto-Stop Cutoff: ${safeOverheadThresh}%`}
            />
          </div>
        </div>

        {/* Sump / Source Tank */}
        <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-300">Source / Sump Level</span>
            <span className="text-[11px] font-mono text-emerald-400 font-bold">
              Min Safety: {safeSumpThresh}%
            </span>
          </div>

          <div className="flex items-baseline justify-between">
            <div className="text-2xl font-extrabold text-white font-mono">
              {sumpLevel !== null && sumpLevel !== undefined ? `${sumpLevel.toFixed(1)}%` : 'N/A'}
            </div>
            {sumpLevel !== null && sumpLevel !== undefined && (
              <span className={`text-xs font-bold ${sumpLevel <= safeSumpThresh ? 'text-rose-400' : 'text-slate-400'}`}>
                {sumpLevel <= safeSumpThresh ? 'DEPLETED TRIP' : 'ADEQUATE'}
              </span>
            )}
          </div>

          {/* Level Progress Bar */}
          <div className="w-full bg-slate-800 h-3 rounded-full overflow-hidden relative">
            <div
              className={`h-full transition-all duration-700 ${
                sumpLevel && sumpLevel <= safeSumpThresh
                  ? 'bg-gradient-to-r from-rose-600 to-rose-400'
                  : 'bg-gradient-to-r from-emerald-600 to-teal-400'
              }`}
              style={{ width: `${safeSump}%` }}
            />
            {/* Depletion Marker */}
            <div
              className="absolute top-0 bottom-0 w-0.5 bg-rose-500"
              style={{ left: `${safeSumpThresh}%` }}
              title={`Depletion Safety Cutoff: ${safeSumpThresh}%`}
            />
          </div>
        </div>
      </div>

      {/* Footer Info */}
      <div className="flex items-center justify-between text-[11px] text-slate-400 border-t border-slate-800/60 pt-3 z-10">
        <div className="flex items-center gap-2">
          <span>Target Motor State:</span>
          <span className="font-bold text-white font-mono">{motorStatus || 'OFF'}</span>
        </div>
        {lastUpdated && <span>Updated: {new Date(lastUpdated).toLocaleTimeString()}</span>}
      </div>
    </div>
  );
};
