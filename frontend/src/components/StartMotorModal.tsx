import React, { useState, useMemo } from 'react';
import {
  Power,
  Clock,
  Timer,
  Zap,
  ShieldCheck,
  X,
  Play,
  Sliders,
} from 'lucide-react';
import { Motor } from '../types';
import { useLanguage } from '../context/LanguageContext';

interface StartMotorModalProps {
  isOpen: boolean;
  onClose: () => void;
  motor: Motor | null;
  onConfirmStart: (durationMinutes: number) => Promise<void>;
  isProcessing: boolean;
}

export const StartMotorModal: React.FC<StartMotorModalProps> = ({
  isOpen,
  onClose,
  motor,
  onConfirmStart,
  isProcessing,
}) => {
  const { t, language } = useLanguage();
  const [selectedMinutes, setSelectedMinutes] = useState<number>(30);
  const [isCustom, setIsCustom] = useState<boolean>(false);
  const [customMinutesInput, setCustomMinutesInput] = useState<number>(30);

  const presets = useMemo(() => [
    { label: t.preset15m, minutes: 15, sub: t.presetSubFast },
    { label: t.preset30m, minutes: 30, sub: t.presetSubStandard },
    { label: t.preset45m, minutes: 45, sub: t.presetSubTopup },
    { label: t.preset60m, minutes: 60, sub: t.presetSubFull },
    { label: t.preset90m, minutes: 90, sub: t.presetSubHeavy },
    { label: t.presetCustom, minutes: 0, sub: t.presetSubUser },
  ], [t]);

  // Calculate live projected auto-stop time in local timezone
  const closingTimeFormatted = useMemo(() => {
    const mins = isCustom ? customMinutesInput : selectedMinutes;
    if (mins <= 0) return language === 'hi' ? 'मैन्युअल बंद करना होगा' : 'Manual Stop Required';
    const stopDate = new Date(Date.now() + mins * 60 * 1000);
    return stopDate.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  }, [selectedMinutes, isCustom, customMinutesInput, language]);

  if (!isOpen || !motor) return null;

  const handleSelectPreset = (mins: number) => {
    if (mins === 0) {
      setIsCustom(true);
    } else {
      setIsCustom(false);
      setSelectedMinutes(mins);
      setCustomMinutesInput(mins);
    }
  };

  const handleStart = async () => {
    const finalMinutes = isCustom ? customMinutesInput : selectedMinutes;
    await onConfirmStart(finalMinutes);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-3 sm:p-4 animate-fade-in font-sans">
      <div className="w-full max-w-md bg-white rounded-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[calc(100dvh-1.5rem)] shadow-2xl animate-scale-up">
        {/* Header */}
        <div className="shrink-0 p-3.5 sm:p-4 bg-slate-900 text-white flex items-center justify-between border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-slate-800 border border-slate-700/80">
              <Power className="w-4 h-4 text-emerald-400 stroke-[2.5]" />
            </div>
            <div>
              <h2 className="text-xs sm:text-sm font-bold tracking-tight leading-tight text-white">
                {t.startPumpWithTimer}
              </h2>
              <p className="text-[11px] text-slate-400 font-medium">
                {t.autoCutoffScheduleSub}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            disabled={isProcessing}
            className="p-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors cursor-pointer border border-slate-700"
            aria-label="Close dialog"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto overscroll-contain p-3.5 sm:p-4 space-y-4">
          {/* Target Motor Badge Card */}
          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-between">
            <div className="flex items-center gap-2.5 min-w-0">
              <span className="p-1.5 rounded-lg bg-blue-50 border border-blue-200 text-blue-700">
                <Zap className="w-4 h-4" />
              </span>
              <div className="min-w-0">
                <div className="text-xs font-bold text-slate-900 truncate">
                  {motor.name}
                </div>
                <div className="text-[10px] font-mono font-medium text-slate-500">
                  {motor.motor_code}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-1 text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-lg border border-emerald-200/80">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              <span>{t.safetyOk}</span>
            </div>
          </div>

          {/* Section: Select Closing Duration */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs font-bold text-slate-700 uppercase tracking-wider">
              <div className="flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-slate-500" />
                <span>{t.runtimeDuration}</span>
              </div>
              <span className="text-xs text-blue-700 font-bold font-mono">
                {isCustom ? `${customMinutesInput} min` : `${selectedMinutes} min`}
              </span>
            </div>

            {/* Duration Preset Chips Grid */}
            <div className="grid grid-cols-3 gap-2">
              {presets.map((preset) => {
                const isSelected =
                  preset.minutes === 0
                    ? isCustom
                    : !isCustom && selectedMinutes === preset.minutes;

                return (
                  <button
                    key={preset.label}
                    type="button"
                    onClick={() => handleSelectPreset(preset.minutes)}
                    className={`p-2.5 rounded-xl border text-left transition-all relative cursor-pointer ${
                      isSelected
                        ? 'bg-blue-50/80 border-blue-500 ring-1 ring-blue-500/20'
                        : 'bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                    }`}
                  >
                    <div
                      className={`text-xs font-bold ${
                        isSelected ? 'text-blue-900' : 'text-slate-800'
                      }`}
                    >
                      {preset.label}
                    </div>
                    <div
                      className={`text-[10px] font-medium truncate ${
                        isSelected ? 'text-blue-600' : 'text-slate-400'
                      }`}
                    >
                      {preset.sub}
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Custom Minutes Slider & Input */}
            {isCustom && (
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-2.5 mt-2 animate-fade-in">
                <div className="flex items-center justify-between text-xs font-bold text-slate-800">
                  <span className="flex items-center gap-1.5">
                    <Sliders className="w-3.5 h-3.5 text-slate-500" />
                    <span>{t.customCutoffTimer}:</span>
                  </span>
                  <span className="font-mono text-sm font-bold text-blue-700">
                    {customMinutesInput} min
                  </span>
                </div>

                <input
                  type="range"
                  min="1"
                  max="180"
                  step="1"
                  value={customMinutesInput}
                  onChange={(e) => setCustomMinutesInput(Number(e.target.value))}
                  className="w-full accent-blue-600 cursor-pointer h-2 bg-slate-200 rounded-lg"
                />

                <div className="flex justify-between text-[10px] font-semibold text-slate-400 font-mono">
                  <span>1m</span>
                  <span>45m</span>
                  <span>90m</span>
                  <span>180m</span>
                </div>
              </div>
            )}
          </div>

          {/* Live Scheduled Auto-Stop Time Indicator Card */}
          <div className="p-3 rounded-xl bg-blue-50/60 border border-blue-200/80 flex items-center justify-between gap-2">
            <div className="space-y-0.5 min-w-0">
              <div className="text-[10px] font-bold uppercase tracking-wider text-blue-900 flex items-center gap-1">
                <Timer className="w-3 h-3 text-blue-600" />
                <span>{t.scheduledAutoCutoff}</span>
              </div>
              <div className="text-[11px] text-slate-600 leading-snug">
                {language === 'hi'
                  ? `मोटर ${isCustom ? customMinutesInput : selectedMinutes} मिनट तक चलेगी फिर अपने आप बंद हो जाएगी।`
                  : `Pump will run for ${isCustom ? customMinutesInput : selectedMinutes} min then shut off automatically.`}
              </div>
            </div>

            <div className="text-right flex-shrink-0">
              <div className="text-sm font-bold text-blue-950 font-mono">
                {closingTimeFormatted}
              </div>
              <div className="text-[9px] font-bold text-blue-600 uppercase tracking-wide">
                {t.targetTime}
              </div>
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="shrink-0 p-3.5 sm:p-4 bg-slate-50 border-t border-slate-200/80 flex items-center gap-2.5 pb-[max(0.875rem,env(safe-area-inset-bottom,0px))]">
          <button
            type="button"
            onClick={onClose}
            disabled={isProcessing}
            className="flex-1 py-2.5 px-4 rounded-xl bg-white border border-slate-200 hover:bg-slate-100 text-slate-700 text-xs font-semibold transition-colors disabled:opacity-50 cursor-pointer"
          >
            {t.cancel}
          </button>

          <button
            type="button"
            onClick={handleStart}
            disabled={isProcessing}
            className="flex-2 py-2.5 px-4 rounded-xl bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white text-xs font-bold flex items-center justify-center gap-2 transition-colors disabled:opacity-50 cursor-pointer shadow-sm"
          >
            <Play className="w-4 h-4 fill-current" />
            <span>
              {isProcessing
                ? t.starting
                : `${t.startBtn} (${isCustom ? customMinutesInput : selectedMinutes} MIN)`}
            </span>
          </button>
        </div>
      </div>
    </div>
  );
};
