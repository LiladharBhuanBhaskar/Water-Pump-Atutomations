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
    <div className="fixed bottom-0 left-0 right-0 z-50 flex justify-center pointer-events-none pb-[calc(0.5rem+env(safe-area-inset-bottom,0px))] px-3">
      <nav className="pointer-events-auto w-full max-w-md h-16 rounded-2xl px-2 flex items-center justify-between relative bg-white border border-slate-200">
        {/* TAB 1: HOME */}
        <button
          type="button"
          onClick={() => onTabChange('HOME')}
          className={`flex flex-col items-center justify-center flex-1 py-1 transition-colors cursor-pointer ${
            activeTab === 'HOME'
              ? 'text-blue-600 font-bold'
              : 'text-slate-500 hover:text-slate-700 font-medium'
          }`}
        >
          <div
            className={`px-3 py-1 rounded-lg transition-colors ${
              activeTab === 'HOME' ? 'bg-blue-50 text-blue-600' : ''
            }`}
          >
            <Home className="w-5 h-5 fill-current stroke-1" />
          </div>
          <span className="text-[10px] mt-0.5">Home</span>
        </button>

        {/* TAB 2: SCHEDULES */}
        <button
          type="button"
          onClick={() => onTabChange('SCHEDULES')}
          className={`flex flex-col items-center justify-center flex-1 py-1 transition-colors cursor-pointer ${
            activeTab === 'SCHEDULES'
              ? 'text-blue-600 font-bold'
              : 'text-slate-500 hover:text-slate-700 font-medium'
          }`}
        >
          <div
            className={`px-3 py-1 rounded-lg transition-colors ${
              activeTab === 'SCHEDULES' ? 'bg-blue-50 text-blue-600' : ''
            }`}
          >
            <Calendar className="w-5 h-5 stroke-[2]" />
          </div>
          <span className="text-[10px] mt-0.5">Schedules</span>
        </button>

        {/* CENTER FLOATING POWER BUTTON */}
        <div className="flex flex-col items-center justify-center -mt-6 px-2">
          <button
            type="button"
            onClick={onPowerToggle}
            disabled={isProcessing}
            title={isMotorRunning ? 'Tap to Stop Pump' : 'Tap to Start Pump'}
            className={`w-14 h-14 rounded-full flex items-center justify-center text-white relative shadow-xl transition-all cursor-pointer ${
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
          className={`flex flex-col items-center justify-center flex-1 py-1 transition-colors cursor-pointer ${
            activeTab === 'HISTORY'
              ? 'text-blue-600 font-bold'
              : 'text-slate-500 hover:text-slate-700 font-medium'
          }`}
        >
          <div
            className={`px-3 py-1 rounded-lg transition-colors ${
              activeTab === 'HISTORY' ? 'bg-blue-50 text-blue-600' : ''
            }`}
          >
            <BarChart2 className="w-5 h-5 stroke-[2]" />
          </div>
          <span className="text-[10px] mt-0.5">History</span>
        </button>

        {/* TAB 4: SETTINGS */}
        <button
          type="button"
          onClick={() => onTabChange('SETTINGS')}
          className={`flex flex-col items-center justify-center flex-1 py-1 transition-colors cursor-pointer ${
            activeTab === 'SETTINGS'
              ? 'text-blue-600 font-bold'
              : 'text-slate-500 hover:text-slate-700 font-medium'
          }`}
        >
          <div
            className={`px-3 py-1 rounded-lg transition-colors ${
              activeTab === 'SETTINGS' ? 'bg-blue-50 text-blue-600' : ''
            }`}
          >
            <Settings className="w-5 h-5 stroke-[2]" />
          </div>
          <span className="text-[10px] mt-0.5">Settings</span>
        </button>
      </nav>
    </div>
  );
};
