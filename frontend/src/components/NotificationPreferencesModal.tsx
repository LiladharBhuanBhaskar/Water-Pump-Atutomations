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
  Check,
  Volume2,
} from 'lucide-react';
import { NotificationSeverity } from '../types';
import { api } from '../services/api';
import { audioAlert } from '../utils/audioAlert';
import { useLanguage } from '../context/LanguageContext';

interface NotificationPreferencesModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const NotificationPreferencesModal: React.FC<NotificationPreferencesModalProps> = ({
  isOpen,
  onClose,
}) => {
  const { t, language } = useLanguage();
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
      setMessage({
        type: 'success',
        text: language === 'hi' ? 'सूचना प्राथमिकताएं सफलतापूर्वक सहेजी गईं।' : 'Notification preferences saved successfully.',
      });
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
        text: language === 'hi'
          ? `परीक्षण सूचना ${res.delivered_channels.join(', ')} द्वारा भेजी गई।`
          : `Test notification sent via ${res.delivered_channels.join(', ')}.`,
      });
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Failed to dispatch test notification.' });
    } finally {
      setTesting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-slate-950/60 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-lg bg-white sm:rounded-2xl rounded-t-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[90dvh] font-sans">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 bg-slate-50/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-amber-50 text-amber-700 flex items-center justify-center">
              <Bell className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-black text-slate-900 tracking-tight leading-tight">
                {language === 'hi' ? 'सूचना अलर्ट सेटिंग्स' : 'Notification Settings'}
              </h2>
              <p className="text-xs text-slate-400 font-medium">
                {language === 'hi'
                  ? 'अलर्ट माध्यम व संवेदनशीलता सीमा कॉन्फ़िगर करें'
                  : 'Configure alert channels & severity thresholds'}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4">
          {loading ? (
            <div className="py-12 text-center text-slate-400 space-y-2">
              <RotateCw className="w-6 h-6 animate-spin mx-auto text-teal-600" />
              <p className="text-xs font-semibold">
                {language === 'hi' ? 'प्राथमिकताएं लोड हो रही हैं...' : 'Loading your notification preferences...'}
              </p>
            </div>
          ) : (
            <>
              {message && (
                <div
                  className={`flex items-center gap-2 p-3 rounded-2xl text-xs font-semibold border animate-in fade-in duration-150 ${
                    message.type === 'success'
                      ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                      : 'bg-rose-50 border-rose-200 text-rose-700'
                  }`}
                >
                  {message.type === 'success' ? (
                    <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-500" />
                  ) : (
                    <AlertTriangle className="w-4 h-4 shrink-0 text-rose-500" />
                  )}
                  <span>{message.text}</span>
                </div>
              )}

              {/* Delivery Channels */}
              <div className="space-y-2.5">
                <label className="block text-xs font-black uppercase tracking-wider text-slate-400">
                  {language === 'hi' ? 'सक्रिय सूचना माध्यम' : 'Active Delivery Channels'}
                </label>

                <div className="space-y-2">
                  {/* In-App Alerts */}
                  <div
                    onClick={() => setInAppEnabled(!inAppEnabled)}
                    className={`p-3.5 rounded-2xl border transition-all flex items-center justify-between cursor-pointer ${
                      inAppEnabled
                        ? 'bg-teal-50/40 border-teal-200/90 shadow-xs'
                        : 'bg-white border-slate-200/80 hover:bg-slate-50/50'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center shrink-0">
                        <Smartphone className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="text-xs font-bold text-slate-900">
                          {language === 'hi' ? 'ऐप में अलर्ट' : 'In-App Alerts'}
                        </div>
                        <div className="text-[11px] text-slate-500">
                          {language === 'hi'
                            ? 'रीयल-टाइम ब्राउज़र एवं मोबाइल स्क्रीन अलर्ट'
                            : 'Real-time browser & mobile toast alerts'}
                        </div>
                      </div>
                    </div>
                    <div
                      className={`w-5 h-5 rounded-lg flex items-center justify-center transition-all ${
                        inAppEnabled
                          ? 'bg-teal-600 text-white shadow-xs'
                          : 'border-2 border-slate-300 bg-white'
                      }`}
                    >
                      {inAppEnabled && <Check className="w-3.5 h-3.5 stroke-[3]" />}
                    </div>
                  </div>

                  {/* Email Digest & Alerts */}
                  <div
                    onClick={() => setEmailEnabled(!emailEnabled)}
                    className={`p-3.5 rounded-2xl border transition-all flex items-center justify-between cursor-pointer ${
                      emailEnabled
                        ? 'bg-teal-50/40 border-teal-200/90 shadow-xs'
                        : 'bg-white border-slate-200/80 hover:bg-slate-50/50'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-xl bg-teal-50 text-teal-600 flex items-center justify-center shrink-0">
                        <Mail className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="text-xs font-bold text-slate-900">
                          {language === 'hi' ? 'ईमेल अलर्ट व डाइजेस्ट' : 'Email Digest & Alerts'}
                        </div>
                        <div className="text-[11px] text-slate-500">
                          {language === 'hi'
                            ? 'सुरक्षा ट्रिप चेतावनी एवं दैनिक रिपोर्ट'
                            : 'Safety trip warnings and daily digests'}
                        </div>
                      </div>
                    </div>
                    <div
                      className={`w-5 h-5 rounded-lg flex items-center justify-center transition-all ${
                        emailEnabled
                          ? 'bg-teal-600 text-white shadow-xs'
                          : 'border-2 border-slate-300 bg-white'
                      }`}
                    >
                      {emailEnabled && <Check className="w-3.5 h-3.5 stroke-[3]" />}
                    </div>
                  </div>

                  {/* SMS High-Priority Dispatch */}
                  <div
                    onClick={() => setSmsEnabled(!smsEnabled)}
                    className={`p-3.5 rounded-2xl border transition-all flex items-center justify-between cursor-pointer ${
                      smsEnabled
                        ? 'bg-teal-50/40 border-teal-200/90 shadow-xs'
                        : 'bg-white border-slate-200/80 hover:bg-slate-50/50'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center shrink-0">
                        <MessageSquare className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="text-xs font-bold text-slate-900">
                          {language === 'hi' ? 'एसएमएस उच्च-प्राथमिकता अलर्ट' : 'SMS High-Priority Dispatch'}
                        </div>
                        <div className="text-[11px] text-slate-500">
                          {language === 'hi'
                            ? 'आपातकालीन स्टॉप एवं गंभीर ड्राय-रन अलर्ट'
                            : 'Emergency stop & critical dry-run alerts'}
                        </div>
                      </div>
                    </div>
                    <div
                      className={`w-5 h-5 rounded-lg flex items-center justify-center transition-all ${
                        smsEnabled
                          ? 'bg-teal-600 text-white shadow-xs'
                          : 'border-2 border-slate-300 bg-white'
                      }`}
                    >
                      {smsEnabled && <Check className="w-3.5 h-3.5 stroke-[3]" />}
                    </div>
                  </div>
                </div>
              </div>

              {/* Minimum Severity Filter */}
              <div className="space-y-2 pt-1">
                <label className="block text-xs font-black uppercase tracking-wider text-slate-400">
                  {language === 'hi' ? 'न्यूनतम अलर्ट गंभीरता' : 'Minimum Alert Severity'}
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {(['INFO', 'WARNING', 'CRITICAL'] as NotificationSeverity[]).map((level) => {
                    const isSelected = minSeverity === level;
                    const levelLabel =
                      language === 'hi'
                        ? level === 'CRITICAL'
                          ? 'गंभीर'
                          : level === 'WARNING'
                          ? 'चेतावनी'
                          : 'सूचना'
                        : level;
                    return (
                      <button
                        key={level}
                        type="button"
                        onClick={() => setMinSeverity(level)}
                        className={`py-2.5 rounded-xl border text-xs font-bold transition-all text-center cursor-pointer ${
                          isSelected
                            ? level === 'CRITICAL'
                              ? 'bg-rose-600 text-white border-rose-600 shadow-xs'
                              : level === 'WARNING'
                              ? 'bg-amber-500 text-white border-amber-500 shadow-xs'
                              : 'bg-teal-600 text-white border-teal-600 shadow-xs'
                            : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50 hover:text-slate-900'
                        }`}
                      >
                        {levelLabel}
                      </button>
                    );
                  })}
                </div>
                <p className="text-[11px] text-slate-400">
                  {language === 'hi'
                    ? 'आपको केवल चुनी गई गंभीरता या उससे ऊपर के अलर्ट प्राप्त होंगे।'
                    : 'You will only receive dispatches equal to or above the selected severity level.'}
                </p>
              </div>

              {/* Test Actions */}
              <div className="pt-2 border-t border-slate-100 space-y-2">
                <button
                  type="button"
                  onClick={async () => {
                    await audioAlert.testSound('INFO');
                    setMessage({
                      type: 'success',
                      text: language === 'hi'
                        ? 'ब्राउज़र वेब ऑडियो द्वारा परीक्षण ध्वनि सफलतापूर्वक बजाई गई।'
                        : 'Audible chime played successfully via Web Audio API.',
                    });
                  }}
                  className="w-full py-2.5 rounded-xl border border-teal-200 bg-teal-50/60 hover:bg-teal-100 text-teal-800 text-xs font-bold flex items-center justify-center gap-2 transition-colors shadow-xs cursor-pointer"
                >
                  <Volume2 className="w-4 h-4 text-teal-600" />
                  <span>{language === 'hi' ? 'अलर्ट साउंड जांचें 🔊' : 'Test Browser Alert Sound 🔊'}</span>
                </button>

                <button
                  type="button"
                  onClick={handleTestDispatch}
                  disabled={testing}
                  className="w-full py-2.5 rounded-xl border border-slate-200 hover:bg-slate-100 text-slate-700 text-xs font-bold flex items-center justify-center gap-2 transition-colors cursor-pointer"
                >
                  <Send className={`w-3.5 h-3.5 text-slate-500 ${testing ? 'animate-spin' : ''}`} />
                  <span>
                    {testing
                      ? (language === 'hi' ? 'परीक्षण अलर्ट भेजा जा रहा है...' : 'Dispatching Test Alert...')
                      : (language === 'hi' ? 'परीक्षण सूचना भेजें' : 'Send Test Notification')}
                  </span>
                </button>
              </div>
            </>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-5 py-3 border-t border-slate-100 bg-slate-50/50 flex items-center justify-end gap-2.5 pb-[max(0.75rem,env(safe-area-inset-bottom,0px))]">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-colors cursor-pointer"
          >
            {t.cancel}
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || loading}
            className="px-5 py-2 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold shadow-md shadow-teal-600/25 transition-all flex items-center gap-1.5 disabled:opacity-50 cursor-pointer"
          >
            {saving ? <RotateCw className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5 stroke-[3]" />}
            <span>{saving ? t.saving : (language === 'hi' ? 'प्राथमिकताएं सहेजें' : 'Save Preferences')}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
