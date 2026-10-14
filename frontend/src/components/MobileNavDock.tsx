import React from 'react';
import { Home, Calendar, Power, BarChart2, Settings, Loader2, RotateCcw } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';

export type MobileTab = 'HOME' | 'SCHEDULES' | 'HISTORY' | 'SETTINGS';

interface MobileNavDockProps {
  activeTab: MobileTab;
  onTabChange: (tab: MobileTab) => void;
  isMotorRunning: boolean;
  isProcessing: boolean;
  onPowerToggle: () => void;
  motorStatus?: string;
}

export const MobileNavDock: React.FC<MobileNavDockProps> = ({
  activeTab,
  onTabChange,
  isMotorRunning,
  isProcessing,
  onPowerToggle,
  motorStatus,
}) => {
  const { t } = useLanguage();
  const isFault = motorStatus === 'FAULT';

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 flex justify-center pointer-events-none pb-[max(0.5rem,env(safe-area-inset-bottom,0px))] px-3">
      <nav className="pointer-events-auto w-full max-w-md h-16 rounded-2xl px-2 flex items-center justify-between relative bg-white/95 backdrop-blur-md border border-slate-200/90 shadow-lg shadow-slate-900/5">
        {/* TAB 1: HOME */}
        <button
          type="button"
          onClick={() => onTabChange('HOME')}
          className={`flex flex-col items-center justify-center flex-1 py-1 transition-colors cursor-pointer active:scale-95 ${
            activeTab === 'HOME'
              ? 'text-blue-700 font-bold'
              : 'text-slate-500 hover:text-slate-800 font-medium'
          }`}
        >
          <div
            className={`px-3 py-1 rounded-xl transition-colors ${
              activeTab === 'HOME' ? 'bg-blue-50 text-blue-700' : ''
            }`}
          >
            <Home className="w-5 h-5 stroke-[2]" />
          </div>
          <span className="text-[10px] tracking-tight mt-0.5">{t.navHome}</span>
        </button>

        {/* TAB 2: SCHEDULES */}
        <button
          type="button"
          onClick={() => onTabChange('SCHEDULES')}
          className={`flex flex-col items-center justify-center flex-1 py-1 transition-colors cursor-pointer active:scale-95 ${
            activeTab === 'SCHEDULES'
              ? 'text-blue-700 font-bold'
              : 'text-slate-500 hover:text-slate-800 font-medium'
          }`}
        >
          <div
            className={`px-3 py-1 rounded-xl transition-colors ${
              activeTab === 'SCHEDULES' ? 'bg-blue-50 text-blue-700' : ''
            }`}
          >
            <Calendar className="w-5 h-5 stroke-[2]" />
          </div>
          <span className="text-[10px] tracking-tight mt-0.5">{t.navSchedules}</span>
        </button>

        {/* CENTER POWER CONTROL BUTTON */}
        <div className="flex flex-col items-center justify-center -mt-6 px-1 shrink-0">
          <button
            type="button"
            onClick={onPowerToggle}
            disabled={isProcessing}
            title={isFault ? 'Clear Fault & Reset' : isMotorRunning ? t.dockStop : t.dockStart}
            className={`w-14 h-14 rounded-full flex items-center justify-center text-white relative shadow-md transition-all cursor-pointer active:scale-90 ${
              isFault
                ? 'bg-rose-600 hover:bg-rose-700 ring-4 ring-rose-200 animate-pulse'
                : isMotorRunning
                ? 'floating-power-btn-running ring-4 ring-rose-100'
                : 'floating-power-btn ring-4 ring-blue-100'
            }`}
          >
            {isProcessing ? (
              <Loader2 className="w-6 h-6 animate-spin text-white" />
            ) : isFault ? (
              <RotateCcw className="w-6 h-6 stroke-[2.5]" />
            ) : (
              <Power className="w-6 h-6 stroke-[2.5]" />
            )}
          </button>
          <span
            className={`text-[9px] font-black uppercase tracking-wider mt-1 px-1.5 py-0.2 rounded-full ${
              isFault
                ? 'bg-rose-100 text-rose-700 font-black'
                : isMotorRunning
                ? 'bg-rose-100 text-rose-700'
                : 'bg-slate-100 text-slate-600'
            }`}
          >
            {isFault ? 'RESET' : isMotorRunning ? t.dockRunning : t.dockPump}
          </span>
        </div>

        {/* TAB 3: HISTORY */}
        <button
          type="button"
          onClick={() => onTabChange('HISTORY')}
          className={`flex flex-col items-center justify-center flex-1 py-1 transition-colors cursor-pointer active:scale-95 ${
            activeTab === 'HISTORY'
              ? 'text-blue-700 font-bold'
              : 'text-slate-500 hover:text-slate-800 font-medium'
          }`}
        >
          <div
            className={`px-3 py-1 rounded-xl transition-colors ${
              activeTab === 'HISTORY' ? 'bg-blue-50 text-blue-700' : ''
            }`}
          >
            <BarChart2 className="w-5 h-5 stroke-[2]" />
          </div>
          <span className="text-[10px] tracking-tight mt-0.5">{t.navActivity}</span>
        </button>

        {/* TAB 4: SETTINGS / ADMIN */}
        <button
          type="button"
          onClick={() => onTabChange('SETTINGS')}
          className={`flex flex-col items-center justify-center flex-1 py-1 transition-colors cursor-pointer active:scale-95 ${
            activeTab === 'SETTINGS'
              ? 'text-blue-700 font-bold'
              : 'text-slate-500 hover:text-slate-800 font-medium'
          }`}
        >
          <div
            className={`px-3 py-1 rounded-xl transition-colors ${
              activeTab === 'SETTINGS' ? 'bg-blue-50 text-blue-700' : ''
            }`}
          >
            <Settings className="w-5 h-5 stroke-[2]" />
          </div>
          <span className="text-[10px] tracking-tight mt-0.5">{t.navAdmin}</span>
        </button>
      </nav>
    </div>
  );
};
