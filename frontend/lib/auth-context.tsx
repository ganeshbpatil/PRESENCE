"use client";

// lib/auth-context.tsx
//
// Minimal client-side auth state: access token in memory + localStorage
// (survives a refresh), attached as a Bearer header by lib/api.ts callers.
// No refresh-token rotation wired up yet in the UI (the endpoint exists --
// /api/v1/auth/refresh -- this is a read-only admin panel, first pass: a
// user just logs back in once the 30-minute access token expires).

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { getMe, login as apiLogin, type UserResponse } from "./api";

const STORAGE_KEY = "presence_access_token";

interface AuthContextValue {
  token: string | null;
  user: UserResponse | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function restoreSession() {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (!stored) return;
      try {
        const u = await getMe(stored);
        if (cancelled) return;
        setToken(stored);
        setUser(u);
      } catch {
        window.localStorage.removeItem(STORAGE_KEY);
      }
    }

    restoreSession().finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await apiLogin(email, password);
    const u = await getMe(tokens.access_token);
    window.localStorage.setItem(STORAGE_KEY, tokens.access_token);
    setToken(tokens.access_token);
    setUser(u);
  }, []);

  const logout = useCallback(() => {
    window.localStorage.removeItem(STORAGE_KEY);
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ token, user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
