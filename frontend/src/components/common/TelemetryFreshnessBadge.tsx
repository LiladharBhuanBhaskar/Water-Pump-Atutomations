import React, { useState, useEffect } from 'react';
import { Clock, AlertTriangle, Radio } from 'lucide-react';

interface TelemetryFreshnessBadgeProps {
  occurredAt?: string | null;
  staleThresholdSeconds?: number;
}

export const TelemetryFreshnessBadge: React.FC<TelemetryFreshnessBadgeProps> = ({
  occurredAt,
  staleThresholdSeconds = 30,
}) => {
  const [now, setNow] = useState<number>(Date.now());

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  if (!occurredAt) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-slate-800/80 text-slate-400 border border-slate-700/60">
        <Clock className="w-3 h-3 text-slate-500" />
        No data
      </span>
    );
  }

  const timestamp = new Date(occurredAt).getTime();
  if (isNaN(timestamp)) {
    return null;
  }

  const diffSec = Math.max(0, Math.floor((now - timestamp) / 1000));
  const isStale = diffSec >= staleThresholdSeconds;
  const isLive = diffSec < 10;

  if (isLive) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
        Live &bull; {diffSec}s ago
      </span>
    );
  }

  if (isStale) {
    const timeDisplay =
      diffSec >= 3600
        ? `${Math.floor(diffSec / 3600)}h ago`
        : diffSec >= 60
        ? `${Math.floor(diffSec / 60)}m ago`
        : `${diffSec}s ago`;

    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30">
        <AlertTriangle className="w-3 h-3 text-amber-400" />
        Stale &bull; {timeDisplay}
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-cyan-950/60 text-cyan-300 border border-cyan-800/50">
      <Radio className="w-3 h-3 text-cyan-400" />
      Updated {diffSec}s ago
    </span>
  );
};
