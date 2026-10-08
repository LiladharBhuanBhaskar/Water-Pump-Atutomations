import React, { useState } from 'react';
import { Droplets, Lock, Mail, AlertCircle, ArrowRight, Shield, User, Sparkles, CheckCircle2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/common/Button';

export const Login: React.FC = () => {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedRole, setSelectedRole] = useState<'ADMIN' | 'USER' | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Please enter both email and password.');
      return;
    }

    setError(null);
    setLoading(true);
    try {
      await login(email, password);
    } catch (err: any) {
      setError(err.message || 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectRole = (roleType: 'ADMIN' | 'USER') => {
    setSelectedRole(roleType);
    if (roleType === 'ADMIN') {
      setEmail('admin@hydracontrol.io');
      setPassword('SecretPass123!');
    } else {
      setEmail('operator@hydracontrol.io');
      setPassword('SecretPass123!');
    }
    setError(null);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col justify-center items-center p-4 sm:p-6 relative overflow-hidden selection:bg-cyan-500 selection:text-black">
      {/* Background Ambience */}
      <div className="absolute -top-32 -left-32 w-80 h-80 sm:w-96 sm:h-96 bg-cyan-500/15 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-32 -right-32 w-80 h-80 sm:w-96 sm:h-96 bg-blue-600/15 rounded-full blur-3xl pointer-events-none" />

      <div className="w-full max-w-md space-y-6 z-10">
        {/* Branding Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex w-16 h-16 rounded-2xl bg-gradient-to-tr from-cyan-500 to-blue-600 items-center justify-center shadow-xl shadow-cyan-500/25 ring-1 ring-cyan-400/30">
            <Droplets className="w-9 h-9 text-white animate-pulse" />
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-100 to-cyan-400 bg-clip-text text-transparent">
            HydraControl
          </h1>
          <p className="text-xs text-slate-400 font-medium">
            Smart Water Motor Automation & Protection System
          </p>
        </div>

        {/* 2 Primary Access Cards: Admin vs Motor Operator */}
        <div className="space-y-2.5">
          <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400 text-center flex items-center justify-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
            Select Your Account
          </p>
          <div className="grid grid-cols-2 gap-3">
            {/* ID 1: ADMIN */}
            <button
              type="button"
              onClick={() => handleSelectRole('ADMIN')}
              className={`p-3.5 rounded-2xl border text-left transition-all duration-200 relative overflow-hidden ${
                selectedRole === 'ADMIN'
                  ? 'bg-gradient-to-b from-purple-950/70 to-slate-900 border-purple-500 ring-2 ring-purple-500/40 shadow-lg shadow-purple-500/20'
                  : 'bg-slate-900/80 hover:bg-slate-850 border-slate-800 hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="w-8 h-8 rounded-xl bg-purple-500/20 text-purple-400 flex items-center justify-center border border-purple-500/30">
                  <Shield className="w-4 h-4" />
                </div>
                {selectedRole === 'ADMIN' && (
                  <CheckCircle2 className="w-4 h-4 text-purple-400" />
                )}
              </div>
              <div className="font-bold text-sm text-white">1. Admin ID</div>
              <div className="text-[11px] text-slate-400 mt-0.5 leading-tight">
                Full settings, rules, logs & fleet
              </div>
            </button>

            {/* ID 2: USER (MOTOR OPERATOR) */}
            <button
              type="button"
              onClick={() => handleSelectRole('USER')}
              className={`p-3.5 rounded-2xl border text-left transition-all duration-200 relative overflow-hidden ${
                selectedRole === 'USER'
                  ? 'bg-gradient-to-b from-cyan-950/70 to-slate-900 border-cyan-500 ring-2 ring-cyan-500/40 shadow-lg shadow-cyan-500/20'
                  : 'bg-slate-900/80 hover:bg-slate-850 border-slate-800 hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="w-8 h-8 rounded-xl bg-cyan-500/20 text-cyan-400 flex items-center justify-center border border-cyan-500/30">
                  <User className="w-4 h-4" />
                </div>
                {selectedRole === 'USER' && (
                  <CheckCircle2 className="w-4 h-4 text-cyan-400" />
                )}
              </div>
              <div className="font-bold text-sm text-white">2. User ID</div>
              <div className="text-[11px] text-slate-400 mt-0.5 leading-tight">
                Motor controls, tank & schedules
              </div>
            </button>
          </div>
        </div>

        {/* Login Form Card */}
        <div className="glass-panel p-6 sm:p-7 rounded-3xl border border-slate-800 shadow-2xl backdrop-blur-xl bg-slate-900/80">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3.5 rounded-xl bg-rose-950/80 border border-rose-800/60 text-rose-300 text-xs flex items-center gap-2.5 animate-shake">
                <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="space-y-1.5">
              <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                Email Address
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="admin@hydracontrol.io or operator@hydracontrol.io"
                  className="glass-input w-full pl-10 pr-4 py-2.5 rounded-xl text-sm"
                  required
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                Password
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="glass-input w-full pl-10 pr-4 py-2.5 rounded-xl text-sm"
                  required
                />
              </div>
            </div>

            <Button
              type="submit"
              variant="primary"
              size="lg"
              loading={loading}
              className="w-full mt-3 py-3 rounded-xl shadow-lg shadow-cyan-500/25 font-bold tracking-wide"
              icon={<ArrowRight className="w-4 h-4" />}
            >
              Sign In to HydraControl
            </Button>
          </form>
        </div>

        {/* Footer info */}
        <div className="text-center text-[11px] text-slate-500 space-y-1">
          <p>Local Controller Safety Priority &bull; Real-Time IoT Cloud</p>
          <p className="text-slate-600">APK / Android Mobile App Ready</p>
        </div>
      </div>
    </div>
  );
};
