import React from 'react';
import {
  ArrowLeft,
  Calendar,
  Clock,
  Plus,
  Play,
  Pause,
  Trash2,
  Zap,
  RefreshCw,
} from 'lucide-react';
import { ScheduleResponse, Motor } from '../../types';
import { useLanguage } from '../../context/LanguageContext';

interface SchedulesScreenProps {
  onBack: () => void;
  schedules: ScheduleResponse[];
  motors: Motor[];
  activeMotor: Motor | null;
  onOpenAddSchedule: () => void;
  onToggleScheduleActive: (s: ScheduleResponse) => void;
  onDeleteSchedule: (s: ScheduleResponse) => void;
  onRefresh: () => void;
  isSyncing: boolean;
}

export const SchedulesScreen: React.FC<SchedulesScreenProps> = ({
  onBack,
  schedules,
  motors,
  activeMotor,
  onOpenAddSchedule,
  onToggleScheduleActive,
  onDeleteSchedule,
  onRefresh,
  isSyncing,
}) => {
  const { t, language } = useLanguage();
  const activeCount = schedules.filter((s) => s.is_active).length;

  return (
    <div className="space-y-4 animate-fade-in font-sans pb-dock-clearance">
      {/* Top Header Bar */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-100">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-all cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>{t.backToHome}</span>
        </button>

        <div className="flex items-center gap-2">
          <span className="px-2.5 py-1 rounded-xl bg-blue-50 border border-blue-200 text-[11px] font-black text-blue-700">
            {language === 'hi'
              ? `${activeCount} सक्रिय रूटीन`
              : `${activeCount} Active Routine${activeCount !== 1 ? 's' : ''}`}
          </span>
          <button
            type="button"
            onClick={onRefresh}
            className="p-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors cursor-pointer"
            title={language === 'hi' ? 'रीफ़्रेश करें' : 'Refresh Schedules'}
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin text-blue-600' : ''}`} />
          </button>
        </div>
      </div>

      {/* Hero Overview */}
      <div className="mobile-card p-4 bg-white border border-slate-200 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-2xl bg-blue-600 text-white flex items-center justify-center flex-shrink-0">
              <Calendar className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-base font-black text-slate-900 leading-tight">
                {t.schedulesTitle}
              </h2>
              <p className="text-xs text-slate-500 font-medium mt-0.5">
                {t.schedulesSubtitle}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onOpenAddSchedule}
            className="px-3.5 py-2 rounded-2xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-black flex items-center gap-1.5 transition-all cursor-pointer flex-shrink-0"
          >
            <Plus className="w-4 h-4 stroke-[3]" />
            <span>{t.addScheduleBtn}</span>
          </button>
        </div>
      </div>

      {/* List of Schedules */}
      <div className="space-y-2.5">
        <h3 className="text-xs font-black uppercase tracking-wider text-slate-400 px-1">
          {language === 'hi'
            ? `कॉन्फ़िगर किए गए शेड्यूल (${schedules.length})`
            : `Configured Schedules (${schedules.length})`}
        </h3>

        {schedules.length === 0 ? (
          <div className="mobile-card p-8 text-center text-xs text-slate-400 space-y-3">
            <Clock className="w-10 h-10 text-slate-300 mx-auto" />
            <div>
              <p className="font-bold text-slate-700">
                {language === 'hi' ? 'कोई स्वचालित शेड्यूल नहीं बनाया गया है।' : 'No automated schedules created yet.'}
              </p>
              <p className="text-[11px] text-slate-400 mt-0.5">
                {language === 'hi'
                  ? 'स्वचालित मोटर चलाने हेतु सुबह या शाम का दैनिक शेड्यूल सेट करें।'
                  : 'Set up a daily morning or evening routine to automatically run water pump.'}
              </p>
            </div>
            <button
              type="button"
              onClick={onOpenAddSchedule}
              className="px-4 py-2 rounded-2xl bg-blue-600 text-white font-bold text-xs cursor-pointer"
            >
              {language === 'hi' ? '+ पहला शेड्यूल बनाएं' : '+ Create First Schedule'}
            </button>
          </div>
        ) : (
          schedules.map((s) => {
            const targetMotor =
              motors.find((m) => m.id === s.motor_id) ||
              (activeMotor && activeMotor.id === s.motor_id ? activeMotor : null);
            return (
              <div
                key={s.id}
                className={`mobile-card p-3.5 flex flex-col justify-between gap-3 border transition-all ${
                  s.is_active
                    ? 'border-teal-200/80 bg-white'
                    : 'border-slate-200/80 bg-slate-50/70 opacity-80'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-start gap-2.5 min-w-0">
                    <span
                      className={`w-2.5 h-2.5 rounded-full mt-1 shrink-0 ${
                        s.is_active ? 'bg-emerald-500 shadow-xs' : 'bg-slate-300'
                      }`}
                    />
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-xs font-black text-slate-900">{s.name}</span>
                        {targetMotor && (
                          <span className="px-1.5 py-0.5 rounded bg-teal-50 text-teal-800 text-[10px] font-bold border border-teal-200/60 font-mono flex items-center gap-0.5">
                            <Zap className="w-2.5 h-2.5 text-teal-600" />
                            {targetMotor.motor_code}
                          </span>
                        )}
                      </div>
                      <div className="text-[11px] text-slate-500 font-medium mt-0.5">
                        {language === 'hi' ? 'शुरू समय:' : 'Starts at'}{' '}
                        <span className="font-bold text-slate-800">{s.start_time}</span> &bull;{' '}
                        {language === 'hi' ? 'अवधि:' : 'Runs for'}{' '}
                        <span className="font-bold text-slate-800">
                          {Math.round(s.duration_seconds / 60)} {language === 'hi' ? 'मिनट' : 'mins'}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Day Badges */}
                  <div className="flex items-center gap-0.5 flex-wrap justify-end">
                    {[
                      { en: 'M', hi: 'सो', key: 'MON' },
                      { en: 'T', hi: 'मं', key: 'TUE' },
                      { en: 'W', hi: 'बु', key: 'WED' },
                      { en: 'T', hi: 'गु', key: 'THU' },
                      { en: 'F', hi: 'शु', key: 'FRI' },
                      { en: 'S', hi: 'श', key: 'SAT' },
                      { en: 'S', hi: 'र', key: 'SUN' },
                    ].map((d) => {
                      const isIncluded = s.days_of_week?.includes(d.key);
                      return (
                        <span
                          key={d.key}
                          className={`text-[9px] font-bold px-1 py-0.5 rounded ${
                            isIncluded
                              ? 'bg-teal-100 text-teal-800'
                              : 'text-slate-300'
                          }`}
                        >
                          {language === 'hi' ? d.hi : d.en}
                        </span>
                      );
                    })}
                  </div>
                </div>

                {/* Footer Actions */}
                <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-xs">
                  <button
                    type="button"
                    onClick={() => onToggleScheduleActive(s)}
                    className={`px-3 py-1.5 rounded-xl font-bold flex items-center gap-1.5 transition-all text-[11px] cursor-pointer ${
                      s.is_active
                        ? 'bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200'
                        : 'bg-slate-200 hover:bg-slate-300 text-slate-700'
                    }`}
                  >
                    {s.is_active ? (
                      <>
                        <Pause className="w-3 h-3 fill-current" />
                        <span>
                          {language === 'hi' ? 'सक्रिय (रोकने हेतु टैप करें)' : 'Active (Tap to Pause)'}
                        </span>
                      </>
                    ) : (
                      <>
                        <Play className="w-3 h-3 fill-current" />
                        <span>
                          {language === 'hi' ? 'रुका हुआ (चालू करने हेतु टैप करें)' : 'Paused (Tap to Resume)'}
                        </span>
                      </>
                    )}
                  </button>

                  <button
                    type="button"
                    onClick={() => onDeleteSchedule(s)}
                    title={language === 'hi' ? 'शेड्यूल हटाएं' : 'Delete Schedule'}
                    className="p-1.5 rounded-xl text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
