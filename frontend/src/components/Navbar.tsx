import React from 'react';
import { Droplets, LogOut, Radio, UserCheck, Smartphone, Shield } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { Badge } from './common/Badge';

interface NavbarProps {
  wsConnected: boolean;
  activeOrgName?: string;
  activeMode?: 'ENTERPRISE' | 'HOME';
  onModeToggle?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  wsConnected,
  activeOrgName,
  activeMode = 'ENTERPRISE',
  onModeToggle,
}) => {
  const { user, logout } = useAuth();

  const getRoleBadgeVariant = (role?: string) => {
    switch (role) {
      case 'SUPER_ADMIN':
        return 'purple';
      case 'ORGANIZATION_ADMIN':
      case 'SITE_MANAGER':
        return 'info';
      case 'STATION_OPERATOR':
      case 'OWNER':
        return 'success';
      case 'TECHNICIAN':
        return 'warning';
      case 'FAMILY_MEMBER':
        return 'info';
      default:
        return 'neutral';
    }
  };

  const canSwitchMode =
    user?.role === 'SUPER_ADMIN' ||
    user?.role === 'ORGANIZATION_ADMIN' ||
    user?.role === 'SITE_MANAGER' ||
    user?.role === 'OWNER';

  return (
    <header className="border-b border-slate-800/80 bg-slate-900/80 backdrop-blur-xl sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-2">
        {/* Brand */}
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/25 flex-shrink-0">
            <Droplets className="w-5 h-5 sm:w-6 sm:h-6 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-extrabold text-base sm:text-lg bg-gradient-to-r from-white via-slate-100 to-cyan-400 bg-clip-text text-transparent">
                HydraControl
              </span>
            </div>
            {activeOrgName && (
              <p className="hidden sm:block text-[10px] text-slate-400 font-medium">
                Tenant: <span className="text-slate-200 font-semibold">{activeOrgName}</span>
              </p>
            )}
          </div>
        </div>

        {/* Center: Mode Switcher for Admins (Admin Console vs User App) */}
        {canSwitchMode && onModeToggle && (
          <div className="flex items-center p-1 rounded-xl bg-slate-950/90 border border-slate-800 shadow-inner">
            <button
              type="button"
              onClick={activeMode === 'HOME' ? onModeToggle : undefined}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold transition-all ${
                activeMode === 'ENTERPRISE'
                  ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Shield className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Admin</span> Console
            </button>
            <button
              type="button"
              onClick={activeMode === 'ENTERPRISE' ? onModeToggle : undefined}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold transition-all ${
                activeMode === 'HOME'
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Smartphone className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">User</span> App
            </button>
          </div>
        )}

        {/* Status & User */}
        <div className="flex items-center gap-2 sm:gap-4">
          {/* Gateway / WebSocket Status Indicator */}
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-800/60 border border-slate-700/50 shadow-inner">
            <Radio
              className={`w-3.5 h-3.5 ${
                wsConnected ? 'text-emerald-400 animate-pulse' : 'text-amber-400'
              }`}
            />
            <span className="text-xs text-slate-400">Stream:</span>
            <span
              className={`text-xs font-bold ${
                wsConnected ? 'text-emerald-400' : 'text-amber-400'
              }`}
            >
              {wsConnected ? 'LIVE' : 'CONNECTING...'}
            </span>
          </div>

          {/* User profile & Logout */}
          {user && (
            <div className="flex items-center gap-2 sm:gap-3">
              <div className="hidden md:flex flex-col items-end">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-200">
                  <UserCheck className="w-3.5 h-3.5 text-cyan-400" />
                  {user.name}
                </div>
                <Badge variant={getRoleBadgeVariant(user.role)} size="sm">
                  {user.role === 'SUPER_ADMIN' ? 'Admin' : 'Operator'}
                </Badge>
              </div>

              <button
                onClick={logout}
                title="Sign out"
                className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-rose-400 border border-slate-700 transition-colors"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
