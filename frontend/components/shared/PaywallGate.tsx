'use client';

import React from 'react';
import { Lock } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { useAuthModal } from '@/contexts/AuthModalContext';

interface PaywallGateProps {
  ctaTitle: string;
  ctaBody?: string;
  onGetAccess?: () => void;
  children: React.ReactNode;
}

export function PaywallGate({ ctaTitle, ctaBody, onGetAccess, children }: PaywallGateProps) {
  const { isSubscriber, isLoading, user } = useAuth();
  const { openRegister } = useAuthModal();

  if (isLoading) return null;

  if (isSubscriber) return <>{children}</>;

  return (
    <div className="border border-sr-primary/20 bg-sr-primary/5 rounded-card p-8 text-center">
      <div className="flex justify-center mb-4">
        <div className="w-12 h-12 rounded-full bg-sr-primary/10 border border-sr-primary/30 flex items-center justify-center">
          <Lock className="w-5 h-5 text-sr-primary" />
        </div>
      </div>
      <h3 className="text-white text-base font-semibold mb-2">{ctaTitle}</h3>
      {ctaBody && (
        <p className="text-sr-text-muted text-sm mb-5 max-w-xs mx-auto">{ctaBody}</p>
      )}
      {user ? (
        <button
          type="button"
          onClick={onGetAccess ?? openRegister}
          className="bg-sr-primary text-white px-6 py-2.5 rounded-card text-sm font-semibold hover:bg-sr-primary/80 transition-colors"
        >
          Upgrade to unlock
        </button>
      ) : (
        <button
          type="button"
          onClick={onGetAccess ?? openRegister}
          className="bg-sr-primary text-white px-6 py-2.5 rounded-card text-sm font-semibold hover:bg-sr-primary/80 transition-colors"
        >
          Get Access
        </button>
      )}
    </div>
  );
}
