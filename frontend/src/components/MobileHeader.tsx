import React from 'react';
import { Droplets, Radio } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface MobileHeaderProps {
  wsConnected: boolean;
  onAvatarClick?: () => void;
}

export const MobileHeader: React.FC<MobileHeaderProps> = ({
  wsConnected,
  onAvatarClick,
}) => {
  const { user } = useAuth();
  const initial = user?.name ? user.name.charAt(0).toUpperCase() : 'U';

  return (
    <header className="sticky top-0 z-40 bg-[#f0f4f9]/90 backdrop-blur-md px-4 py-2.5 flex items-center justify-between border-b border-slate-200/60 max-w-lg mx-auto w-full">
      {/* Brand */}
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center shadow-md shadow-blue-500/20">
          <Droplets className="w-5 h-5 text-white" />
        </div>
        <span className="font-extrabold text-lg tracking-tight bg-gradient-to-r from-blue-700 to-cyan-600 bg-clip-text text-transparent">
          HydraControl
        </span>
      </div>

      {/* Stream Status Capsule Badge */}
      <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-900 border border-slate-800 text-[11px] font-semibold text-slate-300 shadow-sm">
        <Radio
          className={`w-3.5 h-3.5 ${
            wsConnected ? 'text-emerald-400 animate-pulse' : 'text-amber-400 animate-ping'
          }`}
        />
        <span className="text-slate-400">Stream:</span>
        <span
          className={`font-bold ${
            wsConnected ? 'text-emerald-400' : 'text-amber-400'
          }`}
        >
          {wsConnected ? 'LIVE' : 'CONNECTING...'}
        </span>
      </div>

      {/* User Avatar Circle */}
      <button
        onClick={onAvatarClick}
        title={user?.name || 'User Profile'}
        className="w-8 h-8 rounded-full bg-gradient-to-tr from-purple-500 to-indigo-600 text-white font-bold text-xs flex items-center justify-center shadow-md shadow-purple-500/25 hover:scale-105 active:scale-95 transition-all"
      >
        {initial}
      </button>
    </header>
  );
};
