import React from 'react';
import { Cpu, Clock } from 'lucide-react';
import { Controller } from '../../types';

interface ControllerOfflineOverlayProps {
  controller?: Controller | null;
  className?: string;
}

export const ControllerOfflineOverlay: React.FC<ControllerOfflineOverlayProps> = ({
  controller,
  className = '',
}) => {
  if (!controller || controller.status === 'ACTIVE') {
    return null;
  }

  const isOffline = controller.status === 'OFFLINE' || controller.status === 'DECOMMISSIONED';

  const formatLastSeen = (lastSeen?: string | null) => {
    if (!lastSeen) return 'Unknown';
    try {
      const date = new Date(lastSeen);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return 'Unknown';
    }
  };

  return (
    <div
      className={`rounded-2xl border p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 ${
        isOffline
          ? 'bg-rose-950/40 border-rose-800/60 text-rose-200'
          : 'bg-amber-950/40 border-amber-800/60 text-amber-200'
      } ${className}`}
    >
      <div className="flex items-center gap-3">
        <div
          className={`w-9 h-9 rounded-xl flex items-center justify-center border ${
            isOffline
              ? 'bg-rose-900/50 border-rose-700 text-rose-300'
              : 'bg-amber-900/50 border-amber-700 text-amber-300'
          }`}
        >
          <Cpu className="w-5 h-5" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm tracking-tight">
              CONTROLLER {controller.status}
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-black/40 border border-white/10">
              {controller.controller_code}
            </span>
          </div>
          <p className="text-xs opacity-80 mt-0.5">
            {isOffline
              ? 'Physical hardware is offline. Cloud controls are safely disabled until reconnection.'
              : `Controller is in ${controller.status.toLowerCase()} mode.`}
          </p>
        </div>
      </div>

      {controller.last_seen_at && (
        <div className="flex items-center gap-1.5 text-xs opacity-75 sm:self-center font-mono">
          <Clock className="w-3.5 h-3.5" />
          <span>Last seen: {formatLastSeen(controller.last_seen_at)}</span>
        </div>
      )}
    </div>
  );
};
