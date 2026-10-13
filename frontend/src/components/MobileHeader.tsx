import React, { useState, useEffect } from 'react';
import { Menu, Droplet, Bell, Volume2, VolumeX, LogOut, X, Globe } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
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
  const { language, setLanguage, toggleLanguage, t } = useLanguage();
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
      <header className="sticky top-0 z-40 bg-white border-b border-slate-200/90 shadow-xs w-full pt-[max(0.625rem,env(safe-area-inset-top,0px))] pb-2.5">
        <div className="max-w-lg mx-auto px-3.5 sm:px-4 flex items-center justify-between gap-2">
          {/* Left Hamburger Menu Button */}
          <button
            type="button"
            onClick={() => {
              if (onMenuClick) onMenuClick();
              else setIsMenuOpen(true);
            }}
            className="p-1.5 rounded-xl hover:bg-slate-100 text-slate-700 transition-colors flex-shrink-0 cursor-pointer active:scale-95"
            title="Open Menu"
          >
            <Menu className="w-5 h-5 sm:w-6 sm:h-6 stroke-[2.2]" />
          </button>

          {/* Center Brand */}
          <div className="flex items-center gap-2 flex-1 justify-start ml-0.5 min-w-0">
            <div className="w-8 h-8 rounded-xl bg-blue-600 flex items-center justify-center flex-shrink-0 shadow-xs">
              <Droplet className="w-4.5 h-4.5 text-white fill-current" />
            </div>
            <div className="flex flex-col min-w-0">
              <span className="font-extrabold text-sm sm:text-base tracking-tight text-slate-900 leading-none truncate">
                {t.appTitle}
              </span>
              <span className="text-[9px] sm:text-[10px] font-bold tracking-wider text-slate-500 uppercase leading-tight mt-0.5 truncate">
                {t.appSubtitle}
              </span>
            </div>
          </div>

          {/* Right Controls: Language Switcher + Stream Badge + Notification Bell + Avatar */}
          <div className="flex items-center gap-1.5 sm:gap-2 flex-shrink-0">
            {/* Quick Language Toggle Pill */}
            <button
              type="button"
              onClick={toggleLanguage}
              title={`Switch language / भाषा बदलें (${language === 'en' ? 'हिन्दी' : 'English'})`}
              className="flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-100 hover:bg-blue-50 border border-slate-200 hover:border-blue-300 text-slate-800 hover:text-blue-700 text-[11px] font-bold transition-all cursor-pointer active:scale-95 shadow-xs"
            >
              <Globe className="w-3.5 h-3.5 text-slate-500" />
              <span className="font-mono uppercase tracking-wide">
                {language === 'en' ? 'हिं' : 'EN'}
              </span>
            </button>

            {/* Live WS Status Pill */}
            <div
              className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold border transition-colors ${
                wsConnected
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                  : 'bg-amber-50 text-amber-700 border-amber-200'
              }`}
              title={wsConnected ? 'Cloud Stream Live' : 'Reconnecting...'}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  wsConnected ? 'bg-emerald-500' : 'bg-amber-500'
                }`}
              />
              <span className="hidden xs:inline">{wsConnected ? t.online : t.syncing}</span>
            </div>

            {/* Notification Bell with Badge */}
            <button
              type="button"
              onClick={onOpenNotifications || handleToggleAudio}
              className="p-1.5 sm:p-2 rounded-xl hover:bg-slate-100 text-slate-700 relative transition-colors cursor-pointer active:scale-95"
              title="Notifications & Alerts"
            >
              <Bell className="w-4.5 h-4.5 sm:w-5 sm:h-5 stroke-[2]" />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-rose-500 ring-2 ring-white" />
            </button>

            {/* User Avatar Circle */}
            <button
              type="button"
              onClick={onAvatarClick || (() => setIsMenuOpen(true))}
              title={user?.name || user?.email || 'User Profile'}
              className="w-7 h-7 sm:w-8 sm:h-8 rounded-xl bg-slate-900 text-white font-bold text-xs flex items-center justify-center ring-1 ring-slate-200 hover:bg-slate-800 active:scale-95 transition-all flex-shrink-0 cursor-pointer shadow-xs"
            >
              {initial}
            </button>
          </div>
        </div>
      </header>

      {/* Quick Drawer / Modal on Hamburger Menu */}
      {isMenuOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-start p-4 bg-slate-950/40 backdrop-blur-xs font-sans">
          <div className="bg-white w-full max-w-xs rounded-2xl p-5 border border-slate-200 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-blue-600 flex items-center justify-center text-white font-bold">
                  {initial}
                </div>
                <div>
                  <div className="text-xs font-bold text-slate-900">{user?.name || t.operator}</div>
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
              {/* Language Selection Card in Drawer */}
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
                <div className="flex items-center justify-between text-xs font-bold text-slate-800">
                  <div className="flex items-center gap-1.5">
                    <Globe className="w-4 h-4 text-blue-600" />
                    <span>Language / भाषा</span>
                  </div>
                  <span className="text-[10px] font-mono text-slate-500 font-semibold uppercase">
                    {language === 'en' ? 'English' : 'हिन्दी'}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => setLanguage('en')}
                    className={`py-1.5 px-3 rounded-lg text-xs font-bold transition-all cursor-pointer border ${
                      language === 'en'
                        ? 'bg-blue-600 text-white border-blue-600 shadow-xs'
                        : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-100'
                    }`}
                  >
                    English
                  </button>
                  <button
                    type="button"
                    onClick={() => setLanguage('hi')}
                    className={`py-1.5 px-3 rounded-lg text-xs font-bold transition-all cursor-pointer border ${
                      language === 'hi'
                        ? 'bg-blue-600 text-white border-blue-600 shadow-xs'
                        : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-100'
                    }`}
                  >
                    हिन्दी
                  </button>
                </div>
              </div>

              {/* Audio Alerts Setting */}
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
                  <span>{t.buzzerAudio}</span>
                </div>
                <span className="text-[10px] font-bold text-slate-500">
                  {audioUnlocked ? t.buzzerEnabled : t.buzzerTest}
                </span>
              </button>

              {/* Sign Out */}
              <button
                type="button"
                onClick={() => {
                  setIsMenuOpen(false);
                  logout();
                }}
                className="w-full p-2.5 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-700 text-xs font-semibold flex items-center gap-2 border border-rose-200 cursor-pointer"
              >
                <LogOut className="w-4 h-4" />
                <span>{t.signOut}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
