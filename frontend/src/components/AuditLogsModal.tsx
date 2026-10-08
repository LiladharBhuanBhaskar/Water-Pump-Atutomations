import React, { useState, useEffect, useCallback } from 'react';
import {
  X,
  Shield,
  RotateCcw,
  ChevronLeft,
  ChevronRight,
  AlertTriangle,
  Terminal,
  User,
} from 'lucide-react';
import { AuditLogResponse, AuditAction } from '../types';
import { api } from '../services/api';
import { Button } from './common/Button';
import { Badge } from './common/Badge';

interface AuditLogsModalProps {
  isOpen: boolean;
  onClose: () => void;
  organizationId?: string | null;
}

const AUDIT_ACTIONS: { key: string; label: string }[] = [
  { key: 'ALL', label: 'All Actions' },
  { key: 'START', label: 'Motor Start' },
  { key: 'STOP', label: 'Motor Stop' },
  { key: 'EMERGENCY_STOP', label: 'Emergency Stop' },
  { key: 'RESET', label: 'Trip Reset' },
  { key: 'CREATE', label: 'Resource Created' },
  { key: 'UPDATE', label: 'Resource Updated' },
  { key: 'DELETE', label: 'Resource Deleted' },
  { key: 'LOGIN', label: 'User Login' },
  { key: 'CONFIGURE', label: 'Threshold Changed' },
];

export const AuditLogsModal: React.FC<AuditLogsModalProps> = ({
  isOpen,
  onClose,
  organizationId,
}) => {
  const [logs, setLogs] = useState<AuditLogResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters & Pagination
  const [actionFilter, setActionFilter] = useState<string>('ALL');
  const [resourceFilter, setResourceFilter] = useState<string>('');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [page, setPage] = useState<number>(0);
  const [selectedLog, setSelectedLog] = useState<AuditLogResponse | null>(null);
  const pageSize = 20;

  const loadAuditLogs = useCallback(async () => {
    if (!isOpen) return;
    try {
      setLoading(true);
      setError(null);

      const params: any = {
        limit: pageSize,
        offset: page * pageSize,
      };

      if (organizationId) params.organization_id = organizationId;
      if (actionFilter !== 'ALL') params.action = actionFilter;
      if (resourceFilter.trim()) params.resource_type = resourceFilter.trim();
      if (startDate) params.start_time = new Date(startDate).toISOString();
      if (endDate) params.end_time = new Date(endDate).toISOString();

      const data = await api.getAuditLogs(params);
      setLogs(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load audit trail.');
    } finally {
      setLoading(false);
    }
  }, [isOpen, organizationId, actionFilter, resourceFilter, startDate, endDate, page]);

  useEffect(() => {
    if (isOpen) {
      loadAuditLogs();
    }
  }, [isOpen, loadAuditLogs]);

  const getActionBadgeVariant = (action: AuditAction) => {
    switch (action) {
      case 'START':
        return 'success';
      case 'STOP':
      case 'RESET':
        return 'neutral';
      case 'EMERGENCY_STOP':
      case 'DELETE':
        return 'danger';
      case 'CREATE':
      case 'UPDATE':
      case 'CONFIGURE':
        return 'info';
      default:
        return 'neutral';
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-[#0f172a] border border-[#1e293b] rounded-2xl w-full max-w-5xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#1e293b] bg-[#131f37]">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-teal-500/10 text-teal-400 border border-teal-500/20">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
                System Audit Trail & Compliance Log
              </h2>
              <p className="text-xs text-slate-400">
                Immutable record of user actions, pump commands, and configuration changes
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={loadAuditLogs}
              disabled={loading}
              className="border-[#334155] text-slate-300 hover:text-white"
            >
              <RotateCcw className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin text-teal-400' : ''}`} />
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

        {/* Filter Bar */}
        <div className="p-4 border-b border-[#1e293b] bg-[#0b1329] grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
          <div>
            <label className="block text-[11px] font-medium text-slate-400 mb-1">Action Filter</label>
            <select
              value={actionFilter}
              onChange={(e) => {
                setActionFilter(e.target.value);
                setPage(0);
              }}
              className="w-full px-2.5 py-1.5 rounded-lg bg-[#1e293b] border border-[#334155] text-white text-xs focus:outline-none focus:border-teal-500"
            >
              {AUDIT_ACTIONS.map((a) => (
                <option key={a.key} value={a.key}>
                  {a.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-medium text-slate-400 mb-1">Resource Type</label>
            <input
              type="text"
              placeholder="e.g. MOTOR, STATION"
              value={resourceFilter}
              onChange={(e) => {
                setResourceFilter(e.target.value);
                setPage(0);
              }}
              className="w-full px-2.5 py-1.5 rounded-lg bg-[#1e293b] border border-[#334155] text-white text-xs focus:outline-none focus:border-teal-500"
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium text-slate-400 mb-1">From Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => {
                setStartDate(e.target.value);
                setPage(0);
              }}
              className="w-full px-2.5 py-1.5 rounded-lg bg-[#1e293b] border border-[#334155] text-white text-xs focus:outline-none focus:border-teal-500"
            />
          </div>

          <div>
            <label className="block text-[11px] font-medium text-slate-400 mb-1">To Date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => {
                setEndDate(e.target.value);
                setPage(0);
              }}
              className="w-full px-2.5 py-1.5 rounded-lg bg-[#1e293b] border border-[#334155] text-white text-xs focus:outline-none focus:border-teal-500"
            />
          </div>
        </div>

        {/* Audit Table Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {error && (
            <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2.5">
              <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          {loading && logs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 space-y-3">
              <RotateCcw className="w-7 h-7 text-teal-400 animate-spin" />
              <p className="text-xs text-slate-400">Loading audit compliance logs...</p>
            </div>
          ) : logs.length === 0 ? (
            <div className="text-center py-16 text-slate-500 text-sm">
              No audit logs matched the selected filter criteria.
            </div>
          ) : (
            <div className="border border-[#1e293b] rounded-xl overflow-hidden bg-[#0b1329]">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-[#131f37] font-semibold text-slate-400 uppercase tracking-wider border-b border-[#1e293b]">
                    <tr>
                      <th className="px-4 py-3">Timestamp</th>
                      <th className="px-4 py-3">Actor</th>
                      <th className="px-4 py-3">Action</th>
                      <th className="px-4 py-3">Resource</th>
                      <th className="px-4 py-3">Description</th>
                      <th className="px-4 py-3">IP / Client</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#1e293b]/60">
                    {logs.map((log) => (
                      <tr
                        key={log.id}
                        onClick={() => setSelectedLog(selectedLog?.id === log.id ? null : log)}
                        className="hover:bg-[#1e293b]/50 cursor-pointer transition-colors"
                      >
                        <td className="px-4 py-3 whitespace-nowrap text-slate-400">
                          {new Date(log.occurred_at).toLocaleString()}
                        </td>
                        <td className="px-4 py-3">
                          <span className="font-medium text-white flex items-center gap-1.5">
                            <User className="w-3.5 h-3.5 text-teal-400" />
                            {log.actor_type}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={getActionBadgeVariant(log.action)} size="sm">
                            {log.action}
                          </Badge>
                        </td>
                        <td className="px-4 py-3">
                          <span className="font-mono text-slate-300">{log.resource_type}</span>
                        </td>
                        <td className="px-4 py-3 text-slate-300 max-w-xs truncate">
                          {log.action_description}
                        </td>
                        <td className="px-4 py-3 text-slate-500 font-mono text-[11px]">
                          {log.ip_address || 'Internal Service'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Selected Audit Log Metadata Drawer */}
          {selectedLog && (
            <div className="p-4 rounded-xl bg-[#131f37] border border-teal-500/30 space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-teal-300 flex items-center gap-1.5">
                  <Terminal className="w-4 h-4" /> Audit Entry Inspector: {selectedLog.id}
                </span>
                <button
                  onClick={() => setSelectedLog(null)}
                  className="text-slate-400 hover:text-white text-xs"
                >
                  Close Detail
                </button>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-slate-400 pt-1">
                <div>
                  <span className="block text-slate-500">Resource ID:</span>
                  <span className="font-mono text-white text-[11px]">{selectedLog.resource_id || 'N/A'}</span>
                </div>
                <div>
                  <span className="block text-slate-500">Actor User ID:</span>
                  <span className="font-mono text-white text-[11px]">{selectedLog.actor_user_id || 'System'}</span>
                </div>
                <div>
                  <span className="block text-slate-500">User Agent:</span>
                  <span className="truncate block text-white text-[11px]">{selectedLog.user_agent || 'Standard REST Client'}</span>
                </div>
                <div>
                  <span className="block text-slate-500">Occurred:</span>
                  <span className="text-white text-[11px]">{new Date(selectedLog.occurred_at).toUTCString()}</span>
                </div>
              </div>
              {selectedLog.audit_metadata && (
                <div className="mt-2 bg-[#0b1329] p-2.5 rounded-lg border border-[#1e293b] font-mono text-[11px] text-teal-300 overflow-x-auto">
                  {JSON.stringify(selectedLog.audit_metadata, null, 2)}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Modal Footer & Pagination */}
        <div className="px-6 py-3 border-t border-[#1e293b] bg-[#131f37] flex items-center justify-between text-xs">
          <span className="text-slate-400">
            Page {page + 1} ({logs.length} entries shown)
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0 || loading}
            >
              <ChevronLeft className="w-4 h-4 mr-1" /> Prev
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => p + 1)}
              disabled={logs.length < pageSize || loading}
            >
              Next <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};
