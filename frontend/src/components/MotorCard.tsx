import React from 'react';
import { Power, Octagon, Loader2, Info } from 'lucide-react';
import { Motor, MotorStatus, CommandStatus, MotorCommand } from '../types';
import { Badge } from './common/Badge';
import { Button } from './common/Button';
import { useAuth } from '../context/AuthContext';

interface MotorCardProps {
  motor: Motor;
  activeCommand?: MotorCommand | null;
  onStart: (motorId: string) => Promise<void>;
  onStop: (motorId: string) => Promise<void>;
  onEmergencyStop: (motorId: string) => Promise<void>;
  onReset?: (motorId: string) => Promise<void>;
  isProcessing?: boolean;
}

export const MotorCard: React.FC<MotorCardProps> = ({
  motor,
  activeCommand,
  onStart,
  onStop,
  onEmergencyStop,
  onReset,
  isProcessing = false,
}) => {
  const { isOperator } = useAuth();
  const isRunning = motor.status === 'ON';
  const isTransitioning = motor.status === 'STARTING' || motor.status === 'STOPPING' || isProcessing;
  const isFault = motor.status === 'FAULT';

  const getStatusBadgeVariant = (status: MotorStatus) => {
    switch (status) {
      case 'ON':
        return 'success';
      case 'STARTING':
      case 'STOPPING':
        return 'warning';
      case 'FAULT':
        return 'danger';
      case 'MAINTENANCE':
        return 'purple';
      case 'OFFLINE':
      case 'DISABLED':
        return 'neutral';
      default:
        return 'default';
    }
  };

  const getCommandStatusVariant = (cmdStatus?: CommandStatus) => {
    switch (cmdStatus) {
      case 'EXECUTED':
        return 'success';
      case 'ACKNOWLEDGED':
      case 'SENT':
      case 'PENDING':
        return 'info';
      case 'FAILED':
      case 'TIMEOUT':
        return 'danger';
      default:
        return 'neutral';
    }
  };

  return (
    <div
      className={`glass-panel p-6 rounded-3xl border flex flex-col justify-between gap-6 transition-all duration-300 ${
        isRunning
          ? 'border-emerald-500/30 shadow-emerald-500/10'
          : isFault
          ? 'border-rose-500/40 bg-rose-950/10 shadow-rose-500/10'
          : 'border-slate-800'
      }`}
    >
      {/* Header Info */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-xl font-bold text-white tracking-tight">{motor.name}</h3>
            <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-lg bg-slate-800 text-cyan-400 border border-slate-700">
              {motor.motor_code}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            {motor.motor_type} &bull; Rated Power: {motor.rated_power ?? 5.5} kW
          </p>
        </div>

        <Badge variant={getStatusBadgeVariant(motor.status)} dot size="md">
          {motor.status}
        </Badge>
      </div>

      {/* Command Lifecycle Status */}
      {activeCommand && (
        <div className="p-3 rounded-xl bg-slate-900/80 border border-slate-800 flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            {activeCommand.status === 'PENDING' || activeCommand.status === 'SENT' || activeCommand.status === 'ACKNOWLEDGED' ? (
              <Loader2 className="w-4 h-4 text-cyan-400 animate-spin" />
            ) : (
              <Info className="w-4 h-4 text-slate-400" />
            )}
            <span className="text-slate-400 font-medium">
              Command <span className="font-mono text-slate-300">#{activeCommand.id.slice(0, 8)}</span> ({activeCommand.command_type}):
            </span>
          </div>

          <Badge variant={getCommandStatusVariant(activeCommand.status)} size="sm">
            {activeCommand.status}
          </Badge>
        </div>
      )}

      {/* Error Message if Failed/Timeout */}
      {activeCommand && (activeCommand.status === 'FAILED' || activeCommand.status === 'TIMEOUT') && (
        <div className="text-xs text-rose-400 bg-rose-950/50 p-2.5 rounded-xl border border-rose-800/40">
          <span className="font-bold">Error:</span> {activeCommand.error_message || 'Command failed execution on controller.'}
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-2 border-t border-slate-800/80">
        {/* Main Start / Stop Button or Reset Button on Fault */}
        {isFault && onReset ? (
          <button
            onClick={() => onReset(motor.id)}
            disabled={!isOperator || isTransitioning}
            className="w-full sm:flex-1 py-4 px-6 rounded-2xl flex items-center justify-center gap-3 font-bold text-sm uppercase tracking-wider transition-all duration-300 shadow-xl border cursor-pointer bg-amber-600 hover:bg-amber-500 text-white border-amber-400/40 shadow-amber-600/25 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Power className="w-5 h-5" />
            <span>RESET FAULT LATCH</span>
          </button>
        ) : (
          <button
            onClick={() => (isRunning ? onStop(motor.id) : onStart(motor.id))}
            disabled={!isOperator || isTransitioning || isFault}
            className={`w-full sm:flex-1 py-4 px-6 rounded-2xl flex items-center justify-center gap-3 font-bold text-sm uppercase tracking-wider transition-all duration-300 shadow-xl border cursor-pointer ${
              isRunning
                ? 'bg-rose-600 hover:bg-rose-500 text-white border-rose-400/40 shadow-rose-600/25 animate-pulse-flow'
                : 'bg-emerald-600 hover:bg-emerald-500 text-white border-emerald-400/40 shadow-emerald-600/25'
            } disabled:opacity-40 disabled:cursor-not-allowed disabled:transform-none`}
          >
            {isTransitioning ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                <span>DISPATCHING...</span>
              </>
            ) : (
              <>
                <Power className="w-5 h-5" />
                <span>{isRunning ? 'STOP PUMP' : 'START PUMP'}</span>
              </>
            )}
          </button>
        )}

        {/* Emergency Stop Button */}
        <Button
          variant="danger"
          size="lg"
          onClick={() => onEmergencyStop(motor.id)}
          disabled={!isOperator || isTransitioning}
          className="w-full sm:w-auto bg-rose-950 hover:bg-rose-900 text-rose-300 border-rose-700/60"
          title="Immediate Emergency Cutoff"
        >
          <Octagon className="w-5 h-5 text-rose-400" />
          <span>E-STOP</span>
        </Button>
      </div>

      {!isOperator && (
        <p className="text-[11px] text-center text-slate-500 italic">
          Read-only access: Operator role required to dispatch motor commands.
        </p>
      )}
    </div>
  );
};
