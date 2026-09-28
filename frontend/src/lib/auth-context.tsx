"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { CurrentUser } from "@/types/accounting";
import { apiClient } from "@/lib/api-client";
import { appCache } from "@/lib/cache";
import { UNAUTHORIZED_EVENT, clearToken, getToken, setToken } from "@/lib/auth";

interface AuthContextType {
  user: CurrentUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  login: async () => {},
  logout: () => {},
});

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    clearToken();
    appCache.invalidateAll();
    setUser(null);
  }, []);

  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    apiClient
      .getMe()
      .then(setUser)
      .catch(() => logout())
      .finally(() => setLoading(false));
  }, [logout]);

  useEffect(() => {
    // authFetch fires this on any 401 (expired / revoked token)
    window.addEventListener(UNAUTHORIZED_EVENT, logout);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, logout);
  }, [logout]);

  const login = async (username: string, password: string) => {
    const res = await apiClient.login(username, password);
    setToken(res.access_token);
    appCache.invalidateAll();
    setUser(res.user);
  };

  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>;
};

export const useAuth = () => useContext(AuthContext);
