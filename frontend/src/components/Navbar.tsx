import React from 'react';
import { Droplets, LogOut, Radio, UserCheck } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { Badge } from './common/Badge';

interface NavbarProps {
  wsConnected: boolean;
  activeOrgName?: string;
}

export const Navbar: React.FC<NavbarProps> = ({ wsConnected, activeOrgName }) => {
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
      default:
        return 'neutral';
    }
  };

  return (
    <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-xl sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/25">
            <Droplets className="w-6 h-6 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-lg bg-gradient-to-r from-white via-slate-100 to-cyan-400 bg-clip-text text-transparent">
                HydraControl
              </span>
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-cyan-950/80 text-cyan-400 border border-cyan-800/50">
                v0.1.0-alpha
              </span>
            </div>
            {activeOrgName && (
              <p className="text-[11px] text-slate-400 font-medium tracking-tight">
                Tenant: <span className="text-slate-200 font-semibold">{activeOrgName}</span>
              </p>
            )}
          </div>
        </div>

        {/* Status & User */}
        <div className="flex items-center gap-4">
          {/* Gateway / WebSocket Status Indicator */}
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-800/60 border border-slate-700/50 shadow-inner">
            <Radio className={`w-3.5 h-3.5 ${wsConnected ? 'text-emerald-400 animate-pulse' : 'text-amber-400'}`} />
            <span className="text-xs text-slate-400">Stream:</span>
            <span className={`text-xs font-bold ${wsConnected ? 'text-emerald-400' : 'text-amber-400'}`}>
              {wsConnected ? 'LIVE' : 'CONNECTING...'}
            </span>
          </div>

          {/* User profile & Logout */}
          {user && (
            <div className="flex items-center gap-3">
              <div className="hidden md:flex flex-col items-end">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-200">
                  <UserCheck className="w-3.5 h-3.5 text-cyan-400" />
                  {user.name}
                </div>
                <Badge variant={getRoleBadgeVariant(user.role)} size="sm">
                  {user.role}
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
