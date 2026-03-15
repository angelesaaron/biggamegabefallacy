'use client';

import React, { createContext, useContext, useState } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AuthModalContextValue {
  isOpen: boolean;
  activePanel: 'login' | 'register';
  openLogin: () => void;
  openRegister: () => void;
  close: () => void;
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const AuthModalContext = createContext<AuthModalContextValue | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthModalProvider({ children }: { children: React.ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [activePanel, setActivePanel] = useState<'login' | 'register'>('login');

  function openLogin() {
    setActivePanel('login');
    setIsOpen(true);
  }

  function openRegister() {
    setActivePanel('register');
    setIsOpen(true);
  }

  function close() {
    setIsOpen(false);
  }

  const value: AuthModalContextValue = {
    isOpen,
    activePanel,
    openLogin,
    openRegister,
    close,
  };

  return (
    <AuthModalContext.Provider value={value}>
      {children}
    </AuthModalContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAuthModal(): AuthModalContextValue {
  const ctx = useContext(AuthModalContext);
  if (!ctx) throw new Error('useAuthModal must be used within AuthModalProvider');
  return ctx;
}
