import React, { useState, useEffect } from 'react';
import {
  X,
  Sliders,
  Plus,
  Trash2,
  Lock,
  Save,
  AlertTriangle,
} from 'lucide-react';
import {
  Station,
  Motor,
  Sensor,
  StationSettingsResponse,
  StationSettingsUpdate,
  AutomationRuleResponse,
  AutomationRuleCreate,
  AutomationRuleType,
  AutomationAction,
} from '../types';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { Button } from './common/Button';
import { Spinner } from './common/Spinner';

interface StationSettingsModalProps {
  station: Station;
  motors: Motor[];
  sensors?: Sensor[];
  isOpen: boolean;
  onClose: () => void;
}

export const StationSettingsModal: React.FC<StationSettingsModalProps> = ({
  station,
  motors,
  sensors = [],
  isOpen,
  onClose,
}) => {
  const { hasRole, user } = useAuth();
  const canEdit = hasRole(['SUPER_ADMIN', 'ORGANIZATION_ADMIN', 'SITE_MANAGER']);

  const [settings, setSettings] = useState<StationSettingsResponse | null>(null);
  const [rules, setRules] = useState<AutomationRuleResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'settings' | 'rules'>('settings');

  // New Rule Form State
  const [showAddRule, setShowAddRule] = useState<boolean>(false);
  const [ruleName, setRuleName] = useState<string>('');
  const [ruleType, setRuleType] = useState<AutomationRuleType>('TANK_FULL_AUTO_STOP');
  const [ruleMotorId, setRuleMotorId] = useState<string>(motors[0]?.id || '');
  const [ruleSensorId, setRuleSensorId] = useState<string>('');
  const [ruleThreshold, setRuleThreshold] = useState<number>(95);
  const [ruleAction, setRuleAction] = useState<AutomationAction>('STOP');

  // Load Station Settings and Automation Rules
  useEffect(() => {
    if (!isOpen || !station.id) return;

    const loadData = async () => {
      setLoading(true);
      setError(null);
      try {
        const [settingsData, rulesData] = await Promise.all([
          api.getStationSettings(station.id),
          api.getAutomationRules(station.id),
        ]);
        setSettings(settingsData);
        setRules(rulesData);
      } catch (err: any) {
        setError(err.message || 'Failed to load station configuration.');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [isOpen, station.id]);

  if (!isOpen) return null;

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!settings || !canEdit) return;

    setSaving(true);
    setError(null);
    try {
      const updatePayload: StationSettingsUpdate = {
        timezone: settings.timezone,
        auto_stop_on_tank_full: settings.auto_stop_on_tank_full,
        water_level_threshold: settings.water_level_threshold,
        turbidity_threshold: settings.turbidity_threshold,
        default_timer_seconds: settings.default_timer_seconds,
        offline_alert_enabled: settings.offline_alert_enabled,
        offline_timeout_seconds: settings.offline_timeout_seconds,
      };
      const updated = await api.updateStationSettings(station.id, updatePayload);
      setSettings(updated);
      alert('Station settings saved successfully.');
    } catch (err: any) {
      setError(err.message || 'Failed to save station settings.');
    } finally {
      setSaving(false);
    }
  };

  const handleCreateRule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canEdit || !ruleMotorId) return;

    setSaving(true);
    setError(null);
    try {
      const newRulePayload: AutomationRuleCreate = {
        station_id: station.id,
        name: ruleName.trim(),
        rule_type: ruleType,
        motor_id: ruleMotorId,
        sensor_id: ruleSensorId || undefined,
        threshold_value: ruleThreshold,
        action: ruleAction,
        status: 'ACTIVE',
      };
      const created = await api.createAutomationRule(newRulePayload);
      setRules((prev) => [...prev, created]);
      setShowAddRule(false);
      setRuleName('');
    } catch (err: any) {
      setError(err.message || 'Failed to create automation rule.');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteRule = async (ruleId: string) => {
    if (!canEdit) return;
    if (!confirm('Are you sure you want to delete this automation rule?')) return;

    try {
      await api.deleteAutomationRule(ruleId);
      setRules((prev) => prev.filter((r) => r.id !== ruleId));
    } catch (err: any) {
      alert(`Delete failed: ${err.message}`);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="glass-panel w-full max-w-3xl rounded-3xl border border-slate-700 bg-slate-950 p-6 md:p-8 space-y-6 shadow-2xl relative">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-2xl bg-cyan-500/20 text-cyan-400">
              <Sliders className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-xl font-extrabold text-white">
                {station.name} — Configuration & Safety Rules
              </h2>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-xs text-slate-400">Site Station: {station.station_code}</span>
                {canEdit ? (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                    Admin / Manager Edit Access
                  </span>
                ) : (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700 flex items-center gap-1">
                    <Lock className="w-3 h-3 text-amber-400" /> Read-Only ({user?.role})
                  </span>
                )}
              </div>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-2 border-b border-slate-800">
          <button
            onClick={() => setActiveTab('settings')}
            className={`px-4 py-2 text-xs font-bold transition-all border-b-2 ${
              activeTab === 'settings'
                ? 'border-cyan-400 text-cyan-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Station Thresholds & Settings
          </button>
          <button
            onClick={() => setActiveTab('rules')}
            className={`px-4 py-2 text-xs font-bold transition-all border-b-2 ${
              activeTab === 'rules'
                ? 'border-cyan-400 text-cyan-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Automation & Protection Rules ({rules.length})
          </button>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="p-3 rounded-xl bg-rose-950/80 border border-rose-800 text-rose-300 text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {loading ? (
          <div className="py-12 flex justify-center">
            <Spinner size="lg" label="Loading configuration..." />
          </div>
        ) : activeTab === 'settings' && settings ? (
          /* Tab 1: Settings Form */
          <form onSubmit={handleSaveSettings} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Timezone */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300">Station Timezone</label>
                <input
                  type="text"
                  value={settings.timezone}
                  disabled={!canEdit}
                  onChange={(e) => setSettings({ ...settings, timezone: e.target.value })}
                  className="w-full px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-700 text-xs text-white disabled:opacity-60 focus:outline-none focus:border-cyan-400"
                />
              </div>

              {/* Water Level Threshold */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300">Tank Full Threshold (%)</label>
                <input
                  type="number"
                  step="0.5"
                  value={settings.water_level_threshold ?? 95}
                  disabled={!canEdit}
                  onChange={(e) =>
                    setSettings({ ...settings, water_level_threshold: parseFloat(e.target.value) || 0 })
                  }
                  className="w-full px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-700 text-xs text-white disabled:opacity-60 focus:outline-none focus:border-cyan-400"
                />
              </div>

              {/* Turbidity Threshold */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300">Turbidity Cutoff Limit (NTU)</label>
                <input
                  type="number"
                  step="0.1"
                  value={settings.turbidity_threshold ?? 5.0}
                  disabled={!canEdit}
                  onChange={(e) =>
                    setSettings({ ...settings, turbidity_threshold: parseFloat(e.target.value) || 0 })
                  }
                  className="w-full px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-700 text-xs text-white disabled:opacity-60 focus:outline-none focus:border-cyan-400"
                />
              </div>

              {/* Offline Timeout */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300">Heartbeat Timeout (seconds)</label>
                <input
                  type="number"
                  value={settings.offline_timeout_seconds ?? 60}
                  disabled={!canEdit}
                  onChange={(e) =>
                    setSettings({ ...settings, offline_timeout_seconds: parseInt(e.target.value) || 60 })
                  }
                  className="w-full px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-700 text-xs text-white disabled:opacity-60 focus:outline-none focus:border-cyan-400"
                />
              </div>
            </div>

            {/* Toggle Switches */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
              <label className="flex items-center gap-3 p-3.5 rounded-2xl bg-slate-900/60 border border-slate-800 cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.auto_stop_on_tank_full}
                  disabled={!canEdit}
                  onChange={(e) =>
                    setSettings({ ...settings, auto_stop_on_tank_full: e.target.checked })
                  }
                  className="w-4 h-4 rounded text-cyan-500 focus:ring-cyan-400 bg-slate-800 border-slate-700"
                />
                <div>
                  <span className="text-xs font-bold text-white block">Auto-Stop on Tank Full</span>
                  <span className="text-[11px] text-slate-400">Safely stop pump when tank hits high threshold</span>
                </div>
              </label>

              <label className="flex items-center gap-3 p-3.5 rounded-2xl bg-slate-900/60 border border-slate-800 cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.offline_alert_enabled}
                  disabled={!canEdit}
                  onChange={(e) =>
                    setSettings({ ...settings, offline_alert_enabled: e.target.checked })
                  }
                  className="w-4 h-4 rounded text-cyan-500 focus:ring-cyan-400 bg-slate-800 border-slate-700"
                />
                <div>
                  <span className="text-xs font-bold text-white block">Controller Offline Alerts</span>
                  <span className="text-[11px] text-slate-400">Trigger warnings when heartbeat is lost</span>
                </div>
              </label>
            </div>

            {canEdit && (
              <div className="flex justify-end pt-4 border-t border-slate-800">
                <Button type="submit" variant="primary" disabled={saving}>
                  <Save className="w-4 h-4 mr-2" />
                  {saving ? 'Saving...' : 'Save Station Settings'}
                </Button>
              </div>
            )}
          </form>
        ) : (
          /* Tab 2: Automation Rules List */
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">Active Rules Enforced by Backend Engine</span>
              {canEdit && !showAddRule && (
                <Button size="sm" variant="secondary" onClick={() => setShowAddRule(true)}>
                  <Plus className="w-3.5 h-3.5 mr-1" /> Add Rule
                </Button>
              )}
            </div>

            {/* Create Rule Form */}
            {showAddRule && (
              <form onSubmit={handleCreateRule} className="p-4 rounded-2xl bg-slate-900/80 border border-slate-700 space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-cyan-400 uppercase tracking-wider">New Automation Rule</h4>
                  <button type="button" onClick={() => setShowAddRule(false)} className="text-slate-400 hover:text-white">
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="text-[11px] text-slate-300 font-semibold block mb-1">Rule Name</label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Overhead Tank Full Stop"
                      value={ruleName}
                      onChange={(e) => setRuleName(e.target.value)}
                      className="w-full px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-700 text-xs text-white"
                    />
                  </div>

                  <div>
                    <label className="text-[11px] text-slate-300 font-semibold block mb-1">Rule Type</label>
                    <select
                      value={ruleType}
                      onChange={(e) => setRuleType(e.target.value as AutomationRuleType)}
                      className="w-full px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-700 text-xs text-white"
                    >
                      <option value="TANK_FULL_AUTO_STOP">Tank Full Auto Stop</option>
                      <option value="SOURCE_DEPLETION_AUTO_STOP">Source Depletion Trip</option>
                      <option value="TURBIDITY_CUTOFF">Turbidity Cutoff</option>
                      <option value="DRY_RUN_PROTECTION">Dry-Run Protection</option>
                      <option value="ELECTRICAL_OVERLOAD_PROTECTION">Electrical Overload Trip</option>
                    </select>
                  </div>

                  <div>
                    <label className="text-[11px] text-slate-300 font-semibold block mb-1">Target Motor</label>
                    <select
                      value={ruleMotorId}
                      onChange={(e) => setRuleMotorId(e.target.value)}
                      className="w-full px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-700 text-xs text-white"
                    >
                      {motors.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.name} ({m.motor_code})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="text-[11px] text-slate-300 font-semibold block mb-1">Sensor Binding (Optional)</label>
                    <select
                      value={ruleSensorId}
                      onChange={(e) => setRuleSensorId(e.target.value)}
                      className="w-full px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-700 text-xs text-white"
                    >
                      <option value="">None / Edge Sensor</option>
                      {sensors.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name} ({s.sensor_code})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="text-[11px] text-slate-300 font-semibold block mb-1">Threshold Value</label>
                    <input
                      type="number"
                      step="0.1"
                      value={ruleThreshold}
                      onChange={(e) => setRuleThreshold(parseFloat(e.target.value) || 0)}
                      className="w-full px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-700 text-xs text-white"
                    />
                  </div>

                  <div>
                    <label className="text-[11px] text-slate-300 font-semibold block mb-1">Action</label>
                    <select
                      value={ruleAction}
                      onChange={(e) => setRuleAction(e.target.value as AutomationAction)}
                      className="w-full px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-700 text-xs text-white"
                    >
                      <option value="STOP">STOP Motor</option>
                      <option value="START">START Motor</option>
                      <option value="ALERT_ONLY">ALERT ONLY</option>
                      <option value="LOCKOUT">LOCKOUT</option>
                    </select>
                  </div>
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <Button type="button" variant="ghost" size="sm" onClick={() => setShowAddRule(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" variant="primary" size="sm" disabled={saving}>
                    Create Rule
                  </Button>
                </div>
              </form>
            )}

            {/* Rules List */}
            {rules.length === 0 ? (
              <div className="p-6 rounded-2xl bg-slate-900/40 border border-slate-800 text-center text-xs text-slate-400">
                No custom automation rules configured for this station. System uses authoritative edge defaults.
              </div>
            ) : (
              <div className="space-y-2">
                {rules.map((rule) => (
                  <div
                    key={rule.id}
                    className="p-3.5 rounded-2xl bg-slate-900/70 border border-slate-800 flex items-center justify-between gap-4"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-white">{rule.name}</span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-cyan-500/20 text-cyan-300">
                          {rule.rule_type}
                        </span>
                        <span className="text-[10px] text-slate-400">Action: {rule.action}</span>
                      </div>
                      <div className="text-[11px] text-slate-400">
                        Threshold: {rule.threshold_value ?? 'N/A'} {rule.threshold_unit || ''}
                      </div>
                    </div>

                    {canEdit && (
                      <button
                        onClick={() => handleDeleteRule(rule.id)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                        title="Delete Rule"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
