import React from 'react';
import {
  AlertOctagon,
  ShieldAlert,
  AlertTriangle,
  Waves,
  Droplet,
  Zap,
  Activity,
  X,
  Info,
} from 'lucide-react';
import { Button } from './common/Button';

export interface SafetyAlert {
  id: string;
  eventType: string;
  motorCode?: string;
  deviceUid?: string;
  stationId?: string;
  description: string;
  timestamp: string;
  severity?: 'CRITICAL' | 'WARNING' | 'INFO';
}

interface SafetyAlertBannerProps {
  alerts: SafetyAlert[];
  onDismiss?: (id: string) => void;
}

export const SafetyAlertBanner: React.FC<SafetyAlertBannerProps> = ({ alerts, onDismiss }) => {
  if (!alerts || alerts.length === 0) return null;

  return (
    <div className="space-y-3">
      {alerts.map((alert) => {
        const type = alert.eventType?.toUpperCase() || '';
        const desc = alert.description?.toLowerCase() || '';

        // Classify alert severity and icons
        let severity: 'CRITICAL' | 'WARNING' | 'INFO' = alert.severity || 'WARNING';
        let alertTitle = 'SAFETY INTERLOCK ALERT';
        let Icon = ShieldAlert;
        let badgeBg = 'bg-amber-600 text-white';
        let containerStyle = 'bg-amber-950/80 border-amber-500/70 text-amber-200 animate-pulse-warning';

        if (type === 'EMERGENCY_STOP' || desc.includes('emergency') || desc.includes('estop')) {
          severity = 'CRITICAL';
          alertTitle = 'EMERGENCY STOP ENGAGED';
          Icon = AlertOctagon;
          badgeBg = 'bg-rose-600 text-white';
          containerStyle = 'bg-rose-950/85 border-rose-500/80 text-rose-100 shadow-rose-950/50';
        } else if (type === 'TANK_FULL') {
          severity = 'INFO';
          alertTitle = 'OVERHEAD TANK FULL — AUTO STOP';
          Icon = Waves;
          badgeBg = 'bg-indigo-600 text-white';
          containerStyle = 'bg-indigo-950/80 border-indigo-500/70 text-indigo-200';
        } else if (type === 'SOURCE_DEPLETED') {
          severity = 'CRITICAL';
          alertTitle = 'SOURCE / SUMP DEPLETED — SAFETY TRIP';
          Icon = Waves;
          badgeBg = 'bg-rose-600 text-white';
          containerStyle = 'bg-rose-950/85 border-rose-500/80 text-rose-100';
        } else if (type === 'TURBIDITY_TRIP') {
          severity = 'CRITICAL';
          alertTitle = 'WATER CONTAMINATION — TURBIDITY TRIP';
          Icon = Droplet;
          badgeBg = 'bg-amber-600 text-white';
          containerStyle = 'bg-amber-950/80 border-amber-500/70 text-amber-100';
        } else if (type === 'DRY_RUN_TRIP') {
          severity = 'CRITICAL';
          alertTitle = 'PUMP DRY-RUN DETECTED — SAFETY TRIP';
          Icon = Activity;
          badgeBg = 'bg-rose-600 text-white';
          containerStyle = 'bg-rose-950/85 border-rose-500/80 text-rose-100';
        } else if (type === 'PIPE_BURST') {
          severity = 'CRITICAL';
          alertTitle = 'PIPE BURST / EXCESSIVE FLOW TRIP';
          Icon = AlertTriangle;
          badgeBg = 'bg-purple-600 text-white';
          containerStyle = 'bg-purple-950/85 border-purple-500/80 text-purple-100';
        } else if (type === 'OVERLOAD_TRIP') {
          severity = 'CRITICAL';
          alertTitle = 'ELECTRICAL THERMAL OVERLOAD TRIP';
          Icon = Zap;
          badgeBg = 'bg-rose-600 text-white';
          containerStyle = 'bg-rose-950/85 border-rose-500/80 text-rose-100';
        } else if (type === 'UNDERCURRENT_TRIP' || type === 'VOLTAGE_TRIP') {
          severity = 'WARNING';
          alertTitle = `ELECTRICAL ${type.replace('_', ' ')}`;
          Icon = Zap;
          badgeBg = 'bg-amber-600 text-white';
          containerStyle = 'bg-amber-950/80 border-amber-500/70 text-amber-200';
        } else if (type === 'RESET') {
          severity = 'INFO';
          alertTitle = 'SAFETY INTERLOCK RESET';
          Icon = Info;
          badgeBg = 'bg-emerald-600 text-white';
          containerStyle = 'bg-emerald-950/80 border-emerald-500/70 text-emerald-200';
        }

        return (
          <div
            key={alert.id}
            className={`p-4 rounded-2xl border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-xl transition-all duration-300 ${containerStyle}`}
          >
            <div className="flex items-start gap-3">
              <div className={`p-2.5 rounded-xl flex-shrink-0 ${badgeBg}`}>
                <Icon className="w-5 h-5" />
              </div>
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-extrabold text-xs uppercase tracking-wider">
                    {alertTitle}
                  </span>
                  <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded-md bg-black/40">
                    {severity}
                  </span>
                  {alert.motorCode && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-black/40 font-mono font-bold">
                      Motor: {alert.motorCode}
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-200 max-w-2xl">{alert.description}</p>
                <div className="flex flex-wrap items-center gap-4 text-[11px] text-slate-400">
                  {alert.deviceUid && <span>Controller: {alert.deviceUid}</span>}
                  <span>Timestamp: {new Date(alert.timestamp).toLocaleTimeString()}</span>
                </div>
              </div>
            </div>

            {onDismiss && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onDismiss(alert.id)}
                className="text-slate-300 hover:text-white flex-shrink-0"
              >
                <X className="w-4 h-4 mr-1" />
                Dismiss
              </Button>
            )}
          </div>
        );
      })}
    </div>
  );
};
