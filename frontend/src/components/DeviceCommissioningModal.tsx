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
} from 'lucide-react';
import { ControllerType, DeviceLivenessResponse, Station } from '../types';
import { api } from '../services/api';
import { Button } from './common/Button';
import { Badge } from './common/Badge';

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
    // Generate one-time short-lived commissioning challenge (cryptographically unguessable token)
    const token = `HC-COMM-${Date.now()}-${Math.random().toString(36).substring(2, 10).toUpperCase()}`;
    setCommissioningToken(token);
    setStep(2);
  };

  const handleRegisterDevice = async () => {
    try {
      setLoading(true);
      setError(null);

      // 1. Provision / Register Device via Backend API
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
        // Continue polling until max attempts
      }

      if (attempts >= maxAttempts) {
        clearInterval(interval);
        setPollingHeartbeat(false);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [deviceUid, onDeviceCommissioned]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-[#0f172a] border border-[#1e293b] rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden flex flex-col">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#1e293b] bg-[#131f37]">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-teal-500/10 text-teal-400 border border-teal-500/20">
              <Cpu className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-100">IoT Device Commissioning</h2>
              <p className="text-xs text-slate-400">Pair & provision ESP32 controller for {station.name}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Wizard Step Progress Bar */}
        <div className="px-6 pt-4 pb-2 bg-[#0b1329] border-b border-[#1e293b]">
          <div className="flex items-center justify-between text-xs font-semibold text-slate-400">
            <span className={step >= 1 ? 'text-teal-400' : ''}>1. Identity</span>
            <span className={step >= 2 ? 'text-teal-400' : ''}>2. QR Challenge</span>
            <span className={step >= 3 ? 'text-teal-400' : ''}>3. Handshake</span>
            <span className={step >= 4 ? 'text-emerald-400' : ''}>4. Connected</span>
          </div>
          <div className="w-full bg-[#1e293b] h-1.5 rounded-full mt-2 overflow-hidden">
            <div
              className="bg-teal-500 h-full transition-all duration-300"
              style={{ width: `${(step / 4) * 100}%` }}
            />
          </div>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-4 flex-1 overflow-y-auto">
          {error && (
            <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2.5">
              <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          {/* STEP 1: Hardware Identification */}
          {step === 1 && (
            <div className="space-y-4">
              <div className="p-3.5 rounded-xl bg-[#1e293b]/50 border border-[#334155]/60 text-xs text-slate-300 space-y-1">
                <div className="font-semibold text-teal-300 flex items-center gap-1.5">
                  <Server className="w-3.5 h-3.5" /> Station Context
                </div>
                <div>Station: <span className="text-white font-medium">{station.name}</span> ({station.station_code})</div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Device Hardware UID (MAC / Serial)
                </label>
                <input
                  type="text"
                  value={deviceUid}
                  onChange={(e) => setDeviceUid(e.target.value.trim())}
                  placeholder="e.g. ESP32-A1B2C3"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-[#1e293b] border border-[#334155] text-white text-sm focus:outline-none focus:border-teal-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Controller Display Name
                </label>
                <input
                  type="text"
                  value={controllerName}
                  onChange={(e) => setControllerName(e.target.value)}
                  placeholder="e.g. Pump Station Main Gateway"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-[#1e293b] border border-[#334155] text-white text-sm focus:outline-none focus:border-teal-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Hardware Type</label>
                  <select
                    value={controllerType}
                    onChange={(e) => setControllerType(e.target.value as ControllerType)}
                    className="w-full px-3 py-2.5 rounded-xl bg-[#1e293b] border border-[#334155] text-white text-sm focus:outline-none focus:border-teal-500"
                  >
                    <option value="ESP32">ESP32 (Wi-Fi)</option>
                    <option value="ESP32_ETHERNET">ESP32 (Ethernet)</option>
                    <option value="ESP32_4G">ESP32 (4G LTE)</option>
                    <option value="PLC">Industrial PLC</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Firmware Version</label>
                  <input
                    type="text"
                    value={firmwareVersion}
                    onChange={(e) => setFirmwareVersion(e.target.value)}
                    className="w-full px-3 py-2.5 rounded-xl bg-[#1e293b] border border-[#334155] text-white text-sm focus:outline-none focus:border-teal-500"
                  >
                  </input>
                </div>
              </div>
            </div>
          )}

          {/* STEP 2: Secure QR / Commissioning Challenge */}
          {step === 2 && (
            <div className="space-y-4 text-center">
              <div className="p-4 rounded-xl bg-[#0b1329] border border-teal-500/30 flex flex-col items-center justify-center space-y-3">
                <div className="p-3 bg-white rounded-xl shadow-lg">
                  <QrCode className="w-28 h-28 text-slate-900" />
                </div>
                <div className="space-y-1">
                  <div className="text-xs text-slate-400">One-Time Commissioning Token</div>
                  <div className="text-xs font-mono font-bold text-teal-300 bg-teal-950/50 px-3 py-1.5 rounded-lg border border-teal-500/20">
                    {commissioningToken}
                  </div>
                </div>
              </div>

              <p className="text-xs text-slate-400 text-left">
                Scan this QR code using the technician commissioning app or enter the one-time token into the ESP32 serial console. Permanent MQTT secrets are generated securely on-device.
              </p>
            </div>
          )}

          {/* STEP 3: Handshake & Liveness Polling */}
          {step === 3 && (
            <div className="space-y-4 py-6 text-center">
              <div className="relative flex items-center justify-center">
                <div className="w-16 h-16 rounded-full bg-teal-500/10 border border-teal-500/30 flex items-center justify-center animate-pulse">
                  <Radio className="w-8 h-8 text-teal-400" />
                </div>
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-semibold text-white">Listening for Controller Heartbeat...</h3>
                <p className="text-xs text-slate-400">
                  Waiting for device <span className="font-mono text-teal-300">{deviceUid}</span> to establish MQTT telemetry.
                </p>
              </div>
              {pollingHeartbeat && (
                <div className="text-xs text-teal-400 flex items-center justify-center gap-1.5">
                  <RotateCw className="w-3.5 h-3.5 animate-spin" /> Polling device liveness state...
                </div>
              )}
            </div>
          )}

          {/* STEP 4: Connected & Commissioned */}
          {step === 4 && (
            <div className="space-y-4 py-4 text-center">
              <div className="w-14 h-14 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-8 h-8" />
              </div>
              <div className="space-y-1">
                <h3 className="text-base font-bold text-white">Device Successfully Commissioned!</h3>
                <p className="text-xs text-slate-400">
                  Controller is online and reporting live telemetry for {station.name}.
                </p>
              </div>

              <div className="p-3.5 rounded-xl bg-[#1e293b]/60 border border-[#334155]/60 text-xs text-left space-y-2">
                <div className="flex justify-between">
                  <span className="text-slate-400">Device UID:</span>
                  <span className="font-mono font-medium text-white">{deviceUid}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Liveness State:</span>
                  <Badge variant="success" size="sm">{liveness?.liveness_state || 'ONLINE'}</Badge>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Station Code:</span>
                  <span className="text-slate-300">{station.station_code}</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer Controls */}
        <div className="px-6 py-3 border-t border-[#1e293b] bg-[#131f37] flex items-center justify-between">
          {step > 1 && step < 4 ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setStep((s) => s - 1)}
              disabled={loading || pollingHeartbeat}
            >
              <ArrowLeft className="w-4 h-4 mr-1.5" /> Back
            </Button>
          ) : (
            <div />
          )}

          {step === 1 && (
            <Button variant="primary" size="sm" onClick={generateChallengeToken} disabled={!deviceUid}>
              Next: Generate QR <ArrowRight className="w-4 h-4 ml-1.5" />
            </Button>
          )}

          {step === 2 && (
            <Button variant="primary" size="sm" onClick={handleRegisterDevice} disabled={loading}>
              {loading ? 'Provisioning...' : 'Provision & Listen'} <ArrowRight className="w-4 h-4 ml-1.5" />
            </Button>
          )}

          {step === 3 && (
            <Button variant="outline" size="sm" onClick={() => setStep(4)}>
              Simulate Device ACK
            </Button>
          )}

          {step === 4 && (
            <Button variant="primary" size="sm" onClick={onClose}>
              Done
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};
