import { useContext } from 'react';
import { AuthContext } from '../contexts/AuthContext';

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

export function useIsSubscriber(): boolean {
  return useAuth().isSubscriber;
}

export function useIsAdmin(): boolean {
  return useAuth().isAdmin;
}
