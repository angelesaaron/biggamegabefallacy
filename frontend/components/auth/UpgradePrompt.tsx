'use client';

interface UpgradePromptProps {
  feature?: string;
}

export function UpgradePrompt({ feature }: UpgradePromptProps) {
  function handleUpgradeClick() {
    // Stripe integration coming in next sprint
  }

  return (
    <div className="bg-sr-surface border border-sr-border rounded-card p-6 text-center">
      <h3 className="text-sr-text-primary text-lg font-semibold mb-2">
        Unlock Full Access
      </h3>
      {feature && (
        <p className="text-sr-text-dim text-xs mb-1 uppercase tracking-wide font-medium">
          {feature}
        </p>
      )}
      <p className="text-sr-text-muted text-sm mb-5 max-w-xs mx-auto">
        Get all picks, favor scores, and tier labels every week of the NFL season.
      </p>
      <button
        type="button"
        onClick={handleUpgradeClick}
        className="bg-sr-primary text-white px-8 py-3 rounded-card font-semibold hover:bg-sr-primary-muted transition-colors"
      >
        Upgrade to Pro
      </button>
    </div>
  );
}
