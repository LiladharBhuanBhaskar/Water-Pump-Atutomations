import React, { useState, useEffect } from 'react';
import {
  X,
  Calendar,
  Clock,
  Plus,
  Trash2,
  CheckCircle2,
  AlertCircle,
  RotateCcw,
  Check,
  ShieldAlert,
} from 'lucide-react';
import { Station, Motor, ScheduleResponse, ScheduleCreateRequest } from '../types';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { Button } from './common/Button';
import { Badge } from './common/Badge';

interface ScheduleManagerModalProps {
  isOpen: boolean;
  onClose: () => void;
  station: Station;
  motors: Motor[];
}

const ALL_DAYS = [
  { key: 'MON', label: 'Mon' },
  { key: 'TUE', label: 'Tue' },
  { key: 'WED', label: 'Wed' },
  { key: 'THU', label: 'Thu' },
  { key: 'FRI', label: 'Fri' },
  { key: 'SAT', label: 'Sat' },
  { key: 'SUN', label: 'Sun' },
];

export const ScheduleManagerModal: React.FC<ScheduleManagerModalProps> = ({
  isOpen,
  onClose,
  station,
  motors,
}) => {
  const { hasRole } = useAuth();
  const canManageSchedules = hasRole(['SUPER_ADMIN', 'ORGANIZATION_ADMIN', 'SITE_MANAGER']);

  const [schedules, setSchedules] = useState<ScheduleResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // New Schedule Form State
  const [isCreating, setIsCreating] = useState<boolean>(false);
  const [name, setName] = useState<string>('');
  const [selectedMotorId, setSelectedMotorId] = useState<string>('');
  const [selectedDays, setSelectedDays] = useState<string[]>(['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']);
  const [startTime, setStartTime] = useState<string>('06:00');
  const [durationMinutes, setDurationMinutes] = useState<number>(30);
  const [submitting, setSubmitting] = useState<boolean>(false);

  useEffect(() => {
    if (isOpen) {
      loadSchedules();
      if (motors.length > 0 && !selectedMotorId) {
        setSelectedMotorId(motors[0].id);
      }
    }
  }, [isOpen, station.id]);

  const loadSchedules = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getSchedules(station.id);
      setSchedules(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load schedules.');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleActive = async (schedule: ScheduleResponse) => {
    if (!canManageSchedules) return;
    try {
      setError(null);
      const updated = await api.updateSchedule(station.id, schedule.id, {
        is_active: !schedule.is_active,
      });
      setSchedules((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
      setSuccessMsg(`Schedule "${schedule.name}" ${updated.is_active ? 'activated' : 'deactivated'}.`);
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to update schedule status.');
    }
  };

  const handleDelete = async (scheduleId: string, scheduleName: string) => {
    if (!canManageSchedules) return;
    if (!confirm(`Are you sure you want to delete the schedule "${scheduleName}"?`)) return;

    try {
      setError(null);
      await api.deleteSchedule(station.id, scheduleId);
      setSchedules((prev) => prev.filter((s) => s.id !== scheduleId));
      setSuccessMsg(`Schedule "${scheduleName}" deleted successfully.`);
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to delete schedule.');
    }
  };

  const toggleDay = (dayKey: string) => {
    setSelectedDays((prev) =>
      prev.includes(dayKey) ? prev.filter((d) => d !== dayKey) : [...prev, dayKey]
    );
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canManageSchedules) return;

    if (!name.trim()) {
      setError('Schedule name is required.');
      return;
    }
    if (!selectedMotorId) {
      setError('Please select a target motor.');
      return;
    }
    if (selectedDays.length === 0) {
      setError('Please select at least one day of the week.');
      return;
    }
    if (durationMinutes <= 0 || durationMinutes > 1440) {
      setError('Duration must be between 1 and 1440 minutes.');
      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      const payload: ScheduleCreateRequest = {
        station_id: station.id,
        motor_id: selectedMotorId,
        name: name.trim(),
        days_of_week: selectedDays,
        start_time: startTime,
        duration_seconds: durationMinutes * 60,
        is_active: true,
      };

      const newSched = await api.createSchedule(station.id, payload);
      setSchedules((prev) => [...prev, newSched]);
      setSuccessMsg(`Schedule "${newSched.name}" created successfully.`);
      setIsCreating(false);
      setName('');
      setSelectedDays(['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']);
      setStartTime('06:00');
      setDurationMinutes(30);
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to create schedule.');
    } finally {
      setSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-3xl glass-panel bg-slate-900/90 border border-slate-700/80 rounded-3xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-slate-800 bg-slate-900/50">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
              <Calendar className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
                Automated Schedules & Timers
                <Badge variant="info" size="sm">
                  {station.name}
                </Badge>
              </h2>
              <p className="text-xs text-slate-400">
                Configure deterministic time-of-day motor automation with built-in Phase 10 safety overrides.
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

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {error && (
            <div className="flex items-center gap-3 p-4 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-sm">
              <AlertCircle className="w-5 h-5 flex-shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          {successMsg && (
            <div className="flex items-center gap-3 p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-sm">
              <CheckCircle2 className="w-5 h-5 flex-shrink-0 text-emerald-400" />
              <span>{successMsg}</span>
            </div>
          )}

          {/* Action Bar */}
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-slate-200">
              Active Schedules ({schedules.length})
            </h3>
            {canManageSchedules && !isCreating && (
              <Button
                variant="primary"
                size="sm"
                icon={<Plus className="w-4 h-4" />}
                onClick={() => setIsCreating(true)}
              >
                New Schedule
              </Button>
            )}
          </div>

          {/* New Schedule Form */}
          {isCreating && (
            <form onSubmit={handleCreate} className="p-5 rounded-2xl bg-slate-950/60 border border-cyan-500/30 space-y-4 animate-in fade-in-50 duration-150">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <span className="text-sm font-semibold text-cyan-400 flex items-center gap-2">
                  <Plus className="w-4 h-4" /> Define New Schedule
                </span>
                <button
                  type="button"
                  onClick={() => setIsCreating(false)}
                  className="text-xs text-slate-400 hover:text-slate-200"
                >
                  Cancel
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">Schedule Name</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g., Morning Overhead Tank Fill"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-700 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">Target Motor</label>
                  <select
                    value={selectedMotorId}
                    onChange={(e) => setSelectedMotorId(e.target.value)}
                    className="w-full px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-700 text-sm text-slate-200 focus:outline-none focus:border-cyan-500"
                  >
                    {motors.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name} ({m.motor_code}) — {m.status}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Days of Week Selection */}
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">Repeat Days</label>
                <div className="flex flex-wrap gap-2">
                  {ALL_DAYS.map((d) => {
                    const isSelected = selectedDays.includes(d.key);
                    return (
                      <button
                        type="button"
                        key={d.key}
                        onClick={() => toggleDay(d.key)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                          isSelected
                            ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm shadow-cyan-500/20'
                            : 'bg-slate-900 text-slate-400 border border-slate-800 hover:border-slate-700'
                        }`}
                      >
                        {d.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">Start Time (HH:MM)</label>
                  <input
                    type="time"
                    required
                    value={startTime}
                    onChange={(e) => setStartTime(e.target.value)}
                    className="w-full px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-700 text-sm text-slate-200 focus:outline-none focus:border-cyan-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">Duration (Minutes)</label>
                  <input
                    type="number"
                    min="1"
                    max="1440"
                    required
                    value={durationMinutes}
                    onChange={(e) => setDurationMinutes(parseInt(e.target.value) || 30)}
                    className="w-full px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-700 text-sm text-slate-200 focus:outline-none focus:border-cyan-500"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setIsCreating(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  loading={submitting}
                  icon={<Check className="w-4 h-4" />}
                >
                  Save Schedule
                </Button>
              </div>
            </form>
          )}

          {/* Schedule List */}
          {loading ? (
            <div className="py-12 text-center text-slate-400 space-y-2">
              <RotateCcw className="w-6 h-6 animate-spin mx-auto text-cyan-400" />
              <p className="text-xs">Loading station schedules...</p>
            </div>
          ) : schedules.length === 0 ? (
            <div className="py-12 text-center text-slate-400 border border-dashed border-slate-800 rounded-2xl bg-slate-950/30">
              <Calendar className="w-8 h-8 mx-auto text-slate-500 mb-2" />
              <p className="text-sm font-medium text-slate-300">No schedules configured</p>
              <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1">
                Create scheduled timers to automatically start and stop pumps on defined days and times.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {schedules.map((s) => {
                const targetMotor = motors.find((m) => m.id === s.motor_id);
                return (
                  <div
                    key={s.id}
                    className={`p-4 rounded-2xl border transition-all flex flex-col md:flex-row md:items-center justify-between gap-4 ${
                      s.is_active
                        ? 'bg-slate-950/40 border-slate-800 hover:border-slate-700'
                        : 'bg-slate-950/20 border-slate-900 opacity-60'
                    }`}
                  >
                    <div className="space-y-2">
                      <div className="flex items-center gap-2.5">
                        <span className="text-sm font-semibold text-slate-200">{s.name}</span>
                        <Badge variant={s.is_active ? 'success' : 'neutral'} size="sm">
                          {s.is_active ? 'ACTIVE' : 'INACTIVE'}
                        </Badge>
                        {targetMotor && (
                          <Badge variant="info" size="sm">
                            {targetMotor.name} ({targetMotor.motor_code})
                          </Badge>
                        )}
                      </div>

                      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400">
                        <span className="flex items-center gap-1 text-cyan-300">
                          <Clock className="w-3.5 h-3.5" />
                          {s.start_time} UTC
                        </span>
                        <span>•</span>
                        <span>Duration: {Math.round(s.duration_seconds / 60)} min</span>
                        <span>•</span>
                        <div className="flex gap-1">
                          {s.days_of_week.map((d) => (
                            <span
                              key={d}
                              className="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300 font-mono"
                            >
                              {d}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>

                    {canManageSchedules && (
                      <div className="flex items-center gap-2 self-end md:self-center">
                        <button
                          type="button"
                          onClick={() => handleToggleActive(s)}
                          className={`px-3 py-1.5 rounded-xl text-xs font-medium border transition-colors ${
                            s.is_active
                              ? 'bg-amber-500/10 text-amber-300 border-amber-500/30 hover:bg-amber-500/20'
                              : 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30 hover:bg-emerald-500/20'
                          }`}
                        >
                          {s.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(s.id, s.name)}
                          className="p-2 rounded-xl text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                          title="Delete Schedule"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {!canManageSchedules && (
            <div className="p-3.5 rounded-2xl bg-slate-950/40 border border-slate-800/80 flex items-center gap-2 text-xs text-slate-400">
              <ShieldAlert className="w-4 h-4 text-amber-400 flex-shrink-0" />
              <span>
                Schedule configuration requires Site Manager, Organization Admin, or Super Admin privileges.
              </span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-800 bg-slate-900/50 flex justify-end">
          <Button variant="secondary" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
};
