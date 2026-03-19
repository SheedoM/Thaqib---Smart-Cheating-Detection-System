import React, { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { jwtDecode } from 'jwt-decode';

interface User {
  id: string;
  username: string;
  email: string;
  role: 'admin' | 'referee' | 'invigilator' | 'superadmin';
  full_name: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (access_token: string, refresh_token: string) => void;
  logout: () => void;
  isAuthenticated: boolean;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const savedToken = localStorage.getItem('access_token');
    if (savedToken) {
      try {
        const decoded = jwtDecode<any>(savedToken);
        const currentTime = Date.now() / 1000;
        
        if (decoded.exp > currentTime) {
          setToken(savedToken);
          setUser({
            id: decoded.sub,
            username: decoded.username,
            email: decoded.email,
            role: decoded.role,
            full_name: decoded.full_name
          });
        } else {
          logout();
        }
      } catch (err) {
        logout();
      }
    }
    setIsLoading(false);
  }, []);

  const login = (access_token: string, refresh_token: string) => {
    localStorage.setItem('access_token', access_token);
    localStorage.setItem('refresh_token', refresh_token);
    
    const decoded = jwtDecode<any>(access_token);
    setToken(access_token);
    setUser({
      id: decoded.sub,
      username: decoded.username,
      email: decoded.email,
      role: decoded.role,
      full_name: decoded.full_name
    });
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, login, logout, isAuthenticated: !!user, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
