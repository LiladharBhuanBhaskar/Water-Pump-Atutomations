import React, { useState, useEffect, useCallback } from 'react';
import {
  X,
  Layers,
  Building2,
  Server,
  Activity,
  Zap,
  ShieldAlert,
  RotateCw,
  CheckCircle2,
  AlertOctagon,
  Power,
  Radio,
} from 'lucide-react';
import { OrganizationFleetSummary } from '../types';
import { api } from '../services/api';
import { Button } from './common/Button';
import { Badge } from './common/Badge';

interface FleetSummaryModalProps {
  isOpen: boolean;
  onClose: () => void;
  organizationId: string;
  organizationName?: string;
}

export const FleetSummaryModal: React.FC<FleetSummaryModalProps> = ({
  isOpen,
  onClose,
  organizationId,
  organizationName = 'Enterprise Fleet',
}) => {
  const [summary, setSummary] = useState<OrganizationFleetSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadFleetSummary = useCallback(async () => {
    if (!isOpen || !organizationId) return;
    try {
      setLoading(true);
      setError(null);
      const data = await api.getFleetSummary(organizationId);
      setSummary(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load fleet operational summary.');
    } finally {
      setLoading(false);
    }
  }, [isOpen, organizationId]);

  useEffect(() => {
    if (isOpen) {
      loadFleetSummary();
    }
  }, [isOpen, loadFleetSummary]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-[#0f172a] border border-[#1e293b] rounded-2xl w-full max-w-5xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#1e293b] bg-[#131f37]">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-teal-500/10 text-teal-400 border border-teal-500/20">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                Enterprise Fleet Overview
                <Badge variant="info" size="sm">
                  {summary?.organization_code || 'ORG'}
                </Badge>
              </h2>
              <p className="text-xs text-slate-400">
                {summary?.organization_name || organizationName} • Multi-Site Operational Rollup
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={loadFleetSummary}
              disabled={loading}
              className="border-[#334155] text-slate-300 hover:text-white"
            >
              <RotateCw className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin text-teal-400' : ''}`} />
              Refresh
            </Button>
            <button
              onClick={onClose}
              className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading && !summary && (
            <div className="flex flex-col items-center justify-center py-20 space-y-3">
              <RotateCw className="w-8 h-8 text-teal-400 animate-spin" />
              <p className="text-sm text-slate-400">Aggregating telemetry across all enterprise sites...</p>
            </div>
          )}

          {error && (
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-sm flex items-center gap-3">
              <AlertOctagon className="w-5 h-5 shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          {summary && (
            <>
              {/* Primary KPI Metrics Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                <div className="bg-[#1e293b]/70 border border-[#334155]/60 rounded-xl p-3.5 flex flex-col">
                  <span className="text-xs text-slate-400 font-medium flex items-center gap-1.5 mb-1">
                    <Building2 className="w-3.5 h-3.5 text-teal-400" /> Sites
                  </span>
                  <span className="text-2xl font-bold text-white tracking-tight">{summary.site_count}</span>
                  <span className="text-[11px] text-slate-500 mt-0.5">{summary.station_count} Stations Total</span>
                </div>

                <div className="bg-[#1e293b]/70 border border-[#334155]/60 rounded-xl p-3.5 flex flex-col">
                  <span className="text-xs text-slate-400 font-medium flex items-center gap-1.5 mb-1">
                    <Server className="w-3.5 h-3.5 text-cyan-400" /> Controllers
                  </span>
                  <span className="text-2xl font-bold text-white tracking-tight">{summary.controller_count}</span>
                  <div className="flex items-center gap-2 mt-0.5 text-[11px]">
                    <span className="text-emerald-400">{summary.online_controllers} on</span>
                    <span className="text-slate-500">•</span>
                    <span className="text-rose-400">{summary.offline_controllers} off</span>
                  </div>
                </div>

                <div className="bg-[#1e293b]/70 border border-[#334155]/60 rounded-xl p-3.5 flex flex-col">
                  <span className="text-xs text-slate-400 font-medium flex items-center gap-1.5 mb-1">
                    <Power className="w-3.5 h-3.5 text-emerald-400" /> Running Pumps
                  </span>
                  <span className="text-2xl font-bold text-emerald-400 tracking-tight">{summary.motors.running}</span>
                  <span className="text-[11px] text-slate-500 mt-0.5">of {summary.motors.total} Total Motors</span>
                </div>

                <div className="bg-[#1e293b]/70 border border-[#334155]/60 rounded-xl p-3.5 flex flex-col">
                  <span className="text-xs text-slate-400 font-medium flex items-center gap-1.5 mb-1">
                    <AlertOctagon className="w-3.5 h-3.5 text-rose-400" /> Active Faults
                  </span>
                  <span className={`text-2xl font-bold tracking-tight ${summary.motors.fault > 0 ? 'text-rose-400' : 'text-slate-300'}`}>
                    {summary.motors.fault}
                  </span>
                  <span className="text-[11px] text-slate-500 mt-0.5">{summary.active_safety_alerts.length} Safety Trips</span>
                </div>

                <div className="bg-[#1e293b]/70 border border-[#334155]/60 rounded-xl p-3.5 flex flex-col">
                  <span className="text-xs text-slate-400 font-medium flex items-center gap-1.5 mb-1">
                    <Zap className="w-3.5 h-3.5 text-amber-400" /> Total Power
                  </span>
                  <span className="text-2xl font-bold text-amber-400 tracking-tight">
                    {summary.total_power_kw.toFixed(1)} <span className="text-xs text-slate-400 font-normal">kW</span>
                  </span>
                  <span className="text-[11px] text-slate-500 mt-0.5">Connected Load</span>
                </div>

                <div className="bg-[#1e293b]/70 border border-[#334155]/60 rounded-xl p-3.5 flex flex-col">
                  <span className="text-xs text-slate-400 font-medium flex items-center gap-1.5 mb-1">
                    <Radio className="w-3.5 h-3.5 text-indigo-400" /> Active Sensors
                  </span>
                  <span className="text-2xl font-bold text-white tracking-tight">{summary.total_sensor_count}</span>
                  <span className="text-[11px] text-slate-500 mt-0.5">Live Telemetry</span>
                </div>
              </div>

              {/* Active Safety Alerts Section */}
              {summary.active_safety_alerts.length > 0 && (
                <div className="rounded-xl border border-rose-500/30 bg-rose-950/20 p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-rose-300 flex items-center gap-2">
                      <ShieldAlert className="w-4 h-4 text-rose-400" />
                      Active Safety Alerts ({summary.active_safety_alerts.length})
                    </h3>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                    {summary.active_safety_alerts.map((alert, idx) => (
                      <div
                        key={idx}
                        className="bg-[#0f172a]/80 border border-rose-500/20 rounded-lg p-3 flex items-center justify-between"
                      >
                        <div>
                          <div className="text-sm font-medium text-white flex items-center gap-2">
                            <span>{alert.motor_code}</span>
                            <Badge variant="danger" size="sm">
                              {alert.status}
                            </Badge>
                          </div>
                          <p className="text-xs text-slate-400 mt-0.5">
                            {alert.site_name} • {alert.station_name}
                          </p>
                        </div>
                        <span className="text-[11px] text-slate-500">
                          {new Date(alert.occurred_at).toLocaleTimeString()}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Sites Operational Summary Table */}
              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                  <Activity className="w-4 h-4 text-teal-400" />
                  Site Breakdown & Operational Health
                </h3>
                <div className="border border-[#1e293b] rounded-xl overflow-hidden bg-[#0b1329]">
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm text-slate-300">
                      <thead className="bg-[#131f37] text-xs font-semibold text-slate-400 uppercase tracking-wider border-b border-[#1e293b]">
                        <tr>
                          <th className="px-4 py-3">Site</th>
                          <th className="px-4 py-3">Status</th>
                          <th className="px-4 py-3 text-center">Stations</th>
                          <th className="px-4 py-3 text-center">Controllers</th>
                          <th className="px-4 py-3 text-center">Motors (Run / Total)</th>
                          <th className="px-4 py-3 text-center">Faults</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#1e293b]/60">
                        {summary.sites.length === 0 ? (
                          <tr>
                            <td colSpan={6} className="text-center py-8 text-slate-500">
                              No active sites provisioned in this organization.
                            </td>
                          </tr>
                        ) : (
                          summary.sites.map((site) => (
                            <tr key={site.site_id} className="hover:bg-[#1e293b]/40 transition-colors">
                              <td className="px-4 py-3">
                                <div className="font-medium text-white">{site.site_name}</div>
                                <div className="text-xs text-slate-500">{site.site_code}</div>
                              </td>
                              <td className="px-4 py-3">
                                <Badge
                                  variant={
                                    site.status === 'ACTIVE'
                                      ? 'success'
                                      : site.status === 'MAINTENANCE'
                                      ? 'warning'
                                      : 'neutral'
                                  }
                                  size="sm"
                                >
                                  {site.status}
                                </Badge>
                              </td>
                              <td className="px-4 py-3 text-center font-medium">{site.station_count}</td>
                              <td className="px-4 py-3 text-center font-medium">{site.controller_count}</td>
                              <td className="px-4 py-3 text-center">
                                <span className="text-emerald-400 font-semibold">{site.running_motors}</span>
                                <span className="text-slate-500"> / {site.motor_count}</span>
                              </td>
                              <td className="px-4 py-3 text-center">
                                {site.faulted_motors > 0 ? (
                                  <Badge variant="danger" size="sm">
                                    {site.faulted_motors} Fault
                                  </Badge>
                                ) : (
                                  <span className="text-xs text-emerald-400 flex items-center justify-center gap-1">
                                    <CheckCircle2 className="w-3.5 h-3.5" /> Normal
                                  </span>
                                )}
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-[#1e293b] bg-[#131f37] flex items-center justify-between text-xs text-slate-400">
          <span>
            Telemetry generated:{' '}
            {summary?.generated_at ? new Date(summary.generated_at).toLocaleString() : 'Live'}
          </span>
          <Button variant="outline" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
};
