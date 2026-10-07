import React from 'react';
import {
  Droplets,
  Waves,
  Activity,
  Gauge,
  Thermometer,
  CloudRain,
  Zap,
  FlaskConical,
  Cpu,
  AlertTriangle,
  Clock,
} from 'lucide-react';
import { Card } from './common/Card';
import { Sensor, SensorType, SensorStatus } from '../types';

interface SensorCardProps {
  sensor: Sensor;
  latestReading?: {
    value: number;
    unit: string;
    occurred_at: string;
    metadata?: Record<string, any>;
  };
}

export const SensorCard: React.FC<SensorCardProps> = ({ sensor, latestReading }) => {
  const sType = sensor.sensor_type;
  const value = latestReading?.value;
  const unit = latestReading?.unit || sensor.unit || '';
  const occurredAt = latestReading?.occurred_at;
  const quality = latestReading?.metadata?.quality;

  // Icon & color theme based on SensorType
  const getSensorVisuals = (type: SensorType) => {
    switch (type) {
      case 'WATER_LEVEL':
        return { icon: Droplets, color: 'text-cyan-400', bg: 'bg-cyan-500/10', border: 'border-cyan-500/20' };
      case 'TURBIDITY':
        return { icon: Waves, color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/20' };
      case 'FLOW':
      case 'FLOW_RATE':
        return { icon: Activity, color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20' };
      case 'PRESSURE':
        return { icon: Gauge, color: 'text-teal-400', bg: 'bg-teal-500/10', border: 'border-teal-500/20' };
      case 'TEMPERATURE':
        return { icon: Thermometer, color: 'text-rose-400', bg: 'bg-rose-500/10', border: 'border-rose-500/20' };
      case 'HUMIDITY':
        return { icon: CloudRain, color: 'text-indigo-400', bg: 'bg-indigo-500/10', border: 'border-indigo-500/20' };
      case 'CURRENT':
        return { icon: Zap, color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/20' };
      case 'VOLTAGE':
        return { icon: Zap, color: 'text-purple-400', bg: 'bg-purple-500/10', border: 'border-purple-500/20' };
      case 'PH':
        return { icon: FlaskConical, color: 'text-fuchsia-400', bg: 'bg-fuchsia-500/10', border: 'border-fuchsia-500/20' };
      default:
        return { icon: Cpu, color: 'text-slate-400', bg: 'bg-slate-500/10', border: 'border-slate-500/20' };
    }
  };

  const getStatusBadge = (status: SensorStatus) => {
    switch (status) {
      case 'ACTIVE':
        return <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">ACTIVE</span>;
      case 'FAULT':
        return <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20">FAULT</span>;
      case 'MAINTENANCE':
        return <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">MAINT</span>;
      case 'DISABLED':
        return <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-500/10 text-slate-400 border border-slate-500/20">DISABLED</span>;
      default:
        return <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-500/10 text-slate-400 border border-slate-500/20">{status}</span>;
    }
  };

  const visuals = getSensorVisuals(sType);
  const IconComponent = visuals.icon;
  const isOutOfRange = quality === 'OUT_OF_RANGE';
  const isFault = sensor.status === 'FAULT';

  return (
    <Card
      hover
      className={`relative overflow-hidden transition-all duration-300 ${
        isFault
          ? 'border-rose-500/50 bg-rose-950/20'
          : isOutOfRange
          ? 'border-amber-500/40 bg-amber-950/10'
          : visuals.border
      }`}
    >
      {/* Header: Name, Code & Visual Icon */}
      <div className="flex items-start justify-between">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-bold text-white tracking-tight">{sensor.name}</h4>
            {getStatusBadge(sensor.status)}
          </div>
          <p className="text-[11px] font-mono text-slate-400">{sensor.sensor_code} • {sensor.sensor_type}</p>
        </div>
        <div className={`p-2.5 rounded-xl ${visuals.bg} ${visuals.color}`}>
          <IconComponent className="w-5 h-5" />
        </div>
      </div>

      {/* Main Measurement Value */}
      <div className="mt-4 flex items-baseline justify-between">
        <div className="flex items-baseline gap-1.5">
          <span className="text-3xl font-extrabold text-white tracking-tight">
            {value !== undefined && value !== null ? Number(value).toFixed(2).replace(/\.?0+$/, '') : '--'}
          </span>
          <span className="text-sm font-semibold text-slate-400">{unit}</span>
        </div>

        {isOutOfRange && (
          <div className="flex items-center gap-1 text-[11px] font-semibold text-amber-400 bg-amber-500/10 px-2 py-1 rounded-md border border-amber-500/20">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Range Warning</span>
          </div>
        )}
      </div>

      {/* Description / Metadata */}
      {sensor.description && (
        <p className="mt-2 text-xs text-slate-400 line-clamp-1">{sensor.description}</p>
      )}

      {/* Footer: Last Update Timestamp */}
      <div className="mt-3 pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400">
        <div className="flex items-center gap-1">
          <Clock className="w-3.5 h-3.5" />
          <span>{occurredAt ? new Date(occurredAt).toLocaleTimeString() : 'Awaiting data'}</span>
        </div>
        <span className="text-[10px] font-mono text-slate-400">ID: {sensor.id.slice(0, 8)}</span>
      </div>
    </Card>
  );
};
