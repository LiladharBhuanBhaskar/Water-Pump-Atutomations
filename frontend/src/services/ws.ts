/**
 * HydraControl — Real-Time WebSocket Client Service
 * Manages authenticated WebSocket streaming, channel subscriptions,
 * automatic reconnect with exponential backoff, PING/PONG heartbeats,
 * and event dispatching to UI subscribers.
 */

import { WsServerEvent } from '../types';

type EventListener = (event: WsServerEvent) => void;
type ConnectionStateListener = (connected: boolean) => void;

class WebSocketService {
  private socket: WebSocket | null = null;
  private token: string | null = null;
  private channels: Set<string> = new Set();
  private eventListeners: Set<EventListener> = new Set();
  private stateListeners: Set<ConnectionStateListener> = new Set();
  private reconnectAttempts = 0;
  private maxReconnectDelay = 15000;
  private reconnectTimeoutId: any = null;
  private pingIntervalId: any = null;
  private isExplicitlyClosed = false;

  public isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  public connect(token: string) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN && this.token === token) {
      return;
    }

    this.token = token;
    this.isExplicitlyClosed = false;
    this.initializeSocket();
  }

  private initializeSocket() {
    if (!this.token) return;

    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/api/v1/ws?token=${encodeURIComponent(this.token)}`;

    try {
      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = () => {
        this.reconnectAttempts = 0;
        this.notifyStateChange(true);
        this.startHeartbeat();

        // Resubscribe to all active channels
        if (this.channels.size > 0) {
          this.send({
            action: 'SUBSCRIBE',
            channels: Array.from(this.channels),
          });
        }
      };

      this.socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'PONG') {
            return;
          }
          if (data.event) {
            this.notifyEventListeners(data as WsServerEvent);
          }
        } catch (err) {
          console.error('Error parsing WebSocket message:', err);
        }
      };

      this.socket.onclose = () => {
        this.stopHeartbeat();
        this.notifyStateChange(false);
        this.socket = null;

        if (!this.isExplicitlyClosed) {
          this.scheduleReconnect();
        }
      };

      this.socket.onerror = (error) => {
        console.warn('WebSocket error encountered:', error);
      };
    } catch (err) {
      console.error('Failed creating WebSocket:', err);
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimeoutId || this.isExplicitlyClosed) return;

    const delay = Math.min(
      1000 * Math.pow(1.5, this.reconnectAttempts),
      this.maxReconnectDelay
    );
    this.reconnectAttempts++;

    this.reconnectTimeoutId = setTimeout(() => {
      this.reconnectTimeoutId = null;
      this.initializeSocket();
    }, delay);
  }

  private startHeartbeat() {
    this.stopHeartbeat();
    this.pingIntervalId = setInterval(() => {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        this.send({ action: 'PING' });
      }
    }, 25000);
  }

  private stopHeartbeat() {
    if (this.pingIntervalId) {
      clearInterval(this.pingIntervalId);
      this.pingIntervalId = null;
    }
  }

  public subscribeChannels(newChannels: string[]) {
    newChannels.forEach((ch) => this.channels.add(ch));

    if (this.socket && this.socket.readyState === WebSocket.OPEN && newChannels.length > 0) {
      this.send({
        action: 'SUBSCRIBE',
        channels: newChannels,
      });
    }
  }

  public unsubscribeChannels(oldChannels: string[]) {
    oldChannels.forEach((ch) => this.channels.delete(ch));

    if (this.socket && this.socket.readyState === WebSocket.OPEN && oldChannels.length > 0) {
      this.send({
        action: 'UNSUBSCRIBE',
        channels: oldChannels,
      });
    }
  }

  public send(payload: any) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(payload));
    }
  }

  public onEvent(callback: EventListener): () => void {
    this.eventListeners.add(callback);
    return () => {
      this.eventListeners.delete(callback);
    };
  }

  public onConnectionState(callback: ConnectionStateListener): () => void {
    this.stateListeners.add(callback);
    callback(this.isConnected());
    return () => {
      this.stateListeners.delete(callback);
    };
  }

  private notifyEventListeners(event: WsServerEvent) {
    this.eventListeners.forEach((listener) => {
      try {
        listener(event);
      } catch (err) {
        console.error('Error in WS event listener:', err);
      }
    });
  }

  private notifyStateChange(connected: boolean) {
    this.stateListeners.forEach((listener) => {
      try {
        listener(connected);
      } catch (err) {
        console.error('Error in WS state listener:', err);
      }
    });
  }

  public disconnect() {
    this.isExplicitlyClosed = true;
    this.stopHeartbeat();
    if (this.reconnectTimeoutId) {
      clearTimeout(this.reconnectTimeoutId);
      this.reconnectTimeoutId = null;
    }
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
    this.channels.clear();
    this.token = null;
    this.notifyStateChange(false);
  }
}

export const ws = new WebSocketService();
