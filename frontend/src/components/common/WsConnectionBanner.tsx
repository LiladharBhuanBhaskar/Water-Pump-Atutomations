import React from 'react';
import { WifiOff, RefreshCw } from 'lucide-react';
import { ws } from '../../services/ws';

export type WsStatus = 'CONNECTED' | 'RECONNECTING' | 'DISCONNECTED';

interface WsConnectionBannerProps {
  status: WsStatus;
  reconnectAttempts?: number;
}

export const WsConnectionBanner: React.FC<WsConnectionBannerProps> = ({
  status,
  reconnectAttempts = 0,
}) => {
  if (status === 'CONNECTED') {
    return null;
  }

  const handleManualReconnect = () => {
    const token = localStorage.getItem('hydra_token');
    if (token) {
      ws.connect(token);
    }
  };

  return (
    <div
      className={`w-full px-4 py-2.5 flex items-center justify-between text-xs font-medium border-b transition-all duration-300 ${
        status === 'RECONNECTING'
          ? 'bg-amber-950/80 border-amber-800/60 text-amber-200'
          : 'bg-rose-950/80 border-rose-800/60 text-rose-200'
      }`}
    >
      <div className="max-w-7xl mx-auto w-full flex items-center justify-between gap-4">
        <div className="flex items-center gap-2.5">
          {status === 'RECONNECTING' ? (
            <RefreshCw className="w-4 h-4 text-amber-400 animate-spin" />
          ) : (
            <WifiOff className="w-4 h-4 text-rose-400" />
          )}
          <span>
            {status === 'RECONNECTING'
              ? `Reconnecting real-time stream... (Attempt ${reconnectAttempts + 1})`
              : 'Real-time telemetry stream is currently disconnected.'}
          </span>
        </div>

        <button
          type="button"
          onClick={handleManualReconnect}
          className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-slate-900/80 hover:bg-slate-900 text-white font-semibold border border-slate-700/80 transition-colors shadow-sm"
        >
          <RefreshCw className="w-3 h-3" />
          Reconnect Now
        </button>
      </div>
    </div>
  );
};
