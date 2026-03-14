'use client';

interface PaywallGateProps {
  feature: string;
  children: React.ReactNode;
  ctaTitle?: string;
  ctaBody?: string;
}

export function PaywallGate({
  feature,
  children,
  ctaTitle = 'Big Game Gabe — Season Access',
  ctaBody = 'High conviction picks, value plays, and the fade list — every week of the NFL season. Backed by a real model, not gut picks.',
}: PaywallGateProps) {
  const isSubscribed = false; // TODO: replace with auth hook when JWT is wired (Phase 6)
  const devBypass = process.env.NEXT_PUBLIC_DEV_BYPASS_PAYWALL === 'true';
  if (isSubscribed || devBypass) return <>{children}</>;

  return (
    <div className="relative overflow-hidden rounded-card mt-2">
      {/* Real data, CSS blurred */}
      <div className="pointer-events-none select-none" style={{ filter: 'blur(6px)' }} aria-hidden="true">
        {children}
      </div>
      {/* Gate overlay */}
      <div
        className="absolute inset-0 flex flex-col items-center justify-end pb-10"
        style={{ background: 'linear-gradient(to bottom, transparent 0%, rgba(10,10,10,0.95) 30%)' }}
      >
        <div className="text-center px-6 max-w-md">
          <h3 className="text-white text-lg font-semibold mb-2">{ctaTitle}</h3>
          <p className="text-sr-text-muted text-sm mb-5">{ctaBody}</p>
          <button className="bg-sr-primary text-white px-8 py-2.5 rounded-card font-semibold hover:bg-purple-600 transition-colors text-sm">
            Get Access
          </button>
        </div>
      </div>
    </div>
  );
}
