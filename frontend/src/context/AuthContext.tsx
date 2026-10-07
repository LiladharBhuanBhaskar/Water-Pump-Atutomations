import React, { createContext, useContext, useState, useEffect } from 'react';
import { User, UserRole } from '../types';
import { api } from '../services/api';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  hasRole: (roles: UserRole[]) => boolean;
  isOperator: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const OPERATOR_ROLES: UserRole[] = [
  'SUPER_ADMIN',
  'ORGANIZATION_ADMIN',
  'SITE_MANAGER',
  'STATION_OPERATOR',
  'OWNER',
];

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('hydra_token'));
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const logout = () => {
    localStorage.removeItem('hydra_token');
    setToken(null);
    setUser(null);
  };

  useEffect(() => {
    const handleUnauthorized = () => {
      logout();
    };

    window.addEventListener('auth:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized);
  }, []);

  useEffect(() => {
    const initAuth = async () => {
      const storedToken = localStorage.getItem('hydra_token');
      if (storedToken) {
        try {
          const userData = await api.getMe();
          setUser(userData);
          setToken(storedToken);
        } catch (err) {
          console.error('Failed restoring session:', err);
          logout();
        }
      }
      setIsLoading(false);
    };

    initAuth();
  }, []);

  const login = async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const authResp = await api.login(email, password);
      localStorage.setItem('hydra_token', authResp.access_token);
      setToken(authResp.access_token);

      const userData = await api.getMe();
      setUser(userData);
    } finally {
      setIsLoading(false);
    }
  };

  const hasRole = (roles: UserRole[]): boolean => {
    if (!user) return false;
    return roles.includes(user.role);
  };

  const isOperator = user ? OPERATOR_ROLES.includes(user.role) : false;

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
        hasRole,
        isOperator,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
