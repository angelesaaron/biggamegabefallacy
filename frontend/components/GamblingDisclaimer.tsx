import { AlertTriangle } from 'lucide-react';

export function GamblingDisclaimer() {
  return (
    <div className="mt-8 bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-6">
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
        <div className="text-sm text-yellow-200/90">
          <p className="font-semibold mb-2">Important Disclaimer</p>
          <p className="text-yellow-200/70">
            This tool provides statistical analysis and should not be used as the sole basis for gambling decisions.
            The edge calculations are for informational purposes only and do not guarantee winning outcomes.
            Please gamble responsibly and within your means. If you or someone you know has a gambling problem,
            please call the National Problem Gambling Helpline at 1-800-522-4700.
          </p>
        </div>
      </div>
    </div>
  );
}
