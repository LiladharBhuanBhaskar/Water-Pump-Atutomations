import React, { useState, useEffect, useCallback } from 'react';
import {
  X,
  Bell,
  Mail,
  MessageSquare,
  Smartphone,
  Send,
  CheckCircle2,
  AlertTriangle,
  RotateCw,
} from 'lucide-react';
import { NotificationSeverity } from '../types';
import { api } from '../services/api';
import { audioAlert } from '../utils/audioAlert';
import { Button } from './common/Button';

interface NotificationPreferencesModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const NotificationPreferencesModal: React.FC<NotificationPreferencesModalProps> = ({
  isOpen,
  onClose,
}) => {
  const [inAppEnabled, setInAppEnabled] = useState<boolean>(true);
  const [emailEnabled, setEmailEnabled] = useState<boolean>(true);
  const [smsEnabled, setSmsEnabled] = useState<boolean>(false);
  const [minSeverity, setMinSeverity] = useState<NotificationSeverity>('INFO');

  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [testing, setTesting] = useState<boolean>(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const loadPreferences = useCallback(async () => {
    if (!isOpen) return;
    try {
      setLoading(true);
      setMessage(null);
      const data = await api.getNotificationPreferences();
      setInAppEnabled(data.in_app_enabled);
      setEmailEnabled(data.email_enabled);
      setSmsEnabled(data.sms_enabled);
      setMinSeverity(data.min_severity);
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Failed to load preferences.' });
    } finally {
      setLoading(false);
    }
  }, [isOpen]);

  useEffect(() => {
    if (isOpen) {
      loadPreferences();
    }
  }, [isOpen, loadPreferences]);

  const handleSave = async () => {
    try {
      setSaving(true);
      setMessage(null);
      await api.updateNotificationPreferences({
        in_app_enabled: inAppEnabled,
        email_enabled: emailEnabled,
        sms_enabled: smsEnabled,
        min_severity: minSeverity,
      });
      setMessage({ type: 'success', text: 'Notification preferences saved successfully.' });
      setTimeout(() => {
        if (isOpen) setMessage(null);
      }, 3500);
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Failed to save preferences.' });
    } finally {
      setSaving(false);
    }
  };

  const handleTestDispatch = async () => {
    try {
      setTesting(true);
      setMessage(null);
      const res = await api.sendTestNotification();
      setMessage({
        type: 'success',
        text: `Test notification sent via ${res.delivered_channels.join(', ')}.`,
      });
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Failed to dispatch test notification.' });
    } finally {
      setTesting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-[#0f172a] border border-[#1e293b] rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden flex flex-col">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#1e293b] bg-[#131f37]">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-teal-500/10 text-teal-400 border border-teal-500/20">
              <Bell className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-100">Notification Settings</h2>
              <p className="text-xs text-slate-400">Configure alert channels & severity thresholds</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-5 flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-12 space-y-3">
              <RotateCw className="w-7 h-7 text-teal-400 animate-spin" />
              <p className="text-xs text-slate-400">Loading your notification preferences...</p>
            </div>
          ) : (
            <>
              {message && (
                <div
                  className={`p-3.5 rounded-xl text-xs flex items-center gap-2.5 border ${
                    message.type === 'success'
                      ? 'bg-teal-500/10 border-teal-500/20 text-teal-300'
                      : 'bg-rose-500/10 border-rose-500/20 text-rose-300'
                  }`}
                >
                  {message.type === 'success' ? (
                    <CheckCircle2 className="w-4 h-4 shrink-0 text-teal-400" />
                  ) : (
                    <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
                  )}
                  <span>{message.text}</span>
                </div>
              )}

              {/* Delivery Channels */}
              <div className="space-y-3">
                <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                  Active Delivery Channels
                </label>

                <div className="space-y-2">
                  {/* In-App */}
                  <label className="flex items-center justify-between p-3 rounded-xl bg-[#1e293b]/60 border border-[#334155]/60 cursor-pointer hover:bg-[#1e293b] transition-colors">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400">
                        <Smartphone className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="text-sm font-medium text-white">In-App Alerts</div>
                        <div className="text-xs text-slate-400">Real-time browser & mobile toast alerts</div>
                      </div>
                    </div>
                    <input
                      type="checkbox"
                      checked={inAppEnabled}
                      onChange={(e) => setInAppEnabled(e.target.checked)}
                      className="w-4 h-4 rounded border-slate-600 text-teal-500 focus:ring-teal-400"
                    />
                  </label>

                  {/* Email */}
                  <label className="flex items-center justify-between p-3 rounded-xl bg-[#1e293b]/60 border border-[#334155]/60 cursor-pointer hover:bg-[#1e293b] transition-colors">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-teal-500/10 text-teal-400">
                        <Mail className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="text-sm font-medium text-white">Email Digest & Alerts</div>
                        <div className="text-xs text-slate-400">Safety trip warnings and daily digests</div>
                      </div>
                    </div>
                    <input
                      type="checkbox"
                      checked={emailEnabled}
                      onChange={(e) => setEmailEnabled(e.target.checked)}
                      className="w-4 h-4 rounded border-slate-600 text-teal-500 focus:ring-teal-400"
                    />
                  </label>

                  {/* SMS */}
                  <label className="flex items-center justify-between p-3 rounded-xl bg-[#1e293b]/60 border border-[#334155]/60 cursor-pointer hover:bg-[#1e293b] transition-colors">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400">
                        <MessageSquare className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="text-sm font-medium text-white">SMS High-Priority Dispatch</div>
                        <div className="text-xs text-slate-400">Emergency stop & critical dry-run alerts</div>
                      </div>
                    </div>
                    <input
                      type="checkbox"
                      checked={smsEnabled}
                      onChange={(e) => setSmsEnabled(e.target.checked)}
                      className="w-4 h-4 rounded border-slate-600 text-teal-500 focus:ring-teal-400"
                    />
                  </label>
                </div>
              </div>

              {/* Minimum Severity Filter */}
              <div className="space-y-2 pt-2">
                <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                  Minimum Alert Severity
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {(['INFO', 'WARNING', 'CRITICAL'] as NotificationSeverity[]).map((level) => (
                    <button
                      key={level}
                      type="button"
                      onClick={() => setMinSeverity(level)}
                      className={`p-2.5 rounded-xl border text-xs font-semibold transition-all ${
                        minSeverity === level
                          ? level === 'CRITICAL'
                            ? 'bg-rose-500/20 border-rose-500 text-rose-300 shadow-sm'
                            : level === 'WARNING'
                            ? 'bg-amber-500/20 border-amber-500 text-amber-300 shadow-sm'
                            : 'bg-teal-500/20 border-teal-500 text-teal-300 shadow-sm'
                          : 'bg-[#1e293b]/50 border-[#334155] text-slate-400 hover:text-white'
                      }`}
                    >
                      {level}
                    </button>
                  ))}
                </div>
                <p className="text-[11px] text-slate-500 mt-1">
                  You will only receive dispatches equal to or above the selected severity level.
                </p>
              </div>

              {/* Test Dispatch & Test Audio Sound Buttons */}
              <div className="pt-2 border-t border-[#1e293b] space-y-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={async () => {
                    await audioAlert.testSound('INFO');
                    setMessage({ type: 'success', text: 'Audible chime played successfully via Web Audio API.' });
                  }}
                  className="w-full border-teal-500/30 text-teal-300 hover:text-white hover:bg-teal-500/10"
                >
                  <Bell className="w-3.5 h-3.5 mr-2" />
                  Test Browser Alert Sound 🔊
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleTestDispatch}
                  disabled={testing}
                  className="w-full border-[#334155] text-slate-300 hover:text-white"
                >
                  <Send className={`w-3.5 h-3.5 mr-2 ${testing ? 'animate-spin' : ''}`} />
                  {testing ? 'Dispatching Test Alert...' : 'Send Test Notification'}
                </Button>
              </div>
            </>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-[#1e293b] bg-[#131f37] flex items-center justify-end gap-2.5">
          <Button variant="outline" size="sm" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button variant="primary" size="sm" onClick={handleSave} disabled={saving || loading}>
            {saving ? 'Saving...' : 'Save Preferences'}
          </Button>
        </div>
      </div>
    </div>
  );
};
