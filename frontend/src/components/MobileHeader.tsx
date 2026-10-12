import React, { useState, useEffect } from 'react';
import { Menu, Droplet, Bell, Volume2, VolumeX, LogOut, X } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { audioAlert } from '../utils/audioAlert';

interface MobileHeaderProps {
  wsConnected: boolean;
  onAvatarClick?: () => void;
  onOpenNotifications?: () => void;
  onMenuClick?: () => void;
}

export const MobileHeader: React.FC<MobileHeaderProps> = ({
  wsConnected,
  onAvatarClick,
  onOpenNotifications,
  onMenuClick,
}) => {
  const { user, logout } = useAuth();
  const initial = user?.name ? user.name.charAt(0).toUpperCase() : 'D';
  const [isMenuOpen, setIsMenuOpen] = useState<boolean>(false);
  const [audioUnlocked, setAudioUnlocked] = useState<boolean>(audioAlert.isUnlocked());

  useEffect(() => {
    return audioAlert.onUnlockChange((unlocked) => {
      setAudioUnlocked(unlocked);
    });
  }, []);

  const handleToggleAudio = async () => {
    await audioAlert.testSound('INFO');
    setAudioUnlocked(true);
  };

  return (
    <>
      <header className="sticky top-0 z-40 bg-white px-4 pt-[calc(0.625rem+env(safe-area-inset-top,0px))] pb-2.5 flex items-center justify-between gap-2 border-b border-slate-200 max-w-lg mx-auto w-full">
        {/* Left Hamburger Menu Button */}
        <button
          type="button"
          onClick={() => {
            if (onMenuClick) onMenuClick();
            else setIsMenuOpen(true);
          }}
          className="p-1.5 rounded-xl hover:bg-slate-100 text-slate-700 transition-colors flex-shrink-0 cursor-pointer"
          title="Open Menu"
        >
          <Menu className="w-6 h-6 stroke-[2.2]" />
        </button>

        {/* Center Brand */}
        <div className="flex items-center gap-2 flex-1 justify-start ml-1">
          <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
            <Droplet className="w-5 h-5 text-white fill-current" />
          </div>
          <div className="flex flex-col">
            <span className="font-bold text-base tracking-tight text-slate-900 leading-none">
              HydraControl
            </span>
            <span className="text-[9px] font-semibold tracking-wider text-slate-500 uppercase leading-tight mt-0.5">
              SMART MOTOR OS
            </span>
          </div>
        </div>

        {/* Right Controls: Stream Badge + Notification Bell + Avatar */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Live WS Status Dot */}
          <span
            className={`w-2 h-2 rounded-full ${
              wsConnected ? 'bg-emerald-500' : 'bg-amber-400 animate-pulse'
            }`}
            title={wsConnected ? 'Cloud WebSocket Live' : 'Reconnecting...'}
          />

          {/* Notification Bell with Badge */}
          <button
            type="button"
            onClick={onOpenNotifications || handleToggleAudio}
            className="p-1.5 rounded-full hover:bg-slate-100 text-slate-700 relative transition-colors cursor-pointer"
            title="Notifications & Alerts"
          >
            <Bell className="w-5 h-5 stroke-[2.2]" />
            <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-rose-500 ring-2 ring-white" />
          </button>

          {/* User Avatar Circle */}
          <button
            type="button"
            onClick={onAvatarClick || (() => setIsMenuOpen(true))}
            title={user?.name || user?.email || 'User Profile'}
            className="w-8 h-8 rounded-full bg-blue-600 text-white font-bold text-sm flex items-center justify-center ring-2 ring-slate-100 hover:bg-blue-700 active:scale-95 transition-all flex-shrink-0 cursor-pointer"
          >
            {initial}
          </button>
        </div>
      </header>

      {/* Quick Drawer / Modal on Hamburger Menu */}
      {isMenuOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-start p-4 bg-slate-950/40 backdrop-blur-xs font-sans">
          <div className="bg-white w-full max-w-xs rounded-2xl p-5 border border-slate-200 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white font-bold">
                  {initial}
                </div>
                <div>
                  <div className="text-xs font-bold text-slate-900">{user?.name || 'Operator'}</div>
                  <div className="text-[10px] text-slate-500">{user?.email}</div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsMenuOpen(false)}
                className="p-1 rounded-xl hover:bg-slate-100 text-slate-400 hover:text-slate-600 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-2">
              <button
                type="button"
                onClick={() => {
                  handleToggleAudio();
                  setIsMenuOpen(false);
                }}
                className="w-full p-2.5 rounded-xl bg-slate-50 hover:bg-slate-100 text-slate-800 text-xs font-semibold flex items-center justify-between border border-slate-200 cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  {audioUnlocked ? <Volume2 className="w-4 h-4 text-emerald-600" /> : <VolumeX className="w-4 h-4 text-amber-600" />}
                  <span>Buzzer Audio Alerts</span>
                </div>
                <span className="text-[10px] font-bold text-slate-500">
                  {audioUnlocked ? 'ENABLED' : 'TEST SOUND'}
                </span>
              </button>

              <button
                type="button"
                onClick={() => {
                  setIsMenuOpen(false);
                  logout();
                }}
                className="w-full p-2.5 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-700 text-xs font-semibold flex items-center gap-2 border border-rose-200 cursor-pointer"
              >
                <LogOut className="w-4 h-4" />
                <span>Sign Out</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
