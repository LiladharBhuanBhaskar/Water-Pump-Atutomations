import React, { useState } from 'react';
import { Power, Octagon, Loader2, Info, History, Clock, AlertTriangle } from 'lucide-react';
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
  onViewEvents?: (motor: Motor) => void;
  timerRemainingSeconds?: number;
  isProcessing?: boolean;
  disabledReason?: string | null;
}

export const MotorCard: React.FC<MotorCardProps> = ({
  motor,
  activeCommand,
  onStart,
  onStop,
  onEmergencyStop,
  onReset,
  onViewEvents,
  timerRemainingSeconds,
  isProcessing = false,
  disabledReason,
}) => {
  const { isOperator } = useAuth();
  const [localError, setLocalError] = useState<string | null>(null);
  const [isLocalActionPending, setIsLocalActionPending] = useState<boolean>(false);

  const isRunning = motor.status === 'ON';
  const isTransitioning =
    motor.status === 'STARTING' || motor.status === 'STOPPING' || isProcessing || isLocalActionPending;
  const isFault = motor.status === 'FAULT';
  const isDisabled = !isOperator || isTransitioning || !!disabledReason;

  const handleAction = async (actionFn: (id: string) => Promise<void>) => {
    setLocalError(null);
    setIsLocalActionPending(true);
    try {
      await actionFn(motor.id);
    } catch (err: any) {
      setLocalError(err.message || 'Motor command failed.');
    } finally {
      setIsLocalActionPending(false);
    }
  };

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

        <div className="flex items-center gap-2">
          {isRunning && timerRemainingSeconds !== undefined && timerRemainingSeconds > 0 && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 text-xs font-mono">
              <Clock className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
              <span>
                {Math.floor(timerRemainingSeconds / 60)}:
                {String(timerRemainingSeconds % 60).padStart(2, '0')}
              </span>
            </div>
          )}

          {onViewEvents && (
            <button
              type="button"
              onClick={() => onViewEvents(motor)}
              className="p-1.5 rounded-xl text-slate-400 hover:text-cyan-400 hover:bg-slate-800/80 border border-transparent hover:border-slate-700 transition-all"
              title="View Motor Event History"
            >
              <History className="w-4 h-4" />
            </button>
          )}

          <Badge variant={getStatusBadgeVariant(motor.status)} dot size="md">
            {motor.status}
          </Badge>
        </div>
      </div>

      {/* Local Command Error Banner */}
      {localError && (
        <div className="p-3 rounded-xl bg-rose-950/80 border border-rose-800/80 text-rose-200 text-xs flex items-center justify-between gap-2 shadow-md">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
            <span>{localError}</span>
          </div>
          <button
            onClick={() => setLocalError(null)}
            className="text-rose-400 hover:text-white font-bold px-1"
          >
            &times;
          </button>
        </div>
      )}

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

      {/* Error Message if Failed/Timeout from server */}
      {activeCommand && (activeCommand.status === 'FAILED' || activeCommand.status === 'TIMEOUT') && !localError && (
        <div className="text-xs text-rose-400 bg-rose-950/50 p-2.5 rounded-xl border border-rose-800/40">
          <span className="font-bold">Error:</span> {activeCommand.error_message || 'Command failed execution on controller.'}
        </div>
      )}

      {/* Disabled Reason Banner (e.g. Controller Offline) */}
      {disabledReason && (
        <div className="text-[11px] text-amber-300 bg-amber-950/40 p-2 rounded-xl border border-amber-800/50 flex items-center gap-2">
          <Info className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
          <span>{disabledReason}</span>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-2 border-t border-slate-800/80">
        {/* Main Start / Stop Button or Reset Button on Fault */}
        {isFault && onReset ? (
          <button
            type="button"
            onClick={() => handleAction(onReset)}
            disabled={isDisabled}
            className="w-full sm:flex-1 py-4 px-6 rounded-2xl flex items-center justify-center gap-3 font-bold text-sm uppercase tracking-wider transition-all duration-300 shadow-xl border cursor-pointer bg-amber-600 hover:bg-amber-500 text-white border-amber-400/40 shadow-amber-600/25 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Power className="w-5 h-5" />
            <span>RESET FAULT LATCH</span>
          </button>
        ) : (
          <button
            type="button"
            onClick={() => handleAction(isRunning ? onStop : onStart)}
            disabled={isDisabled || isFault}
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
          onClick={() => handleAction(onEmergencyStop)}
          disabled={!isOperator || isTransitioning || !!disabledReason}
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
