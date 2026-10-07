import React, { useState, useEffect, useCallback } from 'react';
import {
  X,
  History,
  Filter,
  RotateCcw,
  AlertTriangle,
  Power,
  Octagon,
  Radio,
  ChevronLeft,
  ChevronRight,
  Info,
} from 'lucide-react';
import { MotorEventResponse, MotorEventType, Motor, Station } from '../types';
import { api } from '../services/api';
import { Button } from './common/Button';
import { Badge } from './common/Badge';

interface EventHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  station: Station;
  motor?: Motor | null;
}

const EVENT_TYPES: { key: string; label: string }[] = [
  { key: 'ALL', label: 'All Event Types' },
  { key: 'STARTED', label: 'Started' },
  { key: 'STOPPED', label: 'Stopped' },
  { key: 'FAULT', label: 'Fault' },
  { key: 'RESET', label: 'Reset' },
  { key: 'EMERGENCY_STOP', label: 'Emergency Stop' },
  { key: 'ONLINE', label: 'Online' },
  { key: 'OFFLINE', label: 'Offline' },
];

export const EventHistoryModal: React.FC<EventHistoryModalProps> = ({
  isOpen,
  onClose,
  station,
  motor,
}) => {
  const [events, setEvents] = useState<MotorEventResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters & Pagination State
  const [eventType, setEventType] = useState<string>('ALL');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [page, setPage] = useState<number>(0);
  const pageSize = 20;

  const loadEvents = useCallback(async () => {
    if (!isOpen) return;
    try {
      setLoading(true);
      setError(null);

      const params: any = {
        limit: pageSize,
        offset: page * pageSize,
      };

      if (eventType !== 'ALL') {
        params.event_type = eventType;
      }
      if (startDate) {
        params.start_time = new Date(startDate).toISOString();
      }
      if (endDate) {
        params.end_time = new Date(endDate).toISOString();
      }

      let data: MotorEventResponse[] = [];
      if (motor) {
        data = await api.getMotorEvents(motor.id, params);
      } else {
        data = await api.getStationEvents(station.id, params);
      }

      setEvents(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load event history.');
    } finally {
      setLoading(false);
    }
  }, [isOpen, station.id, motor?.id, eventType, startDate, endDate, page]);

  useEffect(() => {
    if (isOpen) {
      loadEvents();
    }
  }, [isOpen, loadEvents]);

  const handleResetFilters = () => {
    setEventType('ALL');
    setStartDate('');
    setEndDate('');
    setPage(0);
  };

  const getEventBadge = (type: MotorEventType) => {
    switch (type) {
      case 'STARTED':
        return <Badge variant="success" size="sm">STARTED</Badge>;
      case 'STOPPED':
        return <Badge variant="neutral" size="sm">STOPPED</Badge>;
      case 'FAULT':
        return <Badge variant="danger" size="sm">FAULT</Badge>;
      case 'EMERGENCY_STOP':
        return <Badge variant="danger" size="sm">EMERGENCY STOP</Badge>;
      case 'RESET':
        return <Badge variant="warning" size="sm">RESET</Badge>;
      case 'ONLINE':
        return <Badge variant="info" size="sm">ONLINE</Badge>;
      case 'OFFLINE':
        return <Badge variant="neutral" size="sm">OFFLINE</Badge>;
      default:
        return <Badge variant="info" size="sm">{type}</Badge>;
    }
  };

  const getEventIcon = (type: MotorEventType) => {
    switch (type) {
      case 'STARTED':
        return <Power className="w-4 h-4 text-emerald-400" />;
      case 'STOPPED':
        return <Power className="w-4 h-4 text-slate-400" />;
      case 'FAULT':
        return <AlertTriangle className="w-4 h-4 text-rose-400" />;
      case 'EMERGENCY_STOP':
        return <Octagon className="w-4 h-4 text-rose-400" />;
      case 'RESET':
        return <RotateCcw className="w-4 h-4 text-amber-400" />;
      case 'ONLINE':
      case 'OFFLINE':
        return <Radio className="w-4 h-4 text-blue-400" />;
      default:
        return <Info className="w-4 h-4 text-cyan-400" />;
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-4xl glass-panel bg-slate-900/90 border border-slate-700/80 rounded-3xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-slate-800 bg-slate-900/50">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
              <History className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
                Motor Event History
                <Badge variant="info" size="sm">
                  {motor ? `${motor.name} (${motor.motor_code})` : station.name}
                </Badge>
              </h2>
              <p className="text-xs text-slate-400">
                Immutable, tamper-evident historical audit log of operational and safety state transitions.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Filters Toolbar */}
        <div className="px-6 py-3.5 border-b border-slate-800/80 bg-slate-950/40 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-1.5 text-xs text-slate-400">
              <Filter className="w-3.5 h-3.5" />
              <span>Type:</span>
            </div>
            <select
              value={eventType}
              onChange={(e) => {
                setEventType(e.target.value);
                setPage(0);
              }}
              className="px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-700 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              {EVENT_TYPES.map((t) => (
                <option key={t.key} value={t.key}>
                  {t.label}
                </option>
              ))}
            </select>

            <div className="flex items-center gap-2 text-xs text-slate-400">
              <span>From:</span>
              <input
                type="date"
                value={startDate}
                onChange={(e) => {
                  setStartDate(e.target.value);
                  setPage(0);
                }}
                className="px-2.5 py-1 rounded-xl bg-slate-900 border border-slate-700 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
              />
              <span>To:</span>
              <input
                type="date"
                value={endDate}
                onChange={(e) => {
                  setEndDate(e.target.value);
                  setPage(0);
                }}
                className="px-2.5 py-1 rounded-xl bg-slate-900 border border-slate-700 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
              />
            </div>

            {(eventType !== 'ALL' || startDate || endDate) && (
              <button
                type="button"
                onClick={handleResetFilters}
                className="text-xs text-cyan-400 hover:text-cyan-300 underline"
              >
                Reset
              </button>
            )}
          </div>

          <Button
            variant="secondary"
            size="sm"
            icon={<RotateCcw className="w-3.5 h-3.5" />}
            onClick={() => loadEvents()}
            loading={loading}
          >
            Refresh
          </Button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {error && (
            <div className="flex items-center gap-3 p-4 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-sm">
              <AlertTriangle className="w-5 h-5 flex-shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          {loading ? (
            <div className="py-16 text-center text-slate-400 space-y-2">
              <RotateCcw className="w-6 h-6 animate-spin mx-auto text-cyan-400" />
              <p className="text-xs">Querying historical event records...</p>
            </div>
          ) : events.length === 0 ? (
            <div className="py-16 text-center text-slate-400 border border-dashed border-slate-800 rounded-2xl bg-slate-950/30">
              <History className="w-8 h-8 mx-auto text-slate-500 mb-2" />
              <p className="text-sm font-medium text-slate-300">No events found</p>
              <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1">
                No motor events matched the active filters for this station or motor hierarchy.
              </p>
            </div>
          ) : (
            <div className="space-y-2.5">
              {events.map((evt) => (
                <div
                  key={evt.id}
                  className="p-3.5 rounded-2xl bg-slate-950/40 border border-slate-800 hover:border-slate-700/80 transition-all flex items-start justify-between gap-4"
                >
                  <div className="flex items-start gap-3">
                    <div className="p-2 rounded-xl bg-slate-900 border border-slate-800 mt-0.5">
                      {getEventIcon(evt.event_type)}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        {getEventBadge(evt.event_type)}
                        <span className="text-xs font-mono text-slate-400">
                          Source: <span className="text-slate-200">{evt.source}</span>
                        </span>
                      </div>
                      <p className="text-xs text-slate-300 mt-1 font-medium">
                        {evt.description || 'No description recorded'}
                      </p>
                      {evt.event_payload && Object.keys(evt.event_payload).length > 0 && (
                        <div className="mt-1.5 p-2 rounded-lg bg-slate-900/60 border border-slate-800/60 text-[11px] font-mono text-slate-400">
                          {JSON.stringify(evt.event_payload)}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="text-right flex-shrink-0">
                    <span className="text-[11px] font-mono text-cyan-400 block">
                      {new Date(evt.occurred_at).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                      })}
                    </span>
                    <span className="text-[10px] text-slate-500 block">
                      {new Date(evt.occurred_at).toLocaleDateString([], {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                      })}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer & Pagination */}
        <div className="px-6 py-4 border-t border-slate-800 bg-slate-900/50 flex items-center justify-between">
          <div className="text-xs text-slate-400">
            Page {page + 1} • {events.length} items loaded
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              icon={<ChevronLeft className="w-4 h-4" />}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0 || loading}
            >
              Previous
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setPage((p) => p + 1)}
              disabled={events.length < pageSize || loading}
            >
              <span>Next</span>
              <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
            <Button variant="secondary" size="sm" onClick={onClose}>
              Close
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};
