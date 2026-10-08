import React, { useState, useEffect } from 'react';
import {
  X,
  Clock,
  Plus,
  Trash2,
  CheckCircle2,
  AlertCircle,
  RotateCcw,
  Check,
  Calendar,
  Power,
} from 'lucide-react';
import { Station, Motor, ScheduleResponse, ScheduleCreateRequest } from '../types';
import { api } from '../services/api';

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
  const [schedules, setSchedules] = useState<ScheduleResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const [scheduleToDelete, setScheduleToDelete] = useState<ScheduleResponse | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  // New Schedule Form State
  const [isCreating, setIsCreating] = useState<boolean>(false);
  const [name, setName] = useState<string>('');
  const [selectedMotorId, setSelectedMotorId] = useState<string>('');
  const [selectedDays, setSelectedDays] = useState<string[]>([
    'MON',
    'TUE',
    'WED',
    'THU',
    'FRI',
    'SAT',
    'SUN',
  ]);
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
    try {
      setError(null);
      const updated = await api.updateSchedule(station.id, schedule.id, {
        is_active: !schedule.is_active,
      });
      setSchedules((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
      setSuccessMsg(
        `Schedule "${schedule.name}" ${updated.is_active ? 'activated' : 'deactivated'}.`
      );
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to update schedule status.');
    }
  };

  const confirmDeleteSchedule = async () => {
    if (!scheduleToDelete) return;
    try {
      setIsDeleting(true);
      setError(null);
      await api.deleteSchedule(station.id, scheduleToDelete.id);
      setSchedules((prev) => prev.filter((s) => s.id !== scheduleToDelete.id));
      setSuccessMsg(`Schedule "${scheduleToDelete.name}" deleted successfully.`);
      setScheduleToDelete(null);
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to delete schedule.');
    } finally {
      setIsDeleting(false);
    }
  };

  const toggleDay = (dayKey: string) => {
    setSelectedDays((prev) =>
      prev.includes(dayKey) ? prev.filter((d) => d !== dayKey) : [...prev, dayKey]
    );
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();

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
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-slate-950/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg bg-white sm:rounded-[28px] rounded-t-[28px] border border-slate-200/80 shadow-2xl overflow-hidden flex flex-col max-h-[92vh] font-['Plus_Jakarta_Sans',sans-serif]">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 bg-slate-50/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-teal-50 text-teal-700 flex items-center justify-center shadow-xs">
              <Clock className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-black text-slate-900 tracking-tight leading-tight">
                Daily Pump Schedules
              </h2>
              <p className="text-xs text-slate-400 font-medium">
                {station.name} &bull; Automated Timers
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4">
          {error && (
            <div className="flex items-center gap-2 p-3 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-semibold">
              <AlertCircle className="w-4 h-4 flex-shrink-0 text-rose-500" />
              <span>{error}</span>
            </div>
          )}

          {successMsg && (
            <div className="flex items-center gap-2 p-3 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-semibold">
              <CheckCircle2 className="w-4 h-4 flex-shrink-0 text-emerald-500" />
              <span>{successMsg}</span>
            </div>
          )}

          {/* Action Header */}
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-black uppercase tracking-wider text-slate-400">
              Configured Timers ({schedules.length})
            </h3>
            {!isCreating && (
              <button
                type="button"
                onClick={() => setIsCreating(true)}
                className="px-3 py-1.5 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold flex items-center gap-1 shadow-md shadow-teal-600/20 transition-all"
              >
                <Plus className="w-3.5 h-3.5 stroke-[3]" />
                <span>Add Timer</span>
              </button>
            )}
          </div>

          {/* New Schedule Form Card */}
          {isCreating && (
            <form
              onSubmit={handleCreate}
              className="p-4 rounded-2xl bg-teal-50/40 border border-teal-200/80 space-y-3.5 animate-in fade-in duration-150"
            >
              <div className="flex items-center justify-between border-b border-teal-200/60 pb-2">
                <span className="text-xs font-black uppercase tracking-wider text-teal-800 flex items-center gap-1.5">
                  <Plus className="w-3.5 h-3.5 stroke-[3]" /> Create New Timer
                </span>
                <button
                  type="button"
                  onClick={() => setIsCreating(false)}
                  className="text-xs font-bold text-slate-400 hover:text-slate-600"
                >
                  Cancel
                </button>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-700 mb-1">
                  Schedule Title
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Morning Tank Fill"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-white border border-slate-200 text-xs font-semibold text-slate-900 placeholder-slate-400 focus:outline-none focus:border-teal-500 shadow-xs"
                />
              </div>

              {motors.length > 1 && (
                <div>
                  <label className="block text-[11px] font-bold text-slate-700 mb-1">
                    Target Motor
                  </label>
                  <select
                    value={selectedMotorId}
                    onChange={(e) => setSelectedMotorId(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-white border border-slate-200 text-xs font-semibold text-slate-900 focus:outline-none focus:border-teal-500 shadow-xs"
                  >
                    {motors.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name} ({m.motor_code})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Day Selection Pills */}
              <div>
                <label className="block text-[11px] font-bold text-slate-700 mb-1.5">
                  Repeat Days
                </label>
                <div className="grid grid-cols-7 gap-1">
                  {ALL_DAYS.map((d) => {
                    const isSelected = selectedDays.includes(d.key);
                    return (
                      <button
                        type="button"
                        key={d.key}
                        onClick={() => toggleDay(d.key)}
                        className={`py-1.5 rounded-lg text-[11px] font-bold transition-all text-center ${
                          isSelected
                            ? 'bg-teal-600 text-white shadow-xs'
                            : 'bg-white text-slate-400 border border-slate-200 hover:text-slate-700'
                        }`}
                      >
                        {d.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2.5">
                <div>
                  <label className="block text-[11px] font-bold text-slate-700 mb-1">
                    Start Time
                  </label>
                  <input
                    type="time"
                    required
                    value={startTime}
                    onChange={(e) => setStartTime(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-white border border-slate-200 text-xs font-semibold text-slate-900 focus:outline-none focus:border-teal-500 shadow-xs"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-slate-700 mb-1">
                    Duration (Minutes)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="1440"
                    required
                    value={durationMinutes}
                    onChange={(e) => setDurationMinutes(parseInt(e.target.value) || 30)}
                    className="w-full px-3 py-2 rounded-xl bg-white border border-slate-200 text-xs font-semibold text-slate-900 focus:outline-none focus:border-teal-500 shadow-xs"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setIsCreating(false)}
                  className="px-3 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold flex items-center gap-1 shadow-md shadow-teal-600/25 transition-all"
                >
                  <Check className="w-3.5 h-3.5 stroke-[3]" />
                  <span>{submitting ? 'Saving...' : 'Save Timer'}</span>
                </button>
              </div>
            </form>
          )}

          {/* Schedule List */}
          {loading ? (
            <div className="py-10 text-center text-slate-400 space-y-2">
              <RotateCcw className="w-6 h-6 animate-spin mx-auto text-teal-600" />
              <p className="text-xs font-semibold">Loading timer schedules...</p>
            </div>
          ) : schedules.length === 0 ? (
            <div className="py-10 text-center border-2 border-dashed border-slate-200 rounded-2xl p-6 space-y-2">
              <Calendar className="w-8 h-8 text-slate-300 mx-auto" />
              <p className="text-sm font-bold text-slate-800">No automated timers configured</p>
              <p className="text-xs text-slate-400 max-w-xs mx-auto">
                Set daily schedules to automatically start and stop your water pump with built-in safety cutoff.
              </p>
              <button
                type="button"
                onClick={() => setIsCreating(true)}
                className="mt-2 px-3.5 py-1.5 rounded-xl bg-teal-50 text-teal-700 font-bold text-xs hover:bg-teal-100 transition-colors"
              >
                + Create First Timer
              </button>
            </div>
          ) : (
            <div className="space-y-2.5">
              {schedules.map((s) => (
                <div
                  key={s.id}
                  className={`p-3.5 rounded-2xl border transition-all flex items-center justify-between gap-3 ${
                    s.is_active
                      ? 'bg-white border-slate-200/80 shadow-xs'
                      : 'bg-slate-50 border-slate-200/50 opacity-60'
                  }`}
                >
                  <div className="space-y-1 min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-slate-900 truncate">{s.name}</span>
                      <span
                        className={`px-2 py-0.5 rounded-md text-[10px] font-extrabold ${
                          s.is_active
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : 'bg-slate-100 text-slate-500'
                        }`}
                      >
                        {s.is_active ? 'ACTIVE' : 'DISABLED'}
                      </span>
                    </div>

                    <div className="text-[11px] text-slate-500 font-medium flex items-center gap-1.5 flex-wrap">
                      <span className="font-bold text-teal-700 flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {s.start_time}
                      </span>
                      <span>&bull;</span>
                      <span>{Math.round(s.duration_seconds / 60)} mins</span>
                      <span>&bull;</span>
                      <span className="font-mono text-[10px] text-slate-400">
                        [{s.days_of_week.join(', ')}]
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    <button
                      type="button"
                      onClick={() => handleToggleActive(s)}
                      title={s.is_active ? 'Deactivate Timer' : 'Activate Timer'}
                      className={`px-2.5 py-1.5 rounded-xl text-xs font-bold flex items-center gap-1 transition-colors ${
                        s.is_active
                          ? 'bg-slate-100 hover:bg-slate-200 text-slate-700'
                          : 'bg-emerald-50 hover:bg-emerald-100 text-emerald-700'
                      }`}
                    >
                      <Power className="w-3 h-3 stroke-[2.5]" />
                      <span>{s.is_active ? 'Pause' : 'Enable'}</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setScheduleToDelete(s)}
                      className="p-1.5 rounded-xl text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                      title="Delete Timer"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-slate-100 bg-slate-50/50 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold shadow-xs transition-colors"
          >
            Done
          </button>
        </div>
      </div>

      {/* Custom Mobile Delete Confirmation Popup */}
      {scheduleToDelete && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="relative w-full max-w-sm bg-white rounded-[24px] border border-slate-200/90 p-5 shadow-2xl space-y-4 animate-in zoom-in-95 duration-150">
            <div className="flex items-start gap-3.5">
              <div className="w-11 h-11 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center flex-shrink-0 shadow-xs border border-rose-100">
                <Trash2 className="w-5 h-5" />
              </div>
              <div className="space-y-1 min-w-0">
                <h3 className="text-base font-black text-slate-900 tracking-tight leading-tight">
                  Delete Timer Schedule?
                </h3>
                <p className="text-xs text-slate-500 leading-relaxed">
                  Are you sure you want to remove <span className="font-bold text-slate-800">"{scheduleToDelete.name}"</span>? Automated pump cycles for this slot will be permanently stopped.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2.5 pt-1">
              <button
                type="button"
                onClick={() => setScheduleToDelete(null)}
                disabled={isDeleting}
                className="py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmDeleteSchedule}
                disabled={isDeleting}
                className="py-2.5 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold shadow-md shadow-rose-600/25 transition-all flex items-center justify-center gap-1.5"
              >
                {isDeleting ? (
                  <RotateCcw className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Trash2 className="w-3.5 h-3.5" />
                )}
                <span>{isDeleting ? 'Deleting...' : 'Delete'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
