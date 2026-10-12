import React from 'react';
import {
  ArrowLeft,
  Sliders,
  Zap,
  Clock,
  RefreshCw,
  Play,
  Square,
} from 'lucide-react';
import { Motor } from '../../types';

interface MotorSelectionScreenProps {
  onBack: () => void;
  motors: Motor[];
  activeMotor: Motor | null;
  onSelectMotor: (motor: Motor) => void;
  isProcessing: boolean;
  onPowerToggle: () => void;
  onOpenStartModal: () => void;
  currentAmps: number;
  voltage: number;
  powerKw: number;
  onRefresh: () => void;
  isSyncing: boolean;
}

export const MotorSelectionScreen: React.FC<MotorSelectionScreenProps> = ({
  onBack,
  motors,
  activeMotor,
  onSelectMotor,
  isProcessing,
  onPowerToggle,
  onOpenStartModal,
  currentAmps,
  voltage,
  powerKw,
  onRefresh,
  isSyncing,
}) => {
  const isRunning = activeMotor?.status === 'ON' || activeMotor?.status === 'STARTING';

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
            {motors.length} Motor{motors.length !== 1 ? 's' : ''} Configured
          </span>
          <button
            type="button"
            onClick={onRefresh}
            className="p-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors cursor-pointer"
            title="Refresh Motors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin text-blue-600' : ''}`} />
          </button>
        </div>
      </div>

      {/* Title & Overview Card */}
      <div className="mobile-card p-4 bg-white border border-slate-200 space-y-2">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl bg-blue-600 text-white flex items-center justify-center flex-shrink-0">
            <Sliders className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-base font-black text-slate-900 leading-tight">Select Active Motor</h2>
            <p className="text-xs text-slate-500 font-medium mt-0.5">
              Choose the designated pump unit for live telemetry &amp; automated control
            </p>
          </div>
        </div>
      </div>

      {/* Active Motor Quick Action Control Banner */}
      {activeMotor && (
        <div className="mobile-card p-4 border border-blue-500 bg-white space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span
                className={`w-3 h-3 rounded-full ${
                  isRunning
                    ? 'bg-emerald-500 animate-pulse ring-4 ring-emerald-100'
                    : activeMotor.status === 'FAULT'
                    ? 'bg-rose-500'
                    : 'bg-slate-400'
                }`}
              />
              <div>
                <div className="text-xs font-black text-slate-900 flex items-center gap-1.5">
                  <span>{activeMotor.name}</span>
                  <span className="px-1.5 py-0.5 rounded bg-blue-100 text-blue-800 text-[10px] font-mono font-bold">
                    {activeMotor.motor_code}
                  </span>
                </div>
                <div className="text-[11px] text-slate-400 font-medium">
                  {activeMotor.motor_type?.replace('_', ' ') || 'Submersible Pump'} &bull; {activeMotor.rated_power ?? 1.5} kW
                </div>
              </div>
            </div>

            <span
              className={`px-2.5 py-1 rounded-xl text-xs font-black uppercase tracking-wider ${
                isRunning
                  ? 'bg-emerald-100 text-emerald-700 border border-emerald-300'
                  : activeMotor.status === 'FAULT'
                  ? 'bg-rose-100 text-rose-700 border border-rose-300'
                  : 'bg-slate-100 text-slate-600 border border-slate-200'
              }`}
            >
              {activeMotor.status}
            </span>
          </div>

          {/* Quick Metrics per Motor */}
          <div className="grid grid-cols-3 gap-2 pt-1 border-t border-slate-100 text-center">
            <div className="p-2 rounded-xl bg-slate-50 border border-slate-100">
              <div className="text-[10px] text-slate-400 font-bold uppercase">Current</div>
              <div className="text-xs font-black text-slate-900 font-mono mt-0.5">
                {currentAmps.toFixed(1)} A
              </div>
            </div>
            <div className="p-2 rounded-xl bg-slate-50 border border-slate-100">
              <div className="text-[10px] text-slate-400 font-bold uppercase">Voltage</div>
              <div className="text-xs font-black text-slate-900 font-mono mt-0.5">
                {voltage.toFixed(0)} V
              </div>
            </div>
            <div className="p-2 rounded-xl bg-slate-50 border border-slate-100">
              <div className="text-[10px] text-slate-400 font-bold uppercase">Power</div>
              <div className="text-xs font-black text-slate-900 font-mono mt-0.5">
                {powerKw.toFixed(2)} kW
              </div>
            </div>
          </div>

          {/* Start / Stop Motor Buttons */}
          <div className="pt-2 flex items-center gap-2">
            {!isRunning ? (
              <>
                <button
                  type="button"
                  onClick={onOpenStartModal}
                  disabled={isProcessing}
                  className="flex-1 py-3 px-4 rounded-2xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-black flex items-center justify-center gap-2 active:scale-95 transition-all cursor-pointer disabled:opacity-50"
                >
                  <Clock className="w-4 h-4" />
                  <span>START WITH TIMER</span>
                </button>

                <button
                  type="button"
                  onClick={onPowerToggle}
                  disabled={isProcessing}
                  className="py-3 px-4 rounded-2xl bg-blue-50 hover:bg-blue-100 text-blue-800 text-xs font-black flex items-center justify-center gap-1.5 border border-blue-200 transition-all active:scale-95 cursor-pointer disabled:opacity-50"
                >
                  <Play className="w-4 h-4 fill-current" />
                  <span>START</span>
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={onPowerToggle}
                disabled={isProcessing}
                className="w-full py-3 px-4 rounded-2xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-black flex items-center justify-center gap-2 active:scale-95 transition-all cursor-pointer disabled:opacity-50"
              >
                <Square className="w-4 h-4 fill-current" />
                <span>STOP MOTOR NOW</span>
              </button>
            )}
          </div>
        </div>
      )}

      {/* Available Motor Units List */}
      <div className="space-y-2 pt-2">
        <h3 className="text-xs font-black uppercase tracking-wider text-slate-400 px-1">
          Available Pump Units ({motors.length})
        </h3>

        <div className="space-y-2.5">
          {motors.map((m) => {
            const isSelected = activeMotor?.id === m.id;
            const isMotorOn = m.status === 'ON' || m.status === 'STARTING';
            return (
              <button
                key={m.id}
                type="button"
                onClick={() => onSelectMotor(m)}
                className={`w-full p-4 rounded-2xl border text-left flex flex-col justify-between gap-3 transition-all cursor-pointer ${
                  isSelected
                    ? 'bg-blue-50/70 border-blue-500 ring-1 ring-blue-500/30'
                    : 'bg-white hover:bg-slate-50 border-slate-200 text-slate-700'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-start gap-3">
                    <div
                      className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${
                        isSelected
                          ? 'bg-blue-600 text-white'
                          : 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      <Zap className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="text-sm font-black text-slate-900 flex items-center gap-2">
                        <span>{m.name}</span>
                        <span className="font-mono text-xs text-slate-500 font-bold bg-slate-100 px-1.5 py-0.5 rounded">
                          {m.motor_code}
                        </span>
                      </div>
                      <div className="text-xs text-slate-400 font-medium mt-0.5">
                        {m.motor_type?.replace('_', ' ') || 'Centrifugal Water Pump'} &bull; Rated {m.rated_power ?? 1.5} kW
                      </div>
                    </div>
                  </div>

                  <span
                    className={`px-2 py-0.5 rounded-lg text-[10px] font-black uppercase tracking-wider ${
                      isMotorOn
                        ? 'bg-emerald-100 text-emerald-700 border border-emerald-300'
                        : m.status === 'FAULT'
                        ? 'bg-rose-100 text-rose-700 border border-rose-300'
                        : 'bg-slate-100 text-slate-600 border border-slate-200'
                    }`}
                  >
                    {m.status}
                  </span>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-xs">
                  <span className={`font-bold ${isSelected ? 'text-blue-700' : 'text-slate-400'}`}>
                    {isSelected ? '✓ Currently Active Unit' : 'Tap to Select this Motor'}
                  </span>
                  <span className="text-[11px] text-slate-400 font-mono">
                    Code: {m.motor_code}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};
