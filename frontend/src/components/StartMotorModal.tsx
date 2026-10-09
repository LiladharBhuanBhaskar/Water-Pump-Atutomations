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

interface StartMotorModalProps {
  isOpen: boolean;
  onClose: () => void;
  motor: Motor | null;
  onConfirmStart: (durationMinutes: number) => Promise<void>;
  isProcessing: boolean;
}

const PRESET_DURATIONS = [
  { label: '15m', minutes: 15, sub: 'Short cycle' },
  { label: '30m', minutes: 30, sub: 'Standard (Default)' },
  { label: '45m', minutes: 45, sub: 'Deep irrigation' },
  { label: '1h', minutes: 60, sub: 'Full cycle' },
  { label: '2h', minutes: 120, sub: 'Extended fill' },
  { label: 'Custom', minutes: 0, sub: 'Set any time' },
];

export const StartMotorModal: React.FC<StartMotorModalProps> = ({
  isOpen,
  onClose,
  motor,
  onConfirmStart,
  isProcessing,
}) => {
  const [selectedMinutes, setSelectedMinutes] = useState<number>(30);
  const [isCustom, setIsCustom] = useState<boolean>(false);
  const [customMinutesInput, setCustomMinutesInput] = useState<number>(30);

  // Calculate live projected auto-stop time in local timezone
  const closingTimeFormatted = useMemo(() => {
    const mins = isCustom ? customMinutesInput : selectedMinutes;
    if (mins <= 0) return 'Manual Stop Required';
    const stopDate = new Date(Date.now() + mins * 60 * 1000);
    return stopDate.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  }, [selectedMinutes, isCustom, customMinutesInput]);

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm p-4 animate-fade-in">
      <div className="w-full max-w-md bg-white rounded-3xl shadow-2xl border border-slate-100 overflow-hidden font-['Plus_Jakarta_Sans',sans-serif] animate-scale-up">
        {/* Header */}
        <div className="p-4 bg-gradient-to-r from-teal-600 via-teal-700 to-cyan-700 text-white flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-2xl bg-white/15 backdrop-blur-md">
              <Power className="w-5 h-5 text-teal-200 stroke-[2.5]" />
            </div>
            <div>
              <h2 className="text-sm font-black tracking-tight leading-tight">
                START PUMP WITH TIMER
              </h2>
              <p className="text-[11px] text-teal-100 font-medium">
                Schedule auto-closing time &amp; runtime safety
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            disabled={isProcessing}
            className="p-1.5 rounded-xl bg-white/10 hover:bg-white/20 text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-4 space-y-4">
          {/* Target Motor Badge Card */}
          <div className="p-3 rounded-2xl bg-slate-50 border border-slate-100 flex items-center justify-between">
            <div className="flex items-center gap-2 min-w-0">
              <span className="p-1.5 rounded-xl bg-teal-100 text-teal-800">
                <Zap className="w-4 h-4" />
              </span>
              <div className="min-w-0">
                <div className="text-xs font-black text-slate-900 truncate">
                  {motor.name}
                </div>
                <div className="text-[10px] font-mono font-bold text-teal-700">
                  {motor.motor_code}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-1 text-[11px] font-extrabold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-xl border border-emerald-200">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Safety OK</span>
            </div>
          </div>

          {/* Section: Select Closing Duration */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs font-black text-slate-800 uppercase tracking-tight">
              <div className="flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-teal-600" />
                <span>SELECT CLOSING DURATION</span>
              </div>
              <span className="text-[11px] text-teal-700 font-bold font-mono">
                {isCustom ? `${customMinutesInput} min` : `${selectedMinutes} min`}
              </span>
            </div>

            {/* Duration Preset Chips Grid */}
            <div className="grid grid-cols-3 gap-2">
              {PRESET_DURATIONS.map((preset) => {
                const isSelected =
                  preset.minutes === 0
                    ? isCustom
                    : !isCustom && selectedMinutes === preset.minutes;

                return (
                  <button
                    key={preset.label}
                    type="button"
                    onClick={() => handleSelectPreset(preset.minutes)}
                    className={`p-2.5 rounded-2xl border text-left transition-all relative ${
                      isSelected
                        ? 'bg-teal-50 border-teal-500 ring-2 ring-teal-500/20 shadow-xs'
                        : 'bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/50'
                    }`}
                  >
                    <div
                      className={`text-xs font-black ${
                        isSelected ? 'text-teal-900' : 'text-slate-800'
                      }`}
                    >
                      {preset.label}
                    </div>
                    <div
                      className={`text-[9px] font-medium truncate ${
                        isSelected ? 'text-teal-700' : 'text-slate-400'
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
              <div className="p-3 rounded-2xl bg-teal-50/50 border border-teal-200/80 space-y-2.5 mt-2 animate-fade-in">
                <div className="flex items-center justify-between text-xs font-bold text-teal-950">
                  <span className="flex items-center gap-1">
                    <Sliders className="w-3.5 h-3.5 text-teal-600" />
                    <span>Custom Auto-Stop Duration:</span>
                  </span>
                  <span className="font-mono text-sm font-black text-teal-800">
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
                  className="w-full accent-teal-600 cursor-pointer h-2 bg-slate-200 rounded-lg"
                />

                <div className="flex justify-between text-[10px] font-bold text-slate-400">
                  <span>1 min</span>
                  <span>45 min</span>
                  <span>90 min</span>
                  <span>180 min (3h)</span>
                </div>
              </div>
            )}
          </div>

          {/* Live Scheduled Auto-Stop Time Indicator Card */}
          <div className="p-3.5 rounded-2xl bg-gradient-to-r from-teal-50 via-cyan-50 to-teal-50 border border-teal-200/80 flex items-center justify-between gap-2 shadow-xs">
            <div className="space-y-0.5 min-w-0">
              <div className="text-[10px] font-extrabold uppercase tracking-wider text-teal-700 flex items-center gap-1">
                <Timer className="w-3 h-3 text-teal-600" />
                <span>Scheduled Auto-Closing Time</span>
              </div>
              <div className="text-xs text-slate-600 font-medium">
                Pump will run for {isCustom ? customMinutesInput : selectedMinutes} minutes and automatically turn off.
              </div>
            </div>

            <div className="text-right flex-shrink-0">
              <div className="text-sm font-black text-teal-900 font-mono">
                {closingTimeFormatted}
              </div>
              <div className="text-[9px] font-bold text-teal-600 uppercase">
                Real Local Time
              </div>
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 bg-slate-50 border-t border-slate-100 flex items-center gap-2.5">
          <button
            type="button"
            onClick={onClose}
            disabled={isProcessing}
            className="flex-1 py-3 px-4 rounded-2xl bg-white border border-slate-200 hover:bg-slate-100 text-slate-700 text-xs font-bold transition-all disabled:opacity-50"
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={handleStart}
            disabled={isProcessing}
            className="flex-2 py-3 px-5 rounded-2xl bg-gradient-to-r from-teal-600 to-emerald-600 hover:from-teal-700 hover:to-emerald-700 text-white text-xs font-black flex items-center justify-center gap-2 shadow-lg shadow-teal-600/30 transition-all active:scale-95 disabled:opacity-50"
          >
            <Play className="w-4 h-4 fill-current" />
            <span>
              {isProcessing
                ? 'STARTING...'
                : `START (${isCustom ? customMinutesInput : selectedMinutes} MIN TIMER)`}
            </span>
          </button>
        </div>
      </div>
    </div>
  );
};
