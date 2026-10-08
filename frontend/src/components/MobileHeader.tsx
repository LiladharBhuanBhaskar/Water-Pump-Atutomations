import React from 'react';
import { Droplets } from 'lucide-react';
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
    <header className="sticky top-0 z-40 bg-white/90 backdrop-blur-xl px-4 py-2.5 flex items-center justify-between gap-2 border-b border-slate-200/60 max-w-lg mx-auto w-full shadow-[0_2px_10px_rgba(0,0,0,0.02)]">
      {/* Brand */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-teal-500 to-emerald-500 flex items-center justify-center shadow-md shadow-teal-500/20 flex-shrink-0">
          <Droplets className="w-4.5 h-4.5 text-white" />
        </div>
        <div className="flex flex-col">
          <span className="font-black text-base tracking-tight text-slate-900 leading-none">
            HydraControl
          </span>
          <span className="text-[9px] font-bold tracking-wider text-teal-600 uppercase leading-tight mt-0.5">
            Smart Motor OS
          </span>
        </div>
      </div>

      {/* Right Controls (Live Capsule + Profile Avatar) */}
      <div className="flex items-center gap-2 flex-shrink-0">
        {/* Stream Status Capsule Badge */}
        {wsConnected ? (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200/90 text-[11px] font-bold text-emerald-700 shadow-xs">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span className="tracking-wide">LIVE</span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-900 border border-slate-800 text-[11px] font-semibold text-slate-300 shadow-xs">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse"></span>
            <span className="text-[10px] text-amber-300 font-bold tracking-wider">SYNCING</span>
          </div>
        )}

        {/* User Avatar Circle */}
        <button
          type="button"
          onClick={onAvatarClick}
          title={user?.name || 'User Profile'}
          className="w-8 h-8 rounded-full bg-gradient-to-tr from-purple-500 to-indigo-600 text-white font-bold text-xs flex items-center justify-center shadow-md shadow-purple-500/20 ring-2 ring-white hover:scale-105 active:scale-95 transition-all flex-shrink-0"
        >
          {initial}
        </button>
      </div>
    </header>
  );
};
