/**
 * HydraControl — Audio & Buzzer Alert Synthesizer
 * Uses the standard Web Audio API to produce crisp, synthesized audible chimes and buzzer alerts
 * without external audio asset dependencies. Handles browser autoplay policies and user interactions.
 */

type UnlockListener = (unlocked: boolean) => void;

class AudioAlertManager {
  private audioCtx: AudioContext | null = null;
  private playedNotifications: Set<string> = new Set();
  private listeners: Set<UnlockListener> = new Set();

  constructor() {
    this.setupAutoplayUnlock();
  }

  public isUnlocked(): boolean {
    return !!this.audioCtx && this.audioCtx.state === 'running';
  }

  public onUnlockChange(listener: UnlockListener): () => void {
    this.listeners.add(listener);
    listener(this.isUnlocked());
    return () => this.listeners.delete(listener);
  }

  private notifyListeners() {
    const status = this.isUnlocked();
    this.listeners.forEach((l) => {
      try {
        l(status);
      } catch {}
    });
  }

  private setupAutoplayUnlock() {
    if (typeof window === 'undefined') return;

    const unlock = async () => {
      try {
        if (!this.audioCtx) {
          const AudioCtxClass = window.AudioContext || (window as any).webkitAudioContext;
          if (AudioCtxClass) {
            this.audioCtx = new AudioCtxClass();
          }
        }
        if (this.audioCtx && this.audioCtx.state === 'suspended') {
          await this.audioCtx.resume();
        }
        this.notifyListeners();
      } catch {
        // Autoplay policy fallback
      }
    };

    window.addEventListener('click', unlock, { passive: true });
    window.addEventListener('keydown', unlock, { passive: true });
    window.addEventListener('touchstart', unlock, { passive: true });
  }

  public async unlockAudio(): Promise<boolean> {
    try {
      if (!this.audioCtx) {
        const AudioCtxClass = window.AudioContext || (window as any).webkitAudioContext;
        if (AudioCtxClass) {
          this.audioCtx = new AudioCtxClass();
        }
      }
      if (this.audioCtx && this.audioCtx.state === 'suspended') {
        await this.audioCtx.resume();
      }
      this.notifyListeners();
      return this.isUnlocked();
    } catch {
      return false;
    }
  }

  /**
   * Directly test the buzzer sound for development and verification.
   */
  public async testSound(severity: string = 'INFO'): Promise<void> {
    await this.unlockAudio();
    await this.playBuzzer(undefined, severity);
  }

  /**
   * Plays a distinct buzzer tone.
   * @param notificationId Optional ID for deduplication (prevents double-sounding)
   * @param severity 'INFO' | 'WARNING' | 'CRITICAL'
   */
  public async playBuzzer(notificationId?: string, severity: string = 'INFO'): Promise<void> {
    // 1. Deduplication check
    if (notificationId) {
      if (this.playedNotifications.has(notificationId)) {
        return;
      }
      this.playedNotifications.add(notificationId);
      // Keep cache small (max 100 IDs)
      if (this.playedNotifications.size > 100) {
        const first = this.playedNotifications.values().next().value;
        if (first) this.playedNotifications.delete(first);
      }
    }

    try {
      if (!this.audioCtx) {
        const AudioCtxClass = window.AudioContext || (window as any).webkitAudioContext;
        if (AudioCtxClass) {
          this.audioCtx = new AudioCtxClass();
        }
      }

      if (!this.audioCtx) return;

      if (this.audioCtx.state === 'suspended') {
        await this.audioCtx.resume();
        this.notifyListeners();
      }

      const now = this.audioCtx.currentTime;
      const gainNode = this.audioCtx.createGain();
      gainNode.connect(this.audioCtx.destination);

      const sevUpper = severity.toUpperCase();

      if (sevUpper === 'CRITICAL' || sevUpper === 'EMERGENCY_STOP' || sevUpper === 'FAULT') {
        // High urgency 3-beep alarm (Sawtooth 880Hz -> 1174Hz)
        for (let i = 0; i < 3; i++) {
          const osc = this.audioCtx.createOscillator();
          osc.type = 'sawtooth';
          osc.frequency.setValueAtTime(880, now + i * 0.15);
          osc.frequency.setValueAtTime(1174, now + i * 0.15 + 0.07);

          const subGain = this.audioCtx.createGain();
          subGain.gain.setValueAtTime(0.3, now + i * 0.15);
          subGain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.15 + 0.12);

          osc.connect(subGain);
          subGain.connect(this.audioCtx.destination);

          osc.start(now + i * 0.15);
          osc.stop(now + i * 0.15 + 0.13);
        }
      } else if (sevUpper === 'WARNING' || sevUpper === 'TIMER_WARNING') {
        // Warning 2-tone chime (700Hz -> 880Hz)
        const osc = this.audioCtx.createOscillator();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(700, now);
        osc.frequency.setValueAtTime(880, now + 0.18);

        gainNode.gain.setValueAtTime(0.3, now);
        gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.45);

        osc.connect(gainNode);
        osc.start(now);
        osc.stop(now + 0.45);
      } else {
        // Standard pleasant 2-tone schedule chime (880Hz -> 1046.5Hz, A5 -> C6)
        const osc = this.audioCtx.createOscillator();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(880, now);
        osc.frequency.setValueAtTime(1046.5, now + 0.16);

        gainNode.gain.setValueAtTime(0.3, now);
        gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.5);

        osc.connect(gainNode);
        osc.start(now);
        osc.stop(now + 0.5);
      }
    } catch {
      // Autoplay or security constraint handled gracefully
    }
  }
}

export const audioAlert = new AudioAlertManager();
