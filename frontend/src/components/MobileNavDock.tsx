import React from 'react';
import { Home, Calendar, Power, BarChart2, Settings, Loader2 } from 'lucide-react';

export type MobileTab = 'HOME' | 'SCHEDULES' | 'HISTORY' | 'SETTINGS';

interface MobileNavDockProps {
  activeTab: MobileTab;
  onTabChange: (tab: MobileTab) => void;
  isMotorRunning: boolean;
  isProcessing: boolean;
  onPowerToggle: () => void;
}

export const MobileNavDock: React.FC<MobileNavDockProps> = ({
  activeTab,
  onTabChange,
  isMotorRunning,
  isProcessing,
  onPowerToggle,
}) => {
  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 flex justify-center pointer-events-none pb-2 px-3">
      <nav className="bottom-nav-dock pointer-events-auto w-full max-w-md h-18 rounded-[28px] px-4 flex items-center justify-between relative">
        {/* TAB 1: HOME */}
        <button
          type="button"
          onClick={() => onTabChange('HOME')}
          className={`flex flex-col items-center justify-center flex-1 py-1 transition-all ${
            activeTab === 'HOME'
              ? 'text-teal-700 font-extrabold'
              : 'text-slate-400 hover:text-slate-600 font-medium'
          }`}
        >
          <div
            className={`p-1.5 rounded-xl transition-all ${
              activeTab === 'HOME' ? 'bg-teal-50 text-teal-700' : ''
            }`}
          >
            <Home className="w-5 h-5" />
          </div>
          <span className="text-[11px] mt-0.5">Home</span>
          {activeTab === 'HOME' && (
            <span className="w-1.5 h-1.5 rounded-full bg-teal-600 mt-0.5" />
          )}
        </button>

        {/* TAB 2: SCHEDULES */}
        <button
          type="button"
          onClick={() => onTabChange('SCHEDULES')}
          className={`flex flex-col items-center justify-center flex-1 py-1 transition-all ${
            activeTab === 'SCHEDULES'
              ? 'text-teal-700 font-extrabold'
              : 'text-slate-400 hover:text-slate-600 font-medium'
          }`}
        >
          <div
            className={`p-1.5 rounded-xl transition-all ${
              activeTab === 'SCHEDULES' ? 'bg-teal-50 text-teal-700' : ''
            }`}
          >
            <Calendar className="w-5 h-5" />
          </div>
          <span className="text-[11px] mt-0.5">Schedules</span>
          {activeTab === 'SCHEDULES' && (
            <span className="w-1.5 h-1.5 rounded-full bg-teal-600 mt-0.5" />
          )}
        </button>

        {/* CENTER FLOATING POWER BUTTON */}
        <div className="flex flex-col items-center justify-center -mt-6 px-2">
          <button
            type="button"
            onClick={onPowerToggle}
            disabled={isProcessing}
            title={isMotorRunning ? 'Tap to Stop Pump' : 'Tap to Start Pump'}
            className={`w-14 h-14 rounded-full flex items-center justify-center text-white relative shadow-xl transition-all ${
              isMotorRunning
                ? 'floating-power-btn-running animate-ring-pulse'
                : 'floating-power-btn'
            }`}
          >
            {isProcessing ? (
              <Loader2 className="w-7 h-7 animate-spin text-white" />
            ) : (
              <Power className="w-7 h-7 stroke-[2.5]" />
            )}
          </button>
        </div>

        {/* TAB 3: HISTORY */}
        <button
          type="button"
          onClick={() => onTabChange('HISTORY')}
          className={`flex flex-col items-center justify-center flex-1 py-1 transition-all ${
            activeTab === 'HISTORY'
              ? 'text-teal-700 font-extrabold'
              : 'text-slate-400 hover:text-slate-600 font-medium'
          }`}
        >
          <div
            className={`p-1.5 rounded-xl transition-all ${
              activeTab === 'HISTORY' ? 'bg-teal-50 text-teal-700' : ''
            }`}
          >
            <BarChart2 className="w-5 h-5" />
          </div>
          <span className="text-[11px] mt-0.5">History</span>
          {activeTab === 'HISTORY' && (
            <span className="w-1.5 h-1.5 rounded-full bg-teal-600 mt-0.5" />
          )}
        </button>

        {/* TAB 4: SETTINGS */}
        <button
          type="button"
          onClick={() => onTabChange('SETTINGS')}
          className={`flex flex-col items-center justify-center flex-1 py-1 transition-all ${
            activeTab === 'SETTINGS'
              ? 'text-teal-700 font-extrabold'
              : 'text-slate-400 hover:text-slate-600 font-medium'
          }`}
        >
          <div
            className={`p-1.5 rounded-xl transition-all ${
              activeTab === 'SETTINGS' ? 'bg-teal-50 text-teal-700' : ''
            }`}
          >
            <Settings className="w-5 h-5" />
          </div>
          <span className="text-[11px] mt-0.5">Settings</span>
          {activeTab === 'SETTINGS' && (
            <span className="w-1.5 h-1.5 rounded-full bg-teal-600 mt-0.5" />
          )}
        </button>
      </nav>
    </div>
  );
};
