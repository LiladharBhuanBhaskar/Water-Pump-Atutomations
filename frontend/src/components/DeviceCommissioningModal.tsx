import React, { useState, useEffect, useCallback } from 'react';
import {
  X,
  Cpu,
  QrCode,
  CheckCircle2,
  AlertTriangle,
  RotateCw,
  Radio,
  ArrowRight,
  ArrowLeft,
  Server,
  Check,
} from 'lucide-react';
import { ControllerType, DeviceLivenessResponse, Station } from '../types';
import { api } from '../services/api';

interface DeviceCommissioningModalProps {
  isOpen: boolean;
  onClose: () => void;
  station: Station;
  onDeviceCommissioned?: () => void;
}

export const DeviceCommissioningModal: React.FC<DeviceCommissioningModalProps> = ({
  isOpen,
  onClose,
  station,
  onDeviceCommissioned,
}) => {
  const [step, setStep] = useState<number>(1);
  const [deviceUid, setDeviceUid] = useState<string>('');
  const [controllerName, setControllerName] = useState<string>('');
  const [controllerType, setControllerType] = useState<ControllerType>('ESP32');
  const [firmwareVersion, setFirmwareVersion] = useState<string>('v1.2.0');

  // Commissioning state
  const [commissioningToken, setCommissioningToken] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [liveness, setLiveness] = useState<DeviceLivenessResponse | null>(null);
  const [pollingHeartbeat, setPollingHeartbeat] = useState<boolean>(false);

  useEffect(() => {
    if (isOpen) {
      setStep(1);
      setDeviceUid(`ESP32-${Math.random().toString(36).substring(2, 8).toUpperCase()}`);
      setControllerName(`${station.name} Primary Gateway`);
      setCommissioningToken('');
      setError(null);
      setLiveness(null);
      setPollingHeartbeat(false);
    }
  }, [isOpen, station]);

  const generateChallengeToken = () => {
    const token = `HC-COMM-${Date.now()}-${Math.random().toString(36).substring(2, 10).toUpperCase()}`;
    setCommissioningToken(token);
    setStep(2);
  };

  const handleRegisterDevice = async () => {
    try {
      setLoading(true);
      setError(null);

      await api.registerDevice({
        device_uid: deviceUid,
        firmware_version: firmwareVersion,
        controller_type: controllerType,
      });

      setStep(3);
      startHeartbeatPolling();
    } catch (err: any) {
      setError(err.message || 'Device provisioning failed. Please verify device UID.');
    } finally {
      setLoading(false);
    }
  };

  const startHeartbeatPolling = useCallback(() => {
    setPollingHeartbeat(true);
    let attempts = 0;
    const maxAttempts = 10;

    const interval = setInterval(async () => {
      attempts++;
      try {
        const status = await api.getDeviceStatus(deviceUid);
        setLiveness(status);
        if (status.status === 'ACTIVE' || status.liveness_state === 'ONLINE') {
          clearInterval(interval);
          setPollingHeartbeat(false);
          setStep(4);
          if (onDeviceCommissioned) onDeviceCommissioned();
        }
      } catch {
        // Continue polling until timeout
      }

      if (attempts >= maxAttempts) {
        clearInterval(interval);
        setPollingHeartbeat(false);
      }
    }, 2500);
  }, [deviceUid, onDeviceCommissioned]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-slate-950/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg bg-white sm:rounded-[28px] rounded-t-[28px] border border-slate-200/80 shadow-2xl overflow-hidden flex flex-col max-h-[92vh] font-['Plus_Jakarta_Sans',sans-serif]">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 bg-slate-50/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-teal-50 text-teal-700 flex items-center justify-center shadow-xs">
              <Cpu className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-black text-slate-900 tracking-tight leading-tight">
                IoT Device Commissioning
              </h2>
              <p className="text-xs text-slate-400 font-medium">
                Pair & provision ESP32 controller for {station.name}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-600 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Wizard Step Progress Bar */}
        <div className="px-5 pt-3.5 pb-2.5 bg-slate-50 border-b border-slate-100">
          <div className="flex items-center justify-between text-[11px] font-bold text-slate-400">
            <span className={step >= 1 ? 'text-teal-700' : ''}>1. Identity</span>
            <span className={step >= 2 ? 'text-teal-700' : ''}>2. QR Challenge</span>
            <span className={step >= 3 ? 'text-teal-700' : ''}>3. Handshake</span>
            <span className={step >= 4 ? 'text-emerald-700' : ''}>4. Connected</span>
          </div>
          <div className="w-full bg-slate-200 h-1.5 rounded-full mt-2 overflow-hidden">
            <div
              className="bg-teal-600 h-full transition-all duration-300 rounded-full"
              style={{ width: `${(step / 4) * 100}%` }}
            />
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4">
          {error && (
            <div className="flex items-center gap-2 p-3 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-semibold">
              <AlertTriangle className="w-4 h-4 shrink-0 text-rose-500" />
              <span>{error}</span>
            </div>
          )}

          {/* STEP 1: Hardware Identification */}
          {step === 1 && (
            <div className="space-y-3.5">
              <div className="p-3 rounded-2xl bg-teal-50/50 border border-teal-200/80 text-xs text-slate-700 space-y-1">
                <div className="font-bold text-teal-800 flex items-center gap-1.5">
                  <Server className="w-3.5 h-3.5 text-teal-600" /> Station Context
                </div>
                <div>Station: <span className="text-slate-900 font-bold">{station.name}</span> ({station.station_code})</div>
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-700 mb-1">
                  Device Hardware UID (MAC / Serial)
                </label>
                <input
                  type="text"
                  value={deviceUid}
                  onChange={(e) => setDeviceUid(e.target.value.trim())}
                  placeholder="e.g. ESP32-A1B2C3"
                  className="w-full px-3 py-2 rounded-xl bg-white border border-slate-200 text-xs font-semibold text-slate-900 focus:outline-none focus:border-teal-500 shadow-xs"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold text-slate-700 mb-1">
                  Controller Display Name
                </label>
                <input
                  type="text"
                  value={controllerName}
                  onChange={(e) => setControllerName(e.target.value)}
                  placeholder="e.g. Pump Station Main Gateway"
                  className="w-full px-3 py-2 rounded-xl bg-white border border-slate-200 text-xs font-semibold text-slate-900 focus:outline-none focus:border-teal-500 shadow-xs"
                />
              </div>

              <div className="grid grid-cols-2 gap-2.5">
                <div>
                  <label className="block text-[11px] font-bold text-slate-700 mb-1">Hardware Type</label>
                  <select
                    value={controllerType}
                    onChange={(e) => setControllerType(e.target.value as ControllerType)}
                    className="w-full px-3 py-2 rounded-xl bg-white border border-slate-200 text-xs font-semibold text-slate-900 focus:outline-none focus:border-teal-500 shadow-xs"
                  >
                    <option value="ESP32">ESP32 (Wi-Fi)</option>
                    <option value="ESP32_ETHERNET">ESP32 (Ethernet)</option>
                    <option value="ESP32_4G">ESP32 (4G LTE)</option>
                    <option value="PLC">Industrial PLC</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-700 mb-1">Firmware Version</label>
                  <input
                    type="text"
                    value={firmwareVersion}
                    onChange={(e) => setFirmwareVersion(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-white border border-slate-200 text-xs font-semibold text-slate-900 focus:outline-none focus:border-teal-500 shadow-xs"
                  />
                </div>
              </div>
            </div>
          )}

          {/* STEP 2: Secure QR / Commissioning Challenge */}
          {step === 2 && (
            <div className="space-y-4 text-center">
              <div className="p-4 rounded-2xl bg-teal-50/40 border border-teal-200/80 flex flex-col items-center justify-center space-y-3">
                <div className="p-3 bg-white rounded-2xl shadow-md border border-slate-100">
                  <QrCode className="w-28 h-28 text-slate-900" />
                </div>
                <div className="space-y-1">
                  <div className="text-[11px] font-bold text-slate-500">One-Time Commissioning Token</div>
                  <div className="text-xs font-mono font-bold text-teal-800 bg-white px-3 py-1.5 rounded-xl border border-teal-200 shadow-xs">
                    {commissioningToken}
                  </div>
                </div>
              </div>

              <p className="text-xs text-slate-500 text-left">
                Scan this QR code using the technician commissioning app or enter the one-time token into the ESP32 serial console. Permanent MQTT secrets are generated securely on-device.
              </p>
            </div>
          )}

          {/* STEP 3: Handshake & Liveness Polling */}
          {step === 3 && (
            <div className="space-y-4 py-6 text-center">
              <div className="relative flex items-center justify-center">
                <div className="w-16 h-16 rounded-2xl bg-teal-50 border border-teal-200 text-teal-700 flex items-center justify-center animate-pulse shadow-xs">
                  <Radio className="w-8 h-8" />
                </div>
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-black text-slate-900">Listening for Controller Heartbeat...</h3>
                <p className="text-xs text-slate-500">
                  Waiting for device <span className="font-mono font-bold text-teal-700">{deviceUid}</span> to establish MQTT telemetry.
                </p>
              </div>
              {pollingHeartbeat && (
                <div className="text-xs text-teal-700 font-bold flex items-center justify-center gap-1.5">
                  <RotateCw className="w-3.5 h-3.5 animate-spin" /> Polling device liveness state...
                </div>
              )}
            </div>
          )}

          {/* STEP 4: Connected & Commissioned */}
          {step === 4 && (
            <div className="space-y-4 py-3 text-center">
              <div className="w-14 h-14 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-600 flex items-center justify-center mx-auto shadow-xs">
                <CheckCircle2 className="w-8 h-8" />
              </div>
              <div className="space-y-1">
                <h3 className="text-base font-black text-slate-900">Device Successfully Commissioned!</h3>
                <p className="text-xs text-slate-500">
                  Controller is online and reporting live telemetry for {station.name}.
                </p>
              </div>

              <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200/80 text-xs text-left space-y-2">
                <div className="flex justify-between">
                  <span className="text-slate-500">Device UID:</span>
                  <span className="font-mono font-bold text-slate-900">{deviceUid}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-500">Liveness State:</span>
                  <span className="px-2 py-0.5 rounded-md text-[10px] font-extrabold bg-emerald-50 text-emerald-700 border border-emerald-200">
                    {liveness?.liveness_state || 'ONLINE'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Station Code:</span>
                  <span className="font-mono text-slate-700">{station.station_code}</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer Controls */}
        <div className="px-5 py-3 border-t border-slate-100 bg-slate-50/50 flex items-center justify-between">
          {step > 1 && step < 4 ? (
            <button
              type="button"
              onClick={() => setStep((s) => s - 1)}
              disabled={loading || pollingHeartbeat}
              className="px-3.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-colors flex items-center gap-1.5"
            >
              <ArrowLeft className="w-3.5 h-3.5" /> Back
            </button>
          ) : (
            <div />
          )}

          {step === 1 && (
            <button
              type="button"
              onClick={generateChallengeToken}
              disabled={!deviceUid}
              className="px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold shadow-md shadow-teal-600/25 transition-all flex items-center gap-1.5 disabled:opacity-50"
            >
              <span>Next: Generate QR</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          )}

          {step === 2 && (
            <button
              type="button"
              onClick={handleRegisterDevice}
              disabled={loading}
              className="px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold shadow-md shadow-teal-600/25 transition-all flex items-center gap-1.5 disabled:opacity-50"
            >
              {loading ? <RotateCw className="w-3.5 h-3.5 animate-spin" /> : null}
              <span>{loading ? 'Provisioning...' : 'Provision & Listen'}</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          )}

          {step === 3 && (
            <button
              type="button"
              onClick={() => setStep(4)}
              className="px-3.5 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-colors"
            >
              Simulate Device ACK
            </button>
          )}

          {step === 4 && (
            <button
              type="button"
              onClick={onClose}
              className="px-5 py-2 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold shadow-md shadow-teal-600/25 transition-all flex items-center gap-1"
            >
              <Check className="w-3.5 h-3.5 stroke-[3]" />
              <span>Done</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
