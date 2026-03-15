'use client';

import React, { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useAuthModal } from '../../contexts/AuthModalContext';
import { LoginPanel } from './LoginPanel';
import { RegisterPanel } from './RegisterPanel';

export function AuthModal() {
  const { isOpen, activePanel, openLogin, openRegister, close } = useAuthModal();
  const modalRef = useRef<HTMLDivElement>(null);

  // Escape key and focus trap
  useEffect(() => {
    if (!isOpen) return;

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        close();
        return;
      }

      if (e.key !== 'Tab') return;

      const modal = modalRef.current;
      if (!modal) return;

      const focusable = modal.querySelectorAll<HTMLElement>(
        'button, input, a[href], select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      const focusableArr = Array.from(focusable).filter(
        (el) => !el.hasAttribute('disabled') && el.getAttribute('tabindex') !== '-1',
      );
      if (focusableArr.length === 0) return;

      const first = focusableArr[0];
      const last = focusableArr[focusableArr.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown);

    // Prevent body scroll while modal open
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = prevOverflow;
    };
  }, [isOpen, close]);

  if (!isOpen) return null;

  function handleBackdropClick(e: React.MouseEvent<HTMLDivElement>) {
    if (e.target === e.currentTarget) close();
  }

  const content = (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center px-0 sm:px-4"
      style={{ backgroundColor: 'rgba(0,0,0,0.80)' }}
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby="auth-modal-title"
    >
      <div
        ref={modalRef}
        className="bg-sr-surface w-full sm:max-w-sm sm:rounded-card shadow-2xl"
      >
        {/* Tab row */}
        <div className="flex border-b border-sr-border">
          <button
            type="button"
            id="auth-modal-title"
            onClick={openLogin}
            className={[
              'flex-1 py-3.5 text-sm font-medium transition-colors',
              activePanel === 'login'
                ? 'border-b-2 border-sr-primary text-white font-semibold'
                : 'text-sr-text-muted hover:text-white border-b-2 border-transparent',
            ].join(' ')}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={openRegister}
            className={[
              'flex-1 py-3.5 text-sm font-medium transition-colors',
              activePanel === 'register'
                ? 'border-b-2 border-sr-primary text-white font-semibold'
                : 'text-sr-text-muted hover:text-white border-b-2 border-transparent',
            ].join(' ')}
          >
            Create Account
          </button>
        </div>

        {/* Panel content */}
        {activePanel === 'login' ? (
          <LoginPanel
            onSuccess={close}
            onSwitchToRegister={openRegister}
          />
        ) : (
          <RegisterPanel
            onSuccess={close}
            onSwitchToLogin={openLogin}
          />
        )}
      </div>
    </div>
  );

  return createPortal(content, document.body);
}
