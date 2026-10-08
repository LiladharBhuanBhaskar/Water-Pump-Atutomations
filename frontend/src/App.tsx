import React, { useEffect, useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { HomeDashboard } from './pages/HomeDashboard';
import { Navbar } from './components/Navbar';
import { MobileHeader } from './components/MobileHeader';
import { Spinner } from './components/common/Spinner';
import { WsConnectionBanner, WsStatus } from './components/common/WsConnectionBanner';
import { ErrorBoundary } from './components/common/ErrorBoundary';
import { ws } from './services/ws';
import { WsServerEvent } from './types';

const MainLayout: React.FC = () => {
  const { isAuthenticated, isLoading, user, token, logout } = useAuth();
  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const [wsStatus, setWsStatus] = useState<WsStatus>('DISCONNECTED');
  const [reconnectAttempts, setReconnectAttempts] = useState<number>(0);
  const [latestWsEvent, setLatestWsEvent] = useState<WsServerEvent | null>(null);

  // Default view routing: Admins get Enterprise Admin Console, Operators/Users get User App
  const isOperatorOrHomeUser =
    user?.role === 'STATION_OPERATOR' ||
    user?.role === 'OWNER' ||
    user?.role === 'FAMILY_MEMBER' ||
    user?.role === 'VIEWER';
  const [viewMode, setViewMode] = useState<'ENTERPRISE' | 'HOME'>('HOME');

  useEffect(() => {
    if (isOperatorOrHomeUser) {
      setViewMode('HOME');
    } else {
      setViewMode('ENTERPRISE');
    }
  }, [isOperatorOrHomeUser]);

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
      <div className="min-h-screen bg-[#f0f4f9] flex items-center justify-center">
        <Spinner size="lg" label="Initializing HydraControl..." />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Login />;
  }

  // Mobile App View (HOME mode matching provided screenshots pixel-by-pixel)
  if (viewMode === 'HOME') {
    return (
      <div className="min-h-screen bg-[#f0f4f9] text-slate-900 flex flex-col selection:bg-blue-500 selection:text-white">
        <MobileHeader
          wsConnected={wsConnected}
          onAvatarClick={() => {
            if (user?.role === 'SUPER_ADMIN' || user?.role === 'ORGANIZATION_ADMIN') {
              setViewMode('ENTERPRISE');
            } else {
              logout();
            }
          }}
        />

        <main className="flex-1 w-full pb-10">
          <ErrorBoundary fallbackTitle="Mobile App View Error">
            <HomeDashboard
              latestWsEvent={latestWsEvent}
              wsConnected={wsConnected}
              onAdminSwitch={
                user?.role === 'SUPER_ADMIN' || user?.role === 'ORGANIZATION_ADMIN'
                  ? () => setViewMode('ENTERPRISE')
                  : undefined
              }
            />
          </ErrorBoundary>
        </main>
      </div>
    );
  }

  // Enterprise Admin Console View
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-cyan-500 selection:text-black">
      <Navbar
        wsConnected={wsConnected}
        activeOrgName={user?.organization_id ? `Org ${user.organization_id.slice(0, 8)}` : undefined}
        activeMode={viewMode}
        onModeToggle={() => setViewMode('HOME')}
      />

      <WsConnectionBanner status={wsStatus} reconnectAttempts={reconnectAttempts} />

      <main className="flex-1 w-full">
        <ErrorBoundary fallbackTitle="Dashboard View Error">
          <Dashboard latestWsEvent={latestWsEvent} />
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
