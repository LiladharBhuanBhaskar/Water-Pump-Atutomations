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
import { DEFAULT_CLOUDFLARE_URL } from '../services/api';

export const Login: React.FC = () => {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedRole, setSelectedRole] = useState<'ADMIN' | 'USER' | null>(null);

  // Cloudflare Remote Tunnel & Server Connection (Unified for APK & Web)
  const [serverUrl, setServerUrl] = useState<string>(() => {
    const saved =
      localStorage.getItem('hydra_server_url') ||
      localStorage.getItem('hydra_mobile_server_url') ||
      localStorage.getItem('hydra_web_custom_server');
    if (saved && saved.trim()) {
      const clean = saved.trim().replace(/\/+$/, '');
      if (clean.includes('trycloudflare.com') && clean !== DEFAULT_CLOUDFLARE_URL) {
        localStorage.setItem('hydra_server_url', DEFAULT_CLOUDFLARE_URL);
        localStorage.setItem('hydra_mobile_server_url', DEFAULT_CLOUDFLARE_URL);
        localStorage.setItem('hydra_web_custom_server', DEFAULT_CLOUDFLARE_URL);
        return DEFAULT_CLOUDFLARE_URL;
      }
      return clean;
    }
    return DEFAULT_CLOUDFLARE_URL;
  });
  const [showServerConfig, setShowServerConfig] = useState<boolean>(false);
  const [isTestingServer, setIsTestingServer] = useState<boolean>(false);
  const [serverTestStatus, setServerTestStatus] = useState<'IDLE' | 'SUCCESS' | 'FAILED'>('IDLE');
  const [serverTestMessage, setServerTestMessage] = useState<string | null>(null);

  const handleSaveServerUrl = (url: string) => {
    const clean = (url.trim() || DEFAULT_CLOUDFLARE_URL).replace(/\/+$/, '');
    setServerUrl(clean);
    localStorage.setItem('hydra_server_url', clean);
    localStorage.setItem('hydra_mobile_server_url', clean);
    localStorage.setItem('hydra_web_custom_server', clean);
  };

  const handleResetServerUrl = () => {
    setServerUrl(DEFAULT_CLOUDFLARE_URL);
    localStorage.setItem('hydra_server_url', DEFAULT_CLOUDFLARE_URL);
    localStorage.setItem('hydra_mobile_server_url', DEFAULT_CLOUDFLARE_URL);
    localStorage.setItem('hydra_web_custom_server', DEFAULT_CLOUDFLARE_URL);
    setServerTestStatus('IDLE');
    setServerTestMessage(null);
  };

  const handleTestConnection = async () => {
    setIsTestingServer(true);
    setServerTestStatus('IDLE');
    setServerTestMessage(null);
    const target = (serverUrl.trim() || DEFAULT_CLOUDFLARE_URL).replace(/\/+$/, '');
    const pingEndpoint = `${target}/health/live`;
    try {
      const startTime = Date.now();
      const res = await fetch(pingEndpoint, { method: 'GET' });
      const latency = Date.now() - startTime;
      if (res.ok) {
        setServerTestStatus('SUCCESS');
        setServerTestMessage(`✓ Connected successfully! (${latency}ms)`);
        localStorage.setItem('hydra_server_url', target);
        localStorage.setItem('hydra_mobile_server_url', target);
        localStorage.setItem('hydra_web_custom_server', target);
      } else {
        setServerTestStatus('FAILED');
        setServerTestMessage(`HTTP ${res.status}: Server returned error.`);
      }
    } catch (err: any) {
      setServerTestStatus('FAILED');
      setServerTestMessage(`Cannot connect to ${target}. Check internet/Wi-Fi or tunnel status.`);
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

    const clean = (serverUrl.trim() || DEFAULT_CLOUDFLARE_URL).replace(/\/+$/, '');
    localStorage.setItem('hydra_server_url', clean);
    localStorage.setItem('hydra_mobile_server_url', clean);
    localStorage.setItem('hydra_web_custom_server', clean);

    setError(null);
    setLoading(true);
    try {
      await login(email, password);
    } catch (err: any) {
      setError(err.message || 'Login failed. Please check credentials or Server Host URL.');
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
    <div className="min-h-screen bg-[#f8fafc] text-slate-900 flex flex-col justify-center items-center p-4 sm:p-6 pt-[calc(1.25rem+env(safe-area-inset-top,0px))] pb-[calc(1.25rem+env(safe-area-inset-bottom,0px))] font-sans selection:bg-blue-500 selection:text-white">
      <div className="w-full max-w-md space-y-5">
        {/* Branding Header */}
        <div className="text-center space-y-1.5">
          <div className="inline-flex w-14 h-14 rounded-2xl bg-blue-600 items-center justify-center border border-blue-500 text-white mb-1">
            <Droplets className="w-7 h-7" />
          </div>
          <h1 className="text-2xl font-black tracking-tight text-slate-900">
            HydraControl
          </h1>
          <p className="text-xs text-slate-500 font-medium">
            Smart Water Motor Automation &amp; Protection System
          </p>
        </div>

        {/* 2 Primary Access Cards: Admin vs Motor Operator */}
        <div className="space-y-2">
          <p className="text-[11px] font-black uppercase tracking-wider text-slate-400 text-center flex items-center justify-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-blue-600" />
            <span>Select Account Preset</span>
          </p>
          <div className="grid grid-cols-2 gap-2.5">
            {/* ID 1: ADMIN */}
            <button
              type="button"
              onClick={() => handleSelectRole('ADMIN')}
              className={`p-3.5 rounded-2xl border text-left transition-all duration-200 relative cursor-pointer ${
                selectedRole === 'ADMIN'
                  ? 'bg-purple-50/70 border-purple-500 ring-1 ring-purple-500/30'
                  : 'bg-white hover:bg-slate-50 border-slate-200 text-slate-700'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="w-8 h-8 rounded-xl bg-purple-100 text-purple-700 flex items-center justify-center">
                  <Shield className="w-4 h-4" />
                </div>
                {selectedRole === 'ADMIN' && (
                  <CheckCircle2 className="w-4 h-4 text-purple-600" />
                )}
              </div>
              <div className="font-bold text-xs text-slate-900">1. Admin ID</div>
              <div className="text-[10px] text-slate-500 mt-0.5 leading-tight">
                Full settings, rules, fleet &amp; plans
              </div>
            </button>

            {/* ID 2: USER (MOTOR OPERATOR) */}
            <button
              type="button"
              onClick={() => handleSelectRole('USER')}
              className={`p-3.5 rounded-2xl border text-left transition-all duration-200 relative cursor-pointer ${
                selectedRole === 'USER'
                  ? 'bg-blue-50/70 border-blue-500 ring-1 ring-blue-500/30'
                  : 'bg-white hover:bg-slate-50 border-slate-200 text-slate-700'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="w-8 h-8 rounded-xl bg-blue-100 text-blue-700 flex items-center justify-center">
                  <User className="w-4 h-4" />
                </div>
                {selectedRole === 'USER' && (
                  <CheckCircle2 className="w-4 h-4 text-blue-600" />
                )}
              </div>
              <div className="font-bold text-xs text-slate-900">2. Operator ID</div>
              <div className="text-[10px] text-slate-500 mt-0.5 leading-tight">
                Motor controls, tank &amp; schedules
              </div>
            </button>
          </div>
        </div>

        {/* Login Form Card */}
        <div className="p-5 sm:p-6 rounded-3xl border border-slate-200 bg-white">
          <form onSubmit={handleSubmit} className="space-y-3.5">
            {error && (
              <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex flex-col gap-2">
                <div className="flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-rose-500 flex-shrink-0 mt-0.5" />
                  <span className="leading-relaxed">{error}</span>
                </div>
                {(error.toLowerCase().includes('resolve host') ||
                  error.toLowerCase().includes('connect') ||
                  error.toLowerCase().includes('failed to fetch') ||
                  error.toLowerCase().includes('no address associated')) && (
                  <button
                    type="button"
                    onClick={() => {
                      handleResetServerUrl();
                      setError(null);
                    }}
                    className="self-start px-2.5 py-1 rounded-lg bg-rose-600 hover:bg-rose-700 text-white font-bold text-[11px] transition-colors cursor-pointer flex items-center gap-1 shadow-xs"
                  >
                    <span>⚡ Reset to Live Server URL</span>
                  </button>
                )}
              </div>
            )}

            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-700">
                Email Address
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="admin@hydracontrol.io or operator@hydracontrol.io"
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-200 bg-slate-50/50 focus:bg-white focus:border-blue-500 focus:outline-none text-xs font-medium text-slate-900 transition-colors"
                  required
                />
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-700">
                Password
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-200 bg-slate-50/50 focus:bg-white focus:border-blue-500 focus:outline-none text-xs font-medium text-slate-900 transition-colors"
                  required
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs flex items-center justify-center gap-2 transition-colors cursor-pointer disabled:opacity-50"
            >
              {loading ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <ArrowRight className="w-4 h-4" />
              )}
              <span>{loading ? 'Authenticating...' : 'Sign In to HydraControl'}</span>
            </button>
          </form>

          {/* Server Connection Settings Accordion (Essential for APK / LAN / Wi-Fi) */}
          <div className="mt-4 pt-3.5 border-t border-slate-100">
            <button
              type="button"
              onClick={() => setShowServerConfig(!showServerConfig)}
              className="w-full flex items-center justify-between text-xs text-slate-500 hover:text-blue-600 transition-colors py-1 cursor-pointer"
            >
              <div className="flex items-center gap-1.5">
                <Wifi className="w-3.5 h-3.5 text-blue-600" />
                <span className="font-bold">Server Connection</span>
                <span className="w-2 h-2 rounded-full bg-emerald-500" title="Active Host Configured" />
              </div>
              <span className="text-[10px] bg-blue-50 text-blue-700 border border-blue-200 px-2 py-0.5 rounded-full font-mono font-bold">
                {showServerConfig ? 'Hide' : 'Change Server'}
              </span>
            </button>
            <div className="text-[10px] text-slate-400 font-mono truncate px-1">
              Active Host: <span className="text-slate-600 font-semibold">{serverUrl || DEFAULT_CLOUDFLARE_URL}</span>
            </div>

            {showServerConfig && (
              <div className="mt-2.5 p-3 rounded-2xl bg-slate-50 border border-slate-200 space-y-2.5">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                    <Globe className="w-3 h-3 text-blue-600" /> Backend Host URL
                  </label>
                  <div className="flex gap-1.5">
                    <input
                      type="text"
                      value={serverUrl}
                      onChange={(e) => handleSaveServerUrl(e.target.value)}
                      placeholder={DEFAULT_CLOUDFLARE_URL}
                      className="flex-1 px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-xs font-mono text-slate-800 focus:outline-none focus:border-blue-500"
                    />
                    <button
                      type="button"
                      onClick={handleTestConnection}
                      disabled={isTestingServer}
                      className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold flex items-center gap-1 disabled:opacity-50 transition-colors cursor-pointer"
                    >
                      {isTestingServer ? (
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Check className="w-3.5 h-3.5" />
                      )}
                      <span>Test</span>
                    </button>
                    <button
                      type="button"
                      onClick={handleResetServerUrl}
                      className="px-2.5 py-1.5 rounded-lg bg-white hover:bg-slate-100 text-slate-600 text-xs font-medium border border-slate-200 transition-colors cursor-pointer"
                      title="Reset to default Cloudflare tunnel"
                    >
                      Reset
                    </button>
                  </div>
                  <div className="flex gap-2 pt-1">
                    <button
                      type="button"
                      onClick={() => handleSaveServerUrl(DEFAULT_CLOUDFLARE_URL)}
                      className="px-2.5 py-1 rounded-lg bg-blue-50 hover:bg-blue-100 border border-blue-200 text-blue-700 text-[10px] font-bold cursor-pointer"
                    >
                      🌐 Cloudflare (Worldwide)
                    </button>
                    <button
                      type="button"
                      onClick={() => handleSaveServerUrl('http://192.168.1.13:8000')}
                      className="px-2.5 py-1 rounded-lg bg-white hover:bg-slate-100 border border-slate-200 text-slate-700 text-[10px] font-medium cursor-pointer"
                    >
                      📶 Local Wi-Fi
                    </button>
                  </div>
                </div>

                {serverTestStatus !== 'IDLE' && (
                  <div
                    className={`p-2 rounded-xl text-xs flex items-center gap-2 ${
                      serverTestStatus === 'SUCCESS'
                        ? 'bg-emerald-50 border border-emerald-200 text-emerald-800 font-medium'
                        : 'bg-rose-50 border border-rose-200 text-rose-800'
                    }`}
                  >
                    {serverTestStatus === 'SUCCESS' ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                    ) : (
                      <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
                    )}
                    <span className="text-[11px]">{serverTestMessage}</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Footer info */}
        <div className="text-center text-[11px] text-slate-400 space-y-0.5">
          <p>Local Controller Safety Priority &bull; Real-Time IoT Cloud</p>
          <p className="text-slate-400">APK / Android Mobile App Ready</p>
        </div>
      </div>
    </div>
  );
};
