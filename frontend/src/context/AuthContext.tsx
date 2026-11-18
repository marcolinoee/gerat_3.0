import React, { createContext, useContext, useEffect, useState } from "react";
import { apiFetch, setAccessToken } from "@/lib/api";
import type { TokenResponse, User, UserRole } from "@/types/api";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (payload: {
    email: string;
    full_name: string;
    password: string;
    role: UserRole;
    invite_code?: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Silent refresh via HttpOnly cookie on initial app mount
    apiFetch<TokenResponse>("/auth/refresh", { method: "POST" }, false)
      .then((res) => {
        setAccessToken(res.access_token);
        setUser(res.user);
      })
      .catch(() => {
        setAccessToken(null);
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  async function login(email: string, password: string) {
    const res = await apiFetch<TokenResponse>(
      "/auth/login",
      {
        method: "POST",
        body: JSON.stringify({ email, password }),
      },
      false
    );
    setAccessToken(res.access_token);
    setUser(res.user);
  }

  async function register(payload: {
    email: string;
    full_name: string;
    password: string;
    role: UserRole;
    invite_code?: string;
  }) {
    const res = await apiFetch<TokenResponse>(
      "/auth/register",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      false
    );
    setAccessToken(res.access_token);
    setUser(res.user);
  }

  async function logout() {
    try {
      await apiFetch("/auth/logout", { method: "POST" }, false);
    } finally {
      setAccessToken(null);
      setUser(null);
    }
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
