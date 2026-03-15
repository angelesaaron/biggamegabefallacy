'use client';

import { Lock } from 'lucide-react';
import { useAuthModal } from '@/contexts/AuthModalContext';

interface TeaserBannerProps {
  label: string;
  count: number;
  noun: string;
  accentClass: string;
  headerTextClass: string;
  descriptor: string;
}

export function TeaserBanner({ label, count, noun, accentClass, headerTextClass, descriptor }: TeaserBannerProps) {
  const { openRegister, openLogin } = useAuthModal();
  const plural = count !== 1 ? `${noun}s` : noun;

  return (
    <section className="mb-8">
      <div className={`flex items-baseline gap-3 mb-3 pb-2 border-b ${accentClass}`}>
        <h2 className={`text-base font-semibold ${headerTextClass}`}>{label}</h2>
        <span className="text-sr-text-dim text-xs">{descriptor}</span>
      </div>
      <div className="border border-sr-primary/20 bg-sr-primary/5 rounded-card p-6 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Lock className="w-4 h-4 text-sr-primary flex-shrink-0" />
          <span className="text-white text-sm font-medium">
            {count} {plural} identified this week
          </span>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <button
            onClick={openLogin}
            className="text-xs text-sr-text-muted hover:text-white underline underline-offset-2 transition-colors"
          >
            Sign in
          </button>
          <button
            onClick={openRegister}
            className="bg-sr-primary text-white px-4 py-2 rounded-card text-xs font-semibold hover:bg-sr-primary/80 transition-colors"
          >
            Get Access
          </button>
        </div>
      </div>
    </section>
  );
}
