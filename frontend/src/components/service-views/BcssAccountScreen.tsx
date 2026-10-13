import React from 'react';
import {
  ArrowLeft,
  Wallet,
  CreditCard,
  Plus,
  Crown,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useLanguage } from '../../context/LanguageContext';

interface BcssAccountScreenProps {
  onBack: () => void;
  onOpenAdminModal?: () => void;
}

export const BcssAccountScreen: React.FC<BcssAccountScreenProps> = ({
  onBack,
  onOpenAdminModal,
}) => {
  const { user } = useAuth();
  const { t, language } = useLanguage();
  const isAdmin = user?.role === 'SUPER_ADMIN' || user?.role === 'ORGANIZATION_ADMIN';

  return (
    <div className="space-y-4 animate-fade-in font-sans pb-dock-clearance">
      {/* Top Header Bar */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-100">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-all cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>{t.backToHome}</span>
        </button>

        <span className="px-2.5 py-1 rounded-xl bg-blue-50 border border-blue-200 text-[11px] font-black text-blue-700">
          Smart Motor OS Pro
        </span>
      </div>

      {/* Main Balance Card */}
      <div className="mobile-card p-5 bg-blue-600 text-white space-y-4 border border-blue-500">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-2xl bg-blue-700 flex items-center justify-center">
              <Wallet className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="text-xs font-black tracking-wide text-blue-100">
                {language === 'hi' ? 'BCSS खाता वॉलेट' : 'BCSS Account Wallet'}
              </div>
              <div className="text-[10px] text-blue-200">
                {language === 'hi'
                  ? 'प्रीपेड यूटिलिटी एवं क्लाउड टेलीमेट्री बैलेंस'
                  : 'Prepaid Utility & Cloud Telemetry Balance'}
              </div>
            </div>
          </div>
          <span className="px-2 py-0.5 rounded-lg bg-emerald-500 text-white text-[10px] font-bold">
            {language === 'hi' ? 'सक्रिय' : 'ACTIVE'}
          </span>
        </div>

        <div className="pt-2">
          <div className="text-[11px] font-medium text-blue-200">
            {t.walletBalance}
          </div>
          <div className="text-3xl font-black tracking-tight font-mono mt-0.5">
            ₹ 0.00
          </div>
        </div>

        <div className="pt-2 border-t border-blue-500 flex items-center gap-2">
          <button
            type="button"
            onClick={() =>
              alert(
                language === 'hi'
                  ? 'टॉप-अप गेटवे: BCSS रिचार्ज मॉड्यूल सक्रिय है।'
                  : 'Top-up gateway: BCSS recharge module active.'
              )
            }
            className="flex-1 py-2.5 px-3 rounded-xl bg-white text-blue-900 text-xs font-black flex items-center justify-center gap-1.5 active:scale-95 transition-all cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5 stroke-[3]" />
            <span>{language === 'hi' ? 'पैसे जोड़ें / टॉप-अप' : 'Add Funds / Top-Up'}</span>
          </button>
          {isAdmin && onOpenAdminModal && (
            <button
              type="button"
              onClick={onOpenAdminModal}
              className="py-2.5 px-3 rounded-xl bg-blue-700 hover:bg-blue-800 text-white text-xs font-bold flex items-center gap-1 transition-colors cursor-pointer"
            >
              <Crown className="w-3.5 h-3.5 text-amber-300" />
              <span>{language === 'hi' ? 'एडमिन कोटा' : 'Admin Quotas'}</span>
            </button>
          )}
        </div>
      </div>

      {/* Subscription Tier Details */}
      <div className="mobile-card p-4 space-y-3">
        <div className="flex items-center justify-between pb-2 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-xl bg-blue-50 text-blue-700">
              <CreditCard className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-xs font-black text-slate-900 uppercase">
                {language === 'hi' ? 'सब्सक्रिप्शन प्लान' : 'Subscription Plan'}
              </h3>
              <p className="text-[10px] text-slate-400">Enterprise HydraControl Cloud</p>
            </div>
          </div>
          <span className="px-2 py-0.5 rounded-lg bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px] font-bold">
            {language === 'hi' ? 'ऑटो-रिन्यू चालू' : 'Auto-Renew ON'}
          </span>
        </div>

        <div className="space-y-2 text-xs">
          <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 border border-slate-100">
            <span className="text-slate-600 font-medium">
              {language === 'hi' ? 'IoT स्टेशन कोटा' : 'IoT Station Quota'}
            </span>
            <span className="font-bold text-slate-900">
              {language === 'hi' ? 'असीमित स्टेशन्स' : 'Unlimited Stations'}
            </span>
          </div>
          <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 border border-slate-100">
            <span className="text-slate-600 font-medium">
              {language === 'hi' ? 'वेबसॉकेट लाइव स्ट्रीमिंग' : 'WebSocket Live Streaming'}
            </span>
            <span className="font-bold text-emerald-600">
              {language === 'hi' ? 'सक्रिय (रीयल-टाइम)' : 'Active (Real-time)'}
            </span>
          </div>
          <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 border border-slate-100">
            <span className="text-slate-600 font-medium">
              {language === 'hi' ? 'ऐतिहासिक डेटा संग्रहण' : 'Historical Analytics Retention'}
            </span>
            <span className="font-bold text-slate-900">
              {language === 'hi' ? '365 दिन' : '365 Days'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
