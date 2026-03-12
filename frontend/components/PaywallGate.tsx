'use client';

interface PaywallGateProps {
  feature: string;
  children: React.ReactNode;
}

export function PaywallGate({ feature, children }: PaywallGateProps) {
  const isSubscribed = false; // TODO: replace with auth hook when JWT is wired (Phase 6)
  if (isSubscribed) return <>{children}</>;

  return (
    <div className="relative overflow-hidden rounded-card mt-8">
      {/* Real data, CSS blurred */}
      <div className="pointer-events-none select-none" style={{ filter: 'blur(6px)' }} aria-hidden="true">
        {children}
      </div>
      {/* Gate overlay */}
      <div
        className="absolute inset-0 flex flex-col items-center justify-end pb-12"
        style={{ background: 'linear-gradient(to bottom, transparent 0%, rgba(10,10,10,0.95) 35%)' }}
      >
        <div className="text-center px-6 max-w-md">
          <p className="text-sr-text-muted text-sm mb-2">Full breakdown</p>
          <h3 className="text-white text-xl font-semibold mb-3">Big Game Gabe Pro</h3>
          <p className="text-sr-text-muted text-sm mb-6">
            Per-player prediction history, calibration by position, and weekly edge reports
          </p>
          <button className="bg-sr-primary text-white px-8 py-3 rounded-card font-semibold hover:bg-purple-600 transition-colors">
            Get Access
          </button>
        </div>
      </div>
    </div>
  );
}
