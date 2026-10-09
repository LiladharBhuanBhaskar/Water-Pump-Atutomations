import React, { useState } from 'react';
import {
  Droplets,
  Lock,
  Mail,
  AlertCircle,
  ArrowRight,
  Shield,
  User,
  Sparkles,
  CheckCircle2,
  Globe,
  RefreshCw,
  Check,
  Wifi,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/common/Button';
import { getServerBaseUrl } from '../services/api';

export const Login: React.FC = () => {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedRole, setSelectedRole] = useState<'ADMIN' | 'USER' | null>(null);

  // Server Connection Configuration (for Android APK / LAN / Cloud)
  const [serverUrl, setServerUrl] = useState<string>(() => {
    return getServerBaseUrl() || 'http://192.168.1.13:8000';
  });
  const [showServerConfig, setShowServerConfig] = useState<boolean>(false);
  const [isTestingServer, setIsTestingServer] = useState<boolean>(false);
  const [serverTestStatus, setServerTestStatus] = useState<'IDLE' | 'SUCCESS' | 'FAILED'>('IDLE');
  const [serverTestMessage, setServerTestMessage] = useState<string | null>(null);

  const handleSaveServerUrl = (url: string) => {
    setServerUrl(url);
    if (url.trim()) {
      localStorage.setItem('hydra_server_url', url.trim().replace(/\/+$/, ''));
    } else {
      localStorage.removeItem('hydra_server_url');
    }
  };

  const handleTestConnection = async () => {
    setIsTestingServer(true);
    setServerTestStatus('IDLE');
    setServerTestMessage(null);
    const target = serverUrl.trim().replace(/\/+$/, '');
    try {
      const startTime = Date.now();
      const res = await fetch(`${target}/health/live`, { method: 'GET' });
      const latency = Date.now() - startTime;
      if (res.ok) {
        setServerTestStatus('SUCCESS');
        setServerTestMessage(`✓ Connected successfully! (${latency}ms)`);
        localStorage.setItem('hydra_server_url', target);
      } else {
        setServerTestStatus('FAILED');
        setServerTestMessage(`HTTP ${res.status}: Server returned error.`);
      }
    } catch (err: any) {
      setServerTestStatus('FAILED');
      setServerTestMessage(`Cannot connect to ${target}. Ensure laptop & phone are on the same Wi-Fi.`);
    } finally {
      setIsTestingServer(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Please enter both email and password.');
      return;
    }

    if (serverUrl.trim()) {
      localStorage.setItem('hydra_server_url', serverUrl.trim().replace(/\/+$/, ''));
    }

    setError(null);
    setLoading(true);
    try {
      await login(email, password);
    } catch (err: any) {
      setError(err.message || 'Login failed. Please check credentials or Server IP.');
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

          {/* Server Connection Settings Accordion (Essential for APK / LAN / Wi-Fi) */}
          <div className="mt-5 pt-4 border-t border-slate-800/80">
            <button
              type="button"
              onClick={() => setShowServerConfig(!showServerConfig)}
              className="w-full flex items-center justify-between text-xs text-slate-400 hover:text-cyan-400 transition-colors py-1"
            >
              <div className="flex items-center gap-2">
                <Wifi className="w-3.5 h-3.5 text-cyan-400" />
                <span className="font-semibold">Server Connection (Wi-Fi / Cloud)</span>
              </div>
              <span className="text-[10px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full font-mono">
                {showServerConfig ? 'Hide' : 'Configure IP'}
              </span>
            </button>

            {showServerConfig && (
              <div className="mt-3 p-3.5 rounded-2xl bg-slate-950/70 border border-slate-800/80 space-y-3 animate-fadeIn">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                    <Globe className="w-3 h-3 text-cyan-400" /> Backend Host URL
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={serverUrl}
                      onChange={(e) => handleSaveServerUrl(e.target.value)}
                      placeholder="http://192.168.1.13:8000"
                      className="glass-input flex-1 px-3 py-2 rounded-xl text-xs font-mono"
                    />
                    <button
                      type="button"
                      onClick={handleTestConnection}
                      disabled={isTestingServer || !serverUrl}
                      className="px-3 py-2 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 text-xs font-semibold border border-cyan-500/30 flex items-center gap-1.5 disabled:opacity-50 transition-all"
                    >
                      {isTestingServer ? (
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Check className="w-3.5 h-3.5" />
                      )}
                      Test
                    </button>
                  </div>
                  <p className="text-[10px] text-slate-500">
                    Default Wi-Fi IP: <code className="text-cyan-400">http://192.168.1.13:8000</code>
                  </p>
                </div>

                {serverTestStatus !== 'IDLE' && (
                  <div
                    className={`p-2.5 rounded-xl text-xs flex items-center gap-2 ${
                      serverTestStatus === 'SUCCESS'
                        ? 'bg-emerald-950/80 border border-emerald-800/60 text-emerald-300'
                        : 'bg-rose-950/80 border border-rose-800/60 text-rose-300'
                    }`}
                  >
                    {serverTestStatus === 'SUCCESS' ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                    ) : (
                      <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                    )}
                    <span className="text-[11px]">{serverTestMessage}</span>
                  </div>
                )}
              </div>
            )}
          </div>
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
