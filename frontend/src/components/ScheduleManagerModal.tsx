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
  Zap,
} from 'lucide-react';
import { Station, Motor, ScheduleResponse, ScheduleCreateRequest } from '../types';
import { api } from '../services/api';
import { useLanguage } from '../context/LanguageContext';

interface ScheduleManagerModalProps {
  isOpen: boolean;
  onClose: () => void;
  station: Station;
  motors: Motor[];
}

export const ScheduleManagerModal: React.FC<ScheduleManagerModalProps> = ({
  isOpen,
  onClose,
  station,
  motors,
}) => {
  const { t, language } = useLanguage();
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
      if (motors.length > 0 && (!selectedMotorId || !motors.some((m) => m.id === selectedMotorId))) {
        setSelectedMotorId(motors[0].id);
      }
    }
  }, [isOpen, station.id, motors]);

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
      setError('Please select a target motor to start.');
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

  const allDays = [
    { key: 'MON', label: language === 'hi' ? 'सोम' : 'Mon' },
    { key: 'TUE', label: language === 'hi' ? 'मंगल' : 'Tue' },
    { key: 'WED', label: language === 'hi' ? 'बुध' : 'Wed' },
    { key: 'THU', label: language === 'hi' ? 'गुरु' : 'Thu' },
    { key: 'FRI', label: language === 'hi' ? 'शुक्र' : 'Fri' },
    { key: 'SAT', label: language === 'hi' ? 'शनि' : 'Sat' },
    { key: 'SUN', label: language === 'hi' ? 'रवि' : 'Sun' },
  ];

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-slate-950/60 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-lg bg-white sm:rounded-2xl rounded-t-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[90dvh] font-sans">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 bg-slate-50/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-blue-50 text-blue-700 flex items-center justify-center">
              <Clock className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-black text-slate-900 tracking-tight leading-tight">
                {language === 'hi' ? 'दैनिक पंप शेड्यूल' : 'Daily Pump Schedules'}
              </h2>
              <p className="text-xs text-slate-400 font-medium">
                {station.name} &bull; {language === 'hi' ? 'स्वचालित मोटर टाइमर' : 'Automated Motor Timers'}
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
              {language === 'hi'
                ? `कॉन्फ़िगर किए गए टाइमर (${schedules.length})`
                : `Configured Timers (${schedules.length})`}
            </h3>
            {!isCreating && (
              <button
                type="button"
                onClick={() => setIsCreating(true)}
                className="px-3 py-1.5 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold flex items-center gap-1 shadow-md shadow-teal-600/20 transition-all cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5 stroke-[3]" />
                <span>{language === 'hi' ? 'टाइमर जोड़ें' : 'Add Timer'}</span>
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
                  <Plus className="w-3.5 h-3.5 stroke-[3]" />{' '}
                  {language === 'hi' ? 'नया टाइमर बनाएं' : 'Create New Timer'}
                </span>
                <button
                  type="button"
                  onClick={() => setIsCreating(false)}
                  className="text-xs font-bold text-slate-400 hover:text-slate-600 cursor-pointer"
                >
                  {t.cancel}
                </button>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-700 mb-1">
                  {language === 'hi' ? 'शेड्यूल का नाम' : 'Schedule Title'}
                </label>
                <input
                  type="text"
                  required
                  placeholder={language === 'hi' ? 'उदा. सुबह टंकी भरना' : 'e.g. Morning Tank Fill'}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-white border border-slate-200 text-xs font-semibold text-slate-900 placeholder-slate-400 focus:outline-none focus:border-teal-500 shadow-xs"
                />
              </div>

              {/* Target Motor Selection (Always visible) */}
              <div>
                <label className="block text-[11px] font-bold text-slate-700 mb-1.5 flex items-center justify-between">
                  <span className="flex items-center gap-1 text-slate-900">
                    <Zap className="w-3.5 h-3.5 text-teal-600" />
                    <span>{language === 'hi' ? 'लक्ष्य मोटर' : 'Target Motor to Start'}</span>
                  </span>
                  <span className="text-[10px] text-slate-400 font-semibold">
                    {motors.length} {language === 'hi' ? 'मोटर यूनिट्स' : (motors.length === 1 ? 'Motor Unit' : 'Motor Units')}
                  </span>
                </label>
                {motors.length > 0 ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {motors.map((m) => {
                      const isSelected = selectedMotorId === m.id;
                      return (
                        <button
                          key={m.id}
                          type="button"
                          onClick={() => setSelectedMotorId(m.id)}
                          className={`p-2.5 rounded-xl border text-left transition-all flex items-center justify-between cursor-pointer ${
                            isSelected
                              ? 'bg-teal-600 text-white border-teal-600 shadow-sm ring-2 ring-teal-500/30'
                              : 'bg-white text-slate-700 border-slate-200 hover:border-teal-300 hover:bg-teal-50/40'
                          }`}
                        >
                          <div className="min-w-0 pr-2">
                            <div className={`text-xs font-bold truncate ${isSelected ? 'text-white' : 'text-slate-900'}`}>
                              {m.name}
                            </div>
                            <div className={`text-[10px] font-mono ${isSelected ? 'text-teal-100' : 'text-slate-400'}`}>
                              {m.motor_code} • {m.rated_power ? `${m.rated_power} kW` : '1.5 kW'}
                            </div>
                          </div>
                          <div className="flex items-center gap-1.5 flex-shrink-0">
                            <span
                              className={`w-2 h-2 rounded-full ${
                                m.status === 'ON' || m.status === 'STARTING'
                                  ? 'bg-emerald-400 animate-pulse'
                                  : m.status === 'FAULT'
                                  ? 'bg-rose-400'
                                  : isSelected
                                  ? 'bg-white/60'
                                  : 'bg-slate-300'
                              }`}
                            />
                            {isSelected && <Check className="w-3.5 h-3.5 text-white stroke-[3]" />}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <div className="p-2.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs">
                    {language === 'hi' ? 'इस स्टेशन के लिए कोई मोटर नहीं मिली।' : 'No motors found for this station.'}
                  </div>
                )}
              </div>

              {/* Day Selection Pills */}
              <div>
                <label className="block text-[11px] font-bold text-slate-700 mb-1.5">
                  {language === 'hi' ? 'पुनरावृत्ति दिन' : 'Repeat Days'}
                </label>
                <div className="grid grid-cols-7 gap-1">
                  {allDays.map((d) => {
                    const isSelected = selectedDays.includes(d.key);
                    return (
                      <button
                        type="button"
                        key={d.key}
                        onClick={() => toggleDay(d.key)}
                        className={`py-1.5 rounded-lg text-[11px] font-bold transition-all text-center cursor-pointer ${
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
                    {language === 'hi' ? 'शुरू समय' : 'Start Time'}
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
                    {language === 'hi' ? 'अवधि (मिनट)' : 'Duration (Minutes)'}
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
                  className="px-3 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-colors cursor-pointer"
                >
                  {t.cancel}
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold flex items-center gap-1 shadow-md shadow-teal-600/25 transition-all cursor-pointer"
                >
                  <Check className="w-3.5 h-3.5 stroke-[3]" />
                  <span>
                    {submitting ? t.saving : (language === 'hi' ? 'टाइमर सहेजें' : 'Save Timer')}
                  </span>
                </button>
              </div>
            </form>
          )}

          {/* Schedule List */}
          {loading ? (
            <div className="py-10 text-center text-slate-400 space-y-2">
              <RotateCcw className="w-6 h-6 animate-spin mx-auto text-teal-600" />
              <p className="text-xs font-semibold">
                {language === 'hi' ? 'टाइमर शेड्यूल लोड हो रहे हैं...' : 'Loading timer schedules...'}
              </p>
            </div>
          ) : schedules.length === 0 ? (
            <div className="py-10 text-center border-2 border-dashed border-slate-200 rounded-2xl p-6 space-y-2">
              <Calendar className="w-8 h-8 text-slate-300 mx-auto" />
              <p className="text-sm font-bold text-slate-800">
                {language === 'hi' ? 'कोई स्वचालित टाइमर कॉन्फ़िगर नहीं है' : 'No automated timers configured'}
              </p>
              <p className="text-xs text-slate-400 max-w-xs mx-auto">
                {language === 'hi'
                  ? 'सुरक्षा कट-ऑफ के साथ मोटर स्वचालित रूप से चालू/बंद करने के लिए दैनिक शेड्यूल सेट करें।'
                  : 'Set daily schedules to automatically start and stop your water pump with built-in safety cutoff.'}
              </p>
              <button
                type="button"
                onClick={() => setIsCreating(true)}
                className="mt-2 px-3.5 py-1.5 rounded-xl bg-teal-50 text-teal-700 font-bold text-xs hover:bg-teal-100 transition-colors cursor-pointer"
              >
                {language === 'hi' ? '+ पहला टाइमर बनाएं' : '+ Create First Timer'}
              </button>
            </div>
          ) : (
            <div className="space-y-2.5">
              {schedules.map((s) => {
                const targetMotor = motors.find((m) => m.id === s.motor_id);
                return (
                  <div
                    key={s.id}
                    className={`p-3.5 rounded-2xl border transition-all flex items-center justify-between gap-3 ${
                      s.is_active
                        ? 'bg-white border-slate-200/80 shadow-xs'
                        : 'bg-slate-50 border-slate-200/50 opacity-60'
                    }`}
                  >
                    <div className="space-y-1.5 min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-bold text-slate-900 truncate">{s.name}</span>
                        <span
                          className={`px-2 py-0.5 rounded-md text-[10px] font-extrabold ${
                            s.is_active
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : 'bg-slate-100 text-slate-500'
                          }`}
                        >
                          {s.is_active
                            ? (language === 'hi' ? 'सक्रिय' : 'ACTIVE')
                            : (language === 'hi' ? 'निष्क्रिय' : 'DISABLED')}
                        </span>
                        {targetMotor && (
                          <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-teal-50 text-teal-800 border border-teal-200/70 flex items-center gap-1 font-mono">
                            <Zap className="w-2.5 h-2.5 text-teal-600" />
                            {targetMotor.motor_code}
                          </span>
                        )}
                      </div>

                      <div className="text-[11px] text-slate-500 font-medium flex items-center gap-1.5 flex-wrap">
                        <span className="font-bold text-teal-700 flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {s.start_time}
                        </span>
                        <span>&bull;</span>
                        <span>
                          {Math.round(s.duration_seconds / 60)} {language === 'hi' ? 'मिनट' : 'mins'}
                        </span>
                        {targetMotor && (
                          <>
                            <span>&bull;</span>
                            <span className="text-slate-600 font-semibold">{targetMotor.name}</span>
                          </>
                        )}
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
                        className={`px-2.5 py-1.5 rounded-xl text-xs font-bold flex items-center gap-1 transition-colors cursor-pointer ${
                          s.is_active
                            ? 'bg-slate-100 hover:bg-slate-200 text-slate-700'
                            : 'bg-emerald-50 hover:bg-emerald-100 text-emerald-700'
                        }`}
                      >
                        <Power className="w-3 h-3 stroke-[2.5]" />
                        <span>
                          {s.is_active
                            ? (language === 'hi' ? 'रोकें' : 'Pause')
                            : (language === 'hi' ? 'चालू करें' : 'Enable')}
                        </span>
                      </button>
                      <button
                        type="button"
                        onClick={() => setScheduleToDelete(s)}
                        className="p-1.5 rounded-xl text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
                        title={language === 'hi' ? 'टाइमर हटाएं' : 'Delete Timer'}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-slate-100 bg-slate-50/50 flex justify-end pb-[max(0.75rem,env(safe-area-inset-bottom,0px))]">
          <button
            type="button"
            onClick={onClose}
            className="px-5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold shadow-xs transition-colors cursor-pointer"
          >
            {language === 'hi' ? 'पूर्ण' : 'Done'}
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
                  {language === 'hi' ? 'टाइमर शेड्यूल हटाएं?' : 'Delete Timer Schedule?'}
                </h3>
                <p className="text-xs text-slate-500 leading-relaxed">
                  {language === 'hi' ? (
                    <>
                      क्या आप <span className="font-bold text-slate-800">"{scheduleToDelete.name}"</span> को हटाना चाहते हैं? इस स्लॉट का स्वचालित मोटर चक्र स्थायी रूप से बंद हो जाएगा।
                    </>
                  ) : (
                    <>
                      Are you sure you want to remove <span className="font-bold text-slate-800">"{scheduleToDelete.name}"</span>? Automated pump cycles for this slot will be permanently stopped.
                    </>
                  )}
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2.5 pt-1">
              <button
                type="button"
                onClick={() => setScheduleToDelete(null)}
                disabled={isDeleting}
                className="py-2.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-colors cursor-pointer"
              >
                {t.cancel}
              </button>
              <button
                type="button"
                onClick={confirmDeleteSchedule}
                disabled={isDeleting}
                className="py-2.5 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold shadow-md shadow-rose-600/25 transition-all flex items-center justify-center gap-1.5 cursor-pointer"
              >
                {isDeleting ? (
                  <RotateCcw className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Trash2 className="w-3.5 h-3.5" />
                )}
                <span>
                  {isDeleting
                    ? (language === 'hi' ? 'हटाया जा रहा है...' : 'Deleting...')
                    : t.delete}
                </span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
