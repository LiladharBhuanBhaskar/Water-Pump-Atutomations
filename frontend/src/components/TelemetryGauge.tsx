import React from 'react';
import { Droplets, Activity, Gauge, Zap, Waves, AlertTriangle } from 'lucide-react';
import { Card } from './common/Card';

interface TelemetryData {
  waterLevel?: number; // %
  turbidity?: number; // NTU
  flowRate?: number; // L/min
  current?: number; // A
  voltage?: number; // V
  pressure?: number; // bar
  lastUpdated?: string;
}

interface TelemetryGaugeProps {
  telemetry: TelemetryData;
}

export const TelemetryGauge: React.FC<TelemetryGaugeProps> = ({ telemetry }) => {
  const level = telemetry.waterLevel ?? 0;
  const turbidity = telemetry.turbidity ?? 0;
  const flow = telemetry.flowRate ?? 0;
  const current = telemetry.current ?? 0;
  const voltage = telemetry.voltage ?? 230;
  const pressure = telemetry.pressure ?? 0;

  const isTurbidityHigh = turbidity > 25;
  const isTankFull = level >= 95;
  const isTankLow = level < 15;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
      {/* 1. Water Level Gauge */}
      <Card
        hover
        className={`relative overflow-hidden ${
          isTankFull ? 'border-amber-500/40' : isTankLow ? 'border-rose-500/40' : ''
        }`}
      >
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Water Level
          </span>
          <div className="p-2 rounded-xl bg-cyan-500/10 text-cyan-400">
            <Droplets className="w-5 h-5" />
          </div>
        </div>

        <div className="mt-3 flex items-baseline gap-1">
          <span className="text-2xl font-extrabold text-white tracking-tight">{level.toFixed(1)}</span>
          <span className="text-xs font-semibold text-slate-400">%</span>
        </div>

        {/* Progress bar */}
        <div className="mt-3 w-full bg-slate-800 rounded-full h-2 overflow-hidden">
          <div
            className={`h-full transition-all duration-500 rounded-full ${
              isTankFull
                ? 'bg-amber-400'
                : isTankLow
                ? 'bg-rose-500'
                : 'bg-gradient-to-r from-cyan-500 to-blue-500'
            }`}
            style={{ width: `${Math.min(100, Math.max(0, level))}%` }}
          />
        </div>

        <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
          <span>{isTankFull ? 'Tank Full Auto-Stop' : isTankLow ? 'Low Water Alert' : 'Normal'}</span>
          <span>Max 100%</span>
        </div>
      </Card>

      {/* 2. Turbidity */}
      <Card
        hover
        className={`relative overflow-hidden ${
          isTurbidityHigh ? 'border-rose-500/50 bg-rose-950/20' : ''
        }`}
      >
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Turbidity
          </span>
          <div
            className={`p-2 rounded-xl ${
              isTurbidityHigh ? 'bg-rose-500/20 text-rose-400 animate-pulse' : 'bg-blue-500/10 text-blue-400'
            }`}
          >
            {isTurbidityHigh ? <AlertTriangle className="w-5 h-5" /> : <Waves className="w-5 h-5" />}
          </div>
        </div>

        <div className="mt-3 flex items-baseline gap-1">
          <span
            className={`text-2xl font-extrabold tracking-tight ${
              isTurbidityHigh ? 'text-rose-400' : 'text-white'
            }`}
          >
            {turbidity.toFixed(1)}
          </span>
          <span className="text-xs font-semibold text-slate-400">NTU</span>
        </div>

        <div className="mt-3 w-full bg-slate-800 rounded-full h-2 overflow-hidden">
          <div
            className={`h-full transition-all duration-500 rounded-full ${
              isTurbidityHigh ? 'bg-rose-500' : 'bg-gradient-to-r from-emerald-500 to-blue-500'
            }`}
            style={{ width: `${Math.min(100, (turbidity / 50) * 100)}%` }}
          />
        </div>

        <div className="mt-2 flex items-center justify-between text-[11px]">
          <span className={isTurbidityHigh ? 'text-rose-400 font-bold' : 'text-slate-400'}>
            {isTurbidityHigh ? 'Cutoff Active (>25)' : 'Safe Quality'}
          </span>
          <span className="text-slate-500">Limit: 25 NTU</span>
        </div>
      </Card>

      {/* 3. Flow Rate */}
      <Card hover>
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Flow Rate
          </span>
          <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-400">
            <Activity className="w-5 h-5" />
          </div>
        </div>

        <div className="mt-3 flex items-baseline gap-1">
          <span className="text-2xl font-extrabold text-white tracking-tight">{flow.toFixed(1)}</span>
          <span className="text-xs font-semibold text-slate-400">L/min</span>
        </div>

        <div className="mt-3 w-full bg-slate-800 rounded-full h-2 overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-emerald-500 to-teal-400 transition-all duration-500 rounded-full"
            style={{ width: `${Math.min(100, (flow / 120) * 100)}%` }}
          />
        </div>

        <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
          <span>{flow > 0 ? 'Pumping Active' : 'Idle'}</span>
          <span>Max 120 L/m</span>
        </div>
      </Card>

      {/* 4. Current */}
      <Card hover>
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Current
          </span>
          <div className="p-2 rounded-xl bg-amber-500/10 text-amber-400">
            <Zap className="w-5 h-5" />
          </div>
        </div>

        <div className="mt-3 flex items-baseline gap-1">
          <span className="text-2xl font-extrabold text-white tracking-tight">{current.toFixed(2)}</span>
          <span className="text-xs font-semibold text-slate-400">A</span>
        </div>

        <div className="mt-3 w-full bg-slate-800 rounded-full h-2 overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-amber-500 to-orange-400 transition-all duration-500 rounded-full"
            style={{ width: `${Math.min(100, (current / 25) * 100)}%` }}
          />
        </div>

        <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
          <span>Motor Load</span>
          <span>Rated 18A</span>
        </div>
      </Card>

      {/* 5. Voltage */}
      <Card hover>
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Voltage
          </span>
          <div className="p-2 rounded-xl bg-purple-500/10 text-purple-400">
            <Zap className="w-5 h-5" />
          </div>
        </div>

        <div className="mt-3 flex items-baseline gap-1">
          <span className="text-2xl font-extrabold text-white tracking-tight">{voltage.toFixed(0)}</span>
          <span className="text-xs font-semibold text-slate-400">V</span>
        </div>

        <div className="mt-3 w-full bg-slate-800 rounded-full h-2 overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-purple-500 to-indigo-400 transition-all duration-500 rounded-full"
            style={{ width: `${Math.min(100, (voltage / 260) * 100)}%` }}
          />
        </div>

        <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
          <span>Line Phase</span>
          <span>Nominal 230V</span>
        </div>
      </Card>

      {/* 6. Pressure */}
      <Card hover>
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Pressure
          </span>
          <div className="p-2 rounded-xl bg-teal-500/10 text-teal-400">
            <Gauge className="w-5 h-5" />
          </div>
        </div>

        <div className="mt-3 flex items-baseline gap-1">
          <span className="text-2xl font-extrabold text-white tracking-tight">{pressure.toFixed(2)}</span>
          <span className="text-xs font-semibold text-slate-400">bar</span>
        </div>

        <div className="mt-3 w-full bg-slate-800 rounded-full h-2 overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-teal-500 to-cyan-400 transition-all duration-500 rounded-full"
            style={{ width: `${Math.min(100, (pressure / 6) * 100)}%` }}
          />
        </div>

        <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
          <span>Discharge Line</span>
          <span>Max 6.0 bar</span>
        </div>
      </Card>
    </div>
  );
};
