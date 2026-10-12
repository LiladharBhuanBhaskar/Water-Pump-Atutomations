import React from 'react';
import {
  ArrowLeft,
  FileText,
  Timer,
  Zap,
  Calendar,
  Shield,
  History,
  RefreshCw,
} from 'lucide-react';
import { Motor, MotorEventResponse } from '../../types';

interface PumpRunSession {
  id: string;
  motorId: string;
  motorCode: string;
  motorName: string;
  startTime: string;
  stopTime: string | null;
  durationSeconds: number;
  triggerType: 'SCHEDULED' | 'MANUAL' | 'PROTECTION' | 'SYSTEM';
  scheduleName?: string;
  description?: string;
  isRunning: boolean;
  status: 'COMPLETED' | 'RUNNING' | 'TRIPPED';
  stopReason: string;
  stopReasonCategory:
    | 'SCHEDULE_END'
    | 'MANUAL_STOP'
    | 'TANK_FULL'
    | 'TURBIDITY'
    | 'DRY_RUN'
    | 'EMERGENCY_STOP'
    | 'FAULT'
    | 'TIMER'
    | 'RUNNING'
    | 'NORMAL';
  stopReasonDetails?: string;
}

interface LatestEventsScreenProps {
  onBack: () => void;
  runSessions: PumpRunSession[];
  filteredSessions: PumpRunSession[];
  filteredEvents: MotorEventResponse[];
  motors: Motor[];
  historyMotorFilter: string;
  setHistoryMotorFilter: (filter: string) => void;
  historyTypeFilter: string;
  setHistoryTypeFilter: (filter: string) => void;
  historyViewMode: 'SESSIONS' | 'TIMELINE';
  setHistoryViewMode: (mode: 'SESSIONS' | 'TIMELINE') => void;
  historyMetrics: {
    totalFormatted: string;
    scheduledFormatted: string;
    manualFormatted: string;
    scheduledCount: number;
    manualCount: number;
  };
  onRefresh: () => void;
  isSyncing: boolean;
  parseIsoDate: (iso: string | null | undefined) => Date;
  formatDurationSecs: (secs: number) => string;
}

export const LatestEventsScreen: React.FC<LatestEventsScreenProps> = ({
  onBack,
  runSessions,
  filteredSessions,
  filteredEvents,
  motors,
  historyMotorFilter,
  setHistoryMotorFilter,
  historyTypeFilter,
  setHistoryTypeFilter,
  historyViewMode,
  setHistoryViewMode,
  historyMetrics,
  onRefresh,
  isSyncing,
  parseIsoDate,
  formatDurationSecs,
}) => {
  return (
    <div className="space-y-4 animate-fade-in font-['Poppins',sans-serif]">
      {/* Top Header Bar */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-100">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-all cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Home</span>
        </button>

        <div className="flex items-center gap-2">
          <span className="px-2.5 py-1 rounded-xl bg-blue-50 border border-blue-200 text-[11px] font-black text-blue-700">
            {runSessions.length} Cycles Logged
          </span>
          <button
            type="button"
            onClick={onRefresh}
            className="p-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors cursor-pointer"
            title="Refresh History"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin text-blue-600' : ''}`} />
          </button>
        </div>
      </div>

      {/* Hero Card */}
      <div className="mobile-card p-4 bg-white border border-slate-200 space-y-3">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl bg-blue-600 text-white flex items-center justify-center flex-shrink-0">
            <FileText className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-base font-black text-slate-900 leading-tight">Latest Event &amp; Run History</h2>
            <p className="text-xs text-slate-500 font-medium mt-0.5">
              Cycle durations, start/stop times &amp; shutdown reasons
            </p>
          </div>
        </div>
      </div>

      {/* 3 Metrics Cards */}
      <div className="grid grid-cols-3 gap-2">
        <div className="mobile-card p-3 space-y-1">
          <div className="flex items-center gap-1.5 text-indigo-600">
            <Timer className="w-3.5 h-3.5 shrink-0" />
            <span className="text-[10px] font-black uppercase tracking-wider text-slate-400 truncate">
              Total Run
            </span>
          </div>
          <div className="text-sm font-black text-slate-900 truncate">
            {historyMetrics.totalFormatted}
          </div>
          <div className="text-[9px] text-slate-400 font-medium truncate">
            {runSessions.length} total cycle{runSessions.length !== 1 ? 's' : ''}
          </div>
        </div>

        <div className="mobile-card p-3 space-y-1">
          <div className="flex items-center gap-1.5 text-teal-600">
            <Calendar className="w-3.5 h-3.5 shrink-0" />
            <span className="text-[10px] font-black uppercase tracking-wider text-slate-400 truncate">
              Scheduled
            </span>
          </div>
          <div className="text-sm font-black text-teal-800 truncate">
            {historyMetrics.scheduledCount} <span className="text-xs font-semibold text-slate-500">runs</span>
          </div>
          <div className="text-[9px] text-teal-700 font-medium truncate">
            {historyMetrics.scheduledFormatted}
          </div>
        </div>

        <div className="mobile-card p-3 space-y-1">
          <div className="flex items-center gap-1.5 text-blue-600">
            <Zap className="w-3.5 h-3.5 shrink-0" />
            <span className="text-[10px] font-black uppercase tracking-wider text-slate-400 truncate">
              Manual
            </span>
          </div>
          <div className="text-sm font-black text-blue-800 truncate">
            {historyMetrics.manualCount} <span className="text-xs font-semibold text-slate-500">runs</span>
          </div>
          <div className="text-[9px] text-blue-700 font-medium truncate">
            {historyMetrics.manualFormatted}
          </div>
        </div>
      </div>

      {/* Motor Selector Chips (if multiple motors) */}
      {motors.length > 1 && (
        <div className="space-y-1.5">
          <div className="text-[10px] font-black uppercase tracking-wider text-slate-400 px-1">
            Filter by Motor
          </div>
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
            <button
              type="button"
              onClick={() => setHistoryMotorFilter('ALL')}
              className={`px-3 py-1 rounded-xl text-xs font-bold transition-all shrink-0 ${
                historyMotorFilter === 'ALL'
                  ? 'bg-slate-900 text-white'
                  : 'bg-white text-slate-600 border border-slate-200'
              }`}
            >
              All Motors ({motors.length})
            </button>
            {motors.map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => setHistoryMotorFilter(m.id)}
                className={`px-3 py-1 rounded-xl text-xs font-bold transition-all shrink-0 font-mono ${
                  historyMotorFilter === m.id
                    ? 'bg-purple-600 text-white'
                    : 'bg-white text-slate-700 border border-slate-200'
                }`}
              >
                {m.motor_code}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Filter Chips & View Mode Toggle */}
      <div className="flex items-center justify-between gap-2 flex-wrap pt-0.5">
        <div className="flex items-center gap-1 overflow-x-auto scrollbar-none">
          <button
            type="button"
            onClick={() => setHistoryTypeFilter('ALL')}
            className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all shrink-0 ${
              historyTypeFilter === 'ALL'
                ? 'bg-slate-800 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            All
          </button>
          <button
            type="button"
            onClick={() => setHistoryTypeFilter('SCHEDULED')}
            className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all shrink-0 flex items-center gap-1 ${
              historyTypeFilter === 'SCHEDULED'
                ? 'bg-teal-600 text-white'
                : 'bg-teal-50 text-teal-800 hover:bg-teal-100'
            }`}
          >
            <Calendar className="w-2.5 h-2.5" />
            <span>Scheduled</span>
          </button>
          <button
            type="button"
            onClick={() => setHistoryTypeFilter('MANUAL')}
            className={`px-2.5 py-1 rounded-lg text-[11px] font-bold transition-all shrink-0 flex items-center gap-1 ${
              historyTypeFilter === 'MANUAL'
                ? 'bg-blue-600 text-white'
                : 'bg-blue-50 text-blue-800 hover:bg-blue-100'
            }`}
          >
            <Zap className="w-2.5 h-2.5" />
            <span>Manual</span>
          </button>
        </div>

        <div className="flex items-center bg-slate-100 p-0.5 rounded-xl border border-slate-200/80 shrink-0">
          <button
            type="button"
            onClick={() => setHistoryViewMode('SESSIONS')}
            className={`px-2.5 py-1 rounded-lg text-[10px] font-extrabold transition-all flex items-center gap-1 ${
              historyViewMode === 'SESSIONS'
                ? 'bg-white text-slate-900 shadow-xs'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <Timer className="w-3 h-3 text-teal-600" />
            <span>Cycles</span>
          </button>
          <button
            type="button"
            onClick={() => setHistoryViewMode('TIMELINE')}
            className={`px-2.5 py-1 rounded-lg text-[10px] font-extrabold transition-all flex items-center gap-1 ${
              historyViewMode === 'TIMELINE'
                ? 'bg-white text-slate-900 shadow-xs'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <History className="w-3 h-3 text-slate-600" />
            <span>Raw Log</span>
          </button>
        </div>
      </div>

      {/* SESSIONS VIEW */}
      {historyViewMode === 'SESSIONS' && (
        <div className="space-y-2.5">
          {filteredSessions.length === 0 ? (
            <div className="mobile-card p-8 text-center text-xs text-slate-400 space-y-2">
              <Timer className="w-8 h-8 text-slate-300 mx-auto" />
              <p className="font-bold text-slate-700">No pump run cycles found</p>
            </div>
          ) : (
            filteredSessions.map((session) => {
              const isSched = session.triggerType === 'SCHEDULED';
              const isManual = session.triggerType === 'MANUAL';
              const isRunning = session.isRunning || session.status === 'RUNNING';

              const startDateObj = parseIsoDate(session.startTime);
              const stopDateObj = session.stopTime ? parseIsoDate(session.stopTime) : null;

              return (
                <div
                  key={session.id}
                  className={`mobile-card p-3.5 space-y-2.5 border transition-all ${
                    isRunning
                      ? 'border-emerald-300 bg-emerald-50/30 ring-1 ring-emerald-400/20'
                      : 'border-slate-200/80 bg-white'
                  }`}
                >
                  {/* Top Row: Motor Code, Trigger Source & Status */}
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="px-2 py-0.5 rounded-lg bg-slate-900 text-white text-[10px] font-black font-mono flex items-center gap-1">
                        <Zap className="w-2.5 h-2.5 text-teal-400" />
                        {session.motorCode}
                      </span>
                      <span className="text-xs font-bold text-slate-800 truncate">
                        {session.motorName}
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5">
                      <span
                        className={`px-2 py-0.5 rounded-lg text-[10px] font-extrabold flex items-center gap-1 border ${
                          isSched
                            ? 'bg-teal-50 text-teal-800 border-teal-200'
                            : isManual
                            ? 'bg-blue-50 text-blue-800 border-blue-200'
                            : 'bg-rose-50 text-rose-800 border-rose-200'
                        }`}
                      >
                        {isSched ? (
                          <Calendar className="w-2.5 h-2.5 text-teal-600" />
                        ) : isManual ? (
                          <Zap className="w-2.5 h-2.5 text-blue-600" />
                        ) : (
                          <Shield className="w-2.5 h-2.5 text-rose-600" />
                        )}
                        <span>{isSched ? 'SCHEDULED' : isManual ? 'MANUAL' : 'SAFETY'}</span>
                      </span>

                      {isRunning ? (
                        <span className="px-2 py-0.5 rounded-lg text-[10px] font-black bg-emerald-50 text-emerald-700 border border-emerald-300 flex items-center gap-1 animate-pulse">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                          <span>RUNNING</span>
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-lg text-[10px] font-bold bg-slate-100 text-slate-600">
                          {session.status === 'TRIPPED' ? 'TRIPPED' : 'OFF'}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Middle Row: Start Time, Off Time, and Total Duration */}
                  <div className="grid grid-cols-3 gap-2 p-2.5 rounded-xl bg-slate-50/80 border border-slate-100 text-center items-center">
                    <div className="text-left space-y-0.5">
                      <div className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">Started</div>
                      <div className="text-xs font-bold text-slate-900 font-mono">
                        {startDateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </div>
                    </div>

                    <div className="text-left space-y-0.5">
                      <div className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">Stopped</div>
                      <div className="text-xs font-bold text-slate-900 font-mono">
                        {stopDateObj
                          ? stopDateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                          : 'Running...'}
                      </div>
                    </div>

                    <div className="text-right space-y-0.5">
                      <div className="text-[9px] font-extrabold uppercase tracking-wider text-teal-700">Duration</div>
                      <div className="text-xs font-black text-teal-900 font-mono">
                        {formatDurationSecs(session.durationSeconds)}
                      </div>
                    </div>
                  </div>

                  {/* REASON MOTOR CLOSED */}
                  {!isRunning && (
                    <div className="p-2 rounded-xl bg-slate-50 border border-slate-200/60 text-xs flex items-center gap-2">
                      <span className="text-[10px] font-black uppercase tracking-wider text-slate-400">Reason:</span>
                      <span className="font-bold text-slate-800">{session.stopReason}</span>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}

      {/* TIMELINE VIEW */}
      {historyViewMode === 'TIMELINE' && (
        <div className="space-y-2">
          {filteredEvents.length === 0 ? (
            <div className="mobile-card p-6 text-center text-xs text-slate-400">
              No event records logged.
            </div>
          ) : (
            filteredEvents.map((ev) => (
              <div
                key={ev.id}
                className="mobile-card p-3 flex items-center justify-between text-xs gap-2"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <span
                    className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                      ev.event_type === 'STARTED'
                        ? 'bg-emerald-500'
                        : ev.event_type === 'STOPPED'
                        ? 'bg-blue-500'
                        : 'bg-rose-500'
                    }`}
                  />
                  <div className="min-w-0">
                    <div className="font-bold text-slate-900">{ev.event_type} &bull; {ev.source}</div>
                    <div className="text-[10px] text-slate-400 truncate">{ev.description || 'Station event'}</div>
                  </div>
                </div>
                <span className="text-[10px] font-mono text-slate-400 shrink-0">
                  {parseIsoDate(ev.occurred_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};
