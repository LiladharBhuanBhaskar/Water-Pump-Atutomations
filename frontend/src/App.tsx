import React, { useEffect, useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { HomeDashboard } from './pages/HomeDashboard';
import { Navbar } from './components/Navbar';
import { Spinner } from './components/common/Spinner';
import { WsConnectionBanner, WsStatus } from './components/common/WsConnectionBanner';
import { ErrorBoundary } from './components/common/ErrorBoundary';
import { ws } from './services/ws';
import { WsServerEvent } from './types';

const MainLayout: React.FC = () => {
  const { isAuthenticated, isLoading, user, token } = useAuth();
  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const [wsStatus, setWsStatus] = useState<WsStatus>('DISCONNECTED');
  const [reconnectAttempts, setReconnectAttempts] = useState<number>(0);
  const [latestWsEvent, setLatestWsEvent] = useState<WsServerEvent | null>(null);

  // Home Mode vs Enterprise Mode state (Phase 21)
  const isResidentialUser = user?.role === 'OWNER' || user?.role === 'FAMILY_MEMBER';
  const [viewMode, setViewMode] = useState<'ENTERPRISE' | 'HOME'>('ENTERPRISE');

  useEffect(() => {
    if (isResidentialUser) {
      setViewMode('HOME');
    } else {
      setViewMode('ENTERPRISE');
    }
  }, [isResidentialUser]);

  useEffect(() => {
    if (isAuthenticated && token) {
      ws.connect(token);

      const unbindState = ws.onConnectionState((connected) => {
        setWsConnected(connected);
      });

      const unbindStatus = ws.onStatusChange((status, attempts) => {
        setWsStatus(status);
        setReconnectAttempts(attempts);
      });

      const unbindEvent = ws.onEvent((event) => {
        setLatestWsEvent(event);
      });

      // Subscribe to user's organization channel by default
      if (user?.organization_id) {
        ws.subscribeChannels([`org:${user.organization_id}`]);
      }

      return () => {
        unbindState();
        unbindStatus();
        unbindEvent();
        ws.disconnect();
      };
    } else {
      ws.disconnect();
    }
  }, [isAuthenticated, token, user?.organization_id]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <Spinner size="lg" label="Initializing HydraControl..." />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Login />;
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-cyan-500 selection:text-black">
      <Navbar
        wsConnected={wsConnected}
        activeOrgName={user?.organization_id ? `Org ${user.organization_id.slice(0, 8)}` : undefined}
        activeMode={viewMode}
        onModeToggle={() => setViewMode((prev) => (prev === 'ENTERPRISE' ? 'HOME' : 'ENTERPRISE'))}
      />

      <WsConnectionBanner status={wsStatus} reconnectAttempts={reconnectAttempts} />

      <main className="flex-1 w-full">
        <ErrorBoundary fallbackTitle="Dashboard View Error">
          {viewMode === 'HOME' ? (
            <HomeDashboard latestWsEvent={latestWsEvent} />
          ) : (
            <Dashboard latestWsEvent={latestWsEvent} />
          )}
        </ErrorBoundary>
      </main>

      <footer className="border-t border-slate-800/60 py-6 text-center text-xs text-slate-500">
        HydraControl Commercial IoT Platform &bull; Cloud Controls, Local Controller Protects
      </footer>
    </div>
  );
};

export default function App() {
  return (
    <AuthProvider>
      <MainLayout />
    </AuthProvider>
  );
}
