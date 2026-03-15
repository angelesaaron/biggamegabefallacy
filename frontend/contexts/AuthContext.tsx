'use client';

import React, {
  createContext,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import { AuthUser } from '../types/auth';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const TOKEN_KEY = 'bggtdm_access_token';
const EXPLICIT_LOGOUT_KEY = 'bggtdm_explicit_logout';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AuthContextValue {
  user: AuthUser | null;
  isLoading: boolean;
  isSubscriber: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshToken: () => Promise<boolean>;
  getToken: () => string | null;
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

export const AuthContext = createContext<AuthContextValue | null>(null);

// ---------------------------------------------------------------------------
// JWT helpers (no external library — decode only, no verification)
// ---------------------------------------------------------------------------

interface JwtPayload {
  exp?: number;
  sub?: string;
  [key: string]: unknown;
}

function decodeJwtPayload(token: string): JwtPayload | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    // Base64url → Base64
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=');
    const json = atob(padded);
    return JSON.parse(json) as JwtPayload;
  } catch {
    return null;
  }
}

function tokenIsExpired(token: string): boolean {
  const payload = decodeJwtPayload(token);
  if (!payload || typeof payload.exp !== 'number') return true;
  // Consider expired if less than 10 seconds remain (clock skew buffer)
  return payload.exp * 1000 < Date.now() + 10_000;
}

function tokenExpiresAt(token: string): number | null {
  const payload = decodeJwtPayload(token);
  if (!payload || typeof payload.exp !== 'number') return null;
  return payload.exp * 1000; // ms
}

// ---------------------------------------------------------------------------
// Storage helpers
// ---------------------------------------------------------------------------

function storeToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // localStorage unavailable (SSR or restricted context) — ignore
  }
}

function loadToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // ignore
  }
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null,
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    credentials: 'include', // send/receive httpOnly cookies for refresh token
    headers,
  });

  if (!res.ok) {
    let message = `Request failed: ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) message = body.detail;
    } catch {
      // ignore parse error
    }
    const err = new Error(message);
    (err as Error & { status: number }).status = res.status;
    throw err;
  }

  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

interface TokenResponse {
  access_token: string;
  token_type: string;
}

interface MeResponse {
  id: string;
  email: string;
  is_subscriber: boolean;
  is_active: boolean;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ---------------------------------------------------------------------------
  // Schedule proactive token refresh 2 min before expiry
  // ---------------------------------------------------------------------------
  const scheduleRefresh = useCallback((token: string) => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
    const expiresAt = tokenExpiresAt(token);
    if (!expiresAt) return;
    const refreshAt = expiresAt - 2 * 60 * 1000; // 2 min before expiry
    const delay = refreshAt - Date.now();
    if (delay <= 0) return; // already past refresh window — will be handled on next API call
    refreshTimerRef.current = setTimeout(async () => {
      await performRefresh();
    }, delay);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ---------------------------------------------------------------------------
  // Core refresh logic (returns new token or null)
  // ---------------------------------------------------------------------------
  const performRefresh = useCallback(async (): Promise<string | null> => {
    try {
      const data = await apiFetch<TokenResponse>('/api/auth/refresh', {
        method: 'POST',
      });
      storeToken(data.access_token);
      scheduleRefresh(data.access_token);
      return data.access_token;
    } catch {
      return null;
    }
  }, [scheduleRefresh]);

  // ---------------------------------------------------------------------------
  // Fetch /api/auth/me to hydrate user state
  // ---------------------------------------------------------------------------
  const hydrateUser = useCallback(
    async (token: string): Promise<boolean> => {
      try {
        const me = await apiFetch<MeResponse>('/api/auth/me', {}, token);
        setUser({ id: me.id, email: me.email, is_subscriber: me.is_subscriber });
        scheduleRefresh(token);
        return true;
      } catch {
        return false;
      }
    },
    [scheduleRefresh],
  );

  // ---------------------------------------------------------------------------
  // Initialization — runs once on mount
  // ---------------------------------------------------------------------------
  useEffect(() => {
    async function initialize() {
      setIsLoading(true);
      try {
        const storedToken = loadToken();

        if (storedToken && !tokenIsExpired(storedToken)) {
          // Token exists and is not expired — hydrate user
          const ok = await hydrateUser(storedToken);
          if (!ok) {
            // /me failed — try refresh
            const newToken = await performRefresh();
            if (newToken) {
              await hydrateUser(newToken);
            } else {
              clearToken();
            }
          }
        } else if (storedToken && tokenIsExpired(storedToken)) {
          // Token expired — try refresh via cookie
          clearToken();
          const newToken = await performRefresh();
          if (newToken) {
            await hydrateUser(newToken);
          }
        }
        // else: no token and no refresh cookie → user stays null

        // Dev auto-login: if credentials are set in env and no session exists, log in automatically.
        // Gated on NODE_ENV === 'development' so Next.js tree-shakes this entire block from
        // production bundles — credentials never ship to the browser in prod even if accidentally
        // set in Vercel env vars.
        if (process.env.NODE_ENV === 'development') {
          const devEmail = process.env.NEXT_PUBLIC_DEV_USER_EMAIL;
          const devPassword = process.env.NEXT_PUBLIC_DEV_USER_PASSWORD;
          const explicitlyLoggedOut = sessionStorage.getItem(EXPLICIT_LOGOUT_KEY) === '1';
          if (devEmail && devPassword && !explicitlyLoggedOut) {
            // Only auto-login if we don't already have a user from the normal init flow
            // (check via localStorage since user state may not be set yet)
            const existingToken = loadToken();
            if (!existingToken || tokenIsExpired(existingToken)) {
              try {
                const formBody = new URLSearchParams();
                formBody.append('username', devEmail);
                formBody.append('password', devPassword);
                const data = await apiFetch<TokenResponse>('/api/auth/login', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                  body: formBody.toString(),
                });
                storeToken(data.access_token);
                await hydrateUser(data.access_token);
              } catch (e) {
                console.warn('[DEV] Auto-login failed — is the backend running?', e);
              }
            }
          }
        }
      } finally {
        setIsLoading(false);
      }
    }

    initialize();

    return () => {
      if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    };
  }, [hydrateUser, performRefresh]);

  // ---------------------------------------------------------------------------
  // Public API: login
  // ---------------------------------------------------------------------------
  const login = useCallback(
    async (email: string, password: string): Promise<void> => {
      let data: TokenResponse;
      try {
        const formBody = new URLSearchParams();
        formBody.append('username', email);   // OAuth2PasswordRequestForm uses 'username'
        formBody.append('password', password);

        data = await apiFetch<TokenResponse>('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: formBody.toString(),
        });
      } catch (err) {
        const msg = (err as Error).message;
        if (msg.includes('401') || msg.toLowerCase().includes('incorrect') || msg.toLowerCase().includes('invalid')) {
          throw new Error('Invalid email or password');
        }
        throw new Error(msg || 'Login failed. Please try again.');
      }

      storeToken(data.access_token);
      const ok = await hydrateUser(data.access_token);
      if (!ok) throw new Error('Login succeeded but failed to load user profile.');
    },
    [hydrateUser],
  );

  // ---------------------------------------------------------------------------
  // Public API: register
  // ---------------------------------------------------------------------------
  const register = useCallback(
    async (email: string, password: string): Promise<void> => {
      let data: TokenResponse;
      try {
        data = await apiFetch<TokenResponse>('/api/auth/register', {
          method: 'POST',
          body: JSON.stringify({ email, password }),
        });
      } catch (err) {
        const msg = (err as Error).message;
        if (msg.includes('409') || msg.toLowerCase().includes('already') || msg.toLowerCase().includes('exists')) {
          throw new Error('Email already registered');
        }
        throw new Error(msg || 'Registration failed. Please try again.');
      }

      storeToken(data.access_token);
      const ok = await hydrateUser(data.access_token);
      if (!ok) throw new Error('Registration succeeded but failed to load user profile.');
    },
    [hydrateUser],
  );

  // ---------------------------------------------------------------------------
  // Public API: logout
  // ---------------------------------------------------------------------------
  const logout = useCallback(async (): Promise<void> => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
    clearToken();
    setUser(null);
    // Prevent dev auto-login from re-authenticating on next page load
    try { sessionStorage.setItem(EXPLICIT_LOGOUT_KEY, '1'); } catch { /* ignore */ }
    try {
      await apiFetch<void>('/api/auth/logout', { method: 'POST' });
    } catch {
      // Best-effort — cookie may already be cleared server-side
    }
  }, []);

  // ---------------------------------------------------------------------------
  // Public API: refreshToken (returns false if refresh fails)
  // ---------------------------------------------------------------------------
  const refreshToken = useCallback(async (): Promise<boolean> => {
    const newToken = await performRefresh();
    if (!newToken) {
      clearToken();
      setUser(null);
      return false;
    }
    return true;
  }, [performRefresh]);

  const value: AuthContextValue = {
    user,
    isLoading,
    isSubscriber: user !== null && user.is_subscriber,
    login,
    register,
    logout,
    refreshToken,
    getToken: loadToken,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
