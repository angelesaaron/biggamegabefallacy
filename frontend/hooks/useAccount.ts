'use client';

import { useAuth } from './useAuth';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function authFetch<T>(
  path: string,
  options: RequestInit,
  token: string,
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...(options.headers as Record<string, string>),
    },
  });

  if (!res.ok) {
    let message = `Request failed: ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) message = body.detail;
    } catch { /* ignore */ }
    throw new Error(message);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export function useAccount() {
  const { user, getToken, refreshUser } = useAuth();

  const updateName = async (firstName: string, lastName: string): Promise<void> => {
    const token = getToken();
    if (!token) throw new Error('Not authenticated');
    await authFetch('/api/users/me', {
      method: 'PATCH',
      body: JSON.stringify({ first_name: firstName, last_name: lastName }),
    }, token);
    await refreshUser();
  };

  const changePassword = async (current: string, next: string): Promise<void> => {
    const token = getToken();
    if (!token) throw new Error('Not authenticated');
    await authFetch('/api/users/me/password', {
      method: 'POST',
      body: JSON.stringify({ current_password: current, new_password: next }),
    }, token);
    await refreshUser();
  };

  const initiateEmailChange = async (newEmail: string): Promise<void> => {
    const token = getToken();
    if (!token) throw new Error('Not authenticated');
    await authFetch('/api/users/me/email', {
      method: 'PATCH',
      body: JSON.stringify({ new_email: newEmail }),
    }, token);
  };

  const cancelSubscription = async (): Promise<void> => {
    const token = getToken();
    if (!token) throw new Error('Not authenticated');
    await authFetch('/api/users/me/cancel', {
      method: 'POST',
      body: JSON.stringify({}),
    }, token);
    await refreshUser();
  };

  return { user, updateName, changePassword, initiateEmailChange, cancelSubscription };
}
