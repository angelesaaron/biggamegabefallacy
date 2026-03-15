'use client';

import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useAuthModal } from '../../contexts/AuthModalContext';
import { LoginPanel } from './LoginPanel';
import { RegisterPanel } from './RegisterPanel';
import { ForgotPanel } from './ForgotPanel';

type LocalPanel = 'forgot';

export function AuthModal() {
  const { isOpen, activePanel, openLogin, openRegister, close } = useAuthModal();

  // 'forgot' is managed as local state — context only knows login | register
  const [localPanel, setLocalPanel] = useState<LocalPanel | null>(null);
  const modalRef = useRef<HTMLDivElement>(null);

  // Reset local panel whenever the modal closes or the context panel changes
  useEffect(() => {
    if (!isOpen) {
      setLocalPanel(null);
    }
  }, [isOpen]);

  useEffect(() => {
    setLocalPanel(null);
  }, [activePanel]);

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

  function handleForgotPassword() {
    setLocalPanel('forgot');
  }

  function handleBackFromForgot() {
    setLocalPanel(null);
    openLogin();
  }

  const isForgot = localPanel === 'forgot';

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
        {isForgot ? (
          /* Forgot password view — no tab row */
          <ForgotPanel onBack={handleBackFromForgot} />
        ) : (
          <>
            {/* Tab row — only shown for login / register */}
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
                onForgotPassword={handleForgotPassword}
              />
            ) : (
              <RegisterPanel
                onSuccess={close}
                onSwitchToLogin={openLogin}
              />
            )}
          </>
        )}
      </div>
    </div>
  );

  return createPortal(content, document.body);
}
