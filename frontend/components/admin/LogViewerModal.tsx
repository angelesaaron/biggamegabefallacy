'use client';

import { useState } from 'react';
import { X, Copy, CheckCircle } from 'lucide-react';

interface LogViewerModalProps {
  stepName: string;
  log: string;
  onClose: () => void;
}

export default function LogViewerModal({ stepName, log, onClose }: LogViewerModalProps) {
  const [copied, setCopied] = useState(false);

  const copyToClipboard = () => {
    navigator.clipboard.writeText(log);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.7)' }}
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-2xl max-h-[80vh] flex flex-col bg-sr-surface border border-sr-border rounded-card overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-4 border-b border-sr-border">
          <div>
            <p className="text-white font-semibold text-sm">Step Output Log</p>
            <p className="text-sr-text-muted text-xs mt-0.5">{stepName}</p>
          </div>
          <button
            onClick={onClose}
            className="text-sr-text-muted hover:text-white transition-colors ml-4"
          >
            <X size={18} />
          </button>
        </div>

        {/* Log content */}
        <div className="flex-1 overflow-y-auto bg-sr-bg p-4 font-mono text-sm">
          {log ? (
            <pre className="text-gray-300 whitespace-pre-wrap break-words m-0">{log}</pre>
          ) : (
            <p className="text-sr-text-dim text-center py-12">
              No output logs available for this step
            </p>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-3 border-t border-sr-border bg-sr-surface">
          <span className="text-xs text-sr-text-dim">Showing last 100 lines of output</span>
          <div className="flex gap-2">
            <button
              onClick={copyToClipboard}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-[#1f2937] text-sr-text-muted hover:text-white transition-colors"
            >
              {copied ? <CheckCircle size={14} className="text-sr-success" /> : <Copy size={14} />}
              {copied ? 'Copied!' : 'Copy'}
            </button>
            <button
              onClick={onClose}
              className="px-3 py-1.5 text-xs rounded-lg bg-sr-primary text-white hover:bg-sr-primary/90 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
