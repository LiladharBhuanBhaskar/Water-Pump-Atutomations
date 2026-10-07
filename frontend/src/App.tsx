import React, { useEffect, useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { Navbar } from './components/Navbar';
import { Spinner } from './components/common/Spinner';
import { ws } from './services/ws';
import { WsServerEvent } from './types';

const MainLayout: React.FC = () => {
  const { isAuthenticated, isLoading, user, token } = useAuth();
  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const [latestWsEvent, setLatestWsEvent] = useState<WsServerEvent | null>(null);

  useEffect(() => {
    if (isAuthenticated && token) {
      ws.connect(token);

      const unbindState = ws.onConnectionState((connected) => {
        setWsConnected(connected);
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
      />
      <main className="flex-1 w-full">
        <Dashboard latestWsEvent={latestWsEvent} />
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
