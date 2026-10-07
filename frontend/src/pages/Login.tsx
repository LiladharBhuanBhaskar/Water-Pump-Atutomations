import React, { useState } from 'react';
import { Droplets, Lock, Mail, AlertCircle, ArrowRight } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/common/Button';

export const Login: React.FC = () => {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

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

  const handleQuickLogin = (quickEmail: string) => {
    setEmail(quickEmail);
    setPassword('SecretPass123!');
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col justify-center items-center p-4 relative overflow-hidden selection:bg-cyan-500 selection:text-black">
      {/* Subtle Background Glows */}
      <div className="absolute -top-40 -left-40 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl pointer-events-none" />

      <div className="w-full max-w-md space-y-8 z-10">
        {/* Header Branding */}
        <div className="text-center space-y-3">
          <div className="inline-flex w-16 h-16 rounded-2xl bg-gradient-to-tr from-cyan-500 to-blue-600 items-center justify-center shadow-xl shadow-cyan-500/25">
            <Droplets className="w-9 h-9 text-white" />
          </div>
          <h1 className="text-3xl font-extrabold bg-gradient-to-r from-white via-slate-100 to-cyan-400 bg-clip-text text-transparent">
            HydraControl
          </h1>
          <p className="text-sm text-slate-400 font-medium">
            Commercial IoT Automation Platform &bull; Cloud Controls, Local Controller Protects
          </p>
        </div>

        {/* Login Card */}
        <div className="glass-panel p-8 rounded-3xl border border-slate-800 shadow-2xl">
          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="p-3.5 rounded-xl bg-rose-950/80 border border-rose-800/60 text-rose-300 text-xs flex items-center gap-2.5">
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
                  placeholder="operator@example.com"
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
              className="w-full mt-2"
              icon={<ArrowRight className="w-4 h-4" />}
            >
              Sign In to Station
            </Button>
          </form>

          {/* Demo User Quick Selection */}
          <div className="mt-8 pt-6 border-t border-slate-800/80">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 text-center mb-3">
              Quick Test Identities (Seed Demo)
            </p>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <button
                type="button"
                onClick={() => handleQuickLogin('admin@hydracontrol.io')}
                className="p-2 rounded-xl bg-slate-800/60 hover:bg-slate-700 text-slate-300 text-left border border-slate-700/60 transition-colors"
              >
                <div className="font-bold text-white">Super Admin</div>
                <div className="text-[10px] text-purple-400">All access</div>
              </button>
              <button
                type="button"
                onClick={() => handleQuickLogin('operator@hydracontrol.io')}
                className="p-2 rounded-xl bg-slate-800/60 hover:bg-slate-700 text-slate-300 text-left border border-slate-700/60 transition-colors"
              >
                <div className="font-bold text-white">Operator</div>
                <div className="text-[10px] text-emerald-400">Pump control</div>
              </button>
              <button
                type="button"
                onClick={() => handleQuickLogin('manager@hydracontrol.io')}
                className="p-2 rounded-xl bg-slate-800/60 hover:bg-slate-700 text-slate-300 text-left border border-slate-700/60 transition-colors"
              >
                <div className="font-bold text-white">Site Manager</div>
                <div className="text-[10px] text-cyan-400">Site oversight</div>
              </button>
              <button
                type="button"
                onClick={() => handleQuickLogin('viewer@hydracontrol.io')}
                className="p-2 rounded-xl bg-slate-800/60 hover:bg-slate-700 text-slate-300 text-left border border-slate-700/60 transition-colors"
              >
                <div className="font-bold text-white">Viewer</div>
                <div className="text-[10px] text-slate-400">Read only</div>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
