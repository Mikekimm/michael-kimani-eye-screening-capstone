import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { NetworkError } from "@/lib/api/http";
import type { User } from "@/lib/api/types";
import type { SignUpInput } from "@/lib/api/endpoints";
import { useServices } from "@/lib/services";

const USER_CACHE = "retina.user";

interface AuthState {
  user: User | null;
  /** true until the stored session has been checked on start-up */
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  /** Creates a pending account; the person can sign in once an administrator approves it. */
  register: (input: SignUpInput) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

function cachedUser(): User | null {
  try {
    const raw = localStorage.getItem(USER_CACHE);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const { api, tokens } = useServices();
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const remember = useCallback((next: User | null) => {
    setUser(next);
    if (next) localStorage.setItem(USER_CACHE, JSON.stringify(next));
    else localStorage.removeItem(USER_CACHE);
  }, []);

  useEffect(() => {
    if (!tokens.accessToken) {
      setLoading(false);
      return;
    }
    api.auth
      .me()
      .then(remember)
      .catch((error) => {
        // Offline at start-up: keep the last known user so capture and queueing still work.
        if (error instanceof NetworkError) setUser(cachedUser());
        else remember(null);
      })
      .finally(() => setLoading(false));
  }, [api, tokens, remember]);

  const login = useCallback(async (email: string, password: string) => {
    tokens.save(await api.auth.login(email, password));
    const me = await api.auth.me();
    remember(me);
    return me;
  }, [api, tokens, remember]);

  const register = useCallback(async (input: SignUpInput) => {
    await api.auth.register(input);
  }, [api]);

  const logout = useCallback(async () => {
    const refresh = tokens.refreshToken;
    tokens.clear();
    remember(null);
    queryClient.clear();
    if (refresh) await api.auth.logout(refresh).catch(() => undefined);
  }, [api, tokens, remember, queryClient]);

  const value = useMemo(() => ({ user, loading, login, register, logout }), [user, loading, login, register, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const auth = useContext(AuthContext);
  if (!auth) throw new Error("useAuth must be used inside AuthProvider");
  return auth;
}
