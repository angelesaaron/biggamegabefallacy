'use client';

import { useEffect, useState } from 'react';
import { SurfaceCard } from '@/components/ui/SurfaceCard';
import { ChevronDown } from 'lucide-react';
import LogViewerModal from './LogViewerModal';

interface BatchStep {
  id: number;
  step_name: string;
  step_order: number;
  status: string;
  started_at?: string;
  completed_at?: string;
  duration_seconds?: number;
  records_processed: number;
  error_message?: string;
  output_log?: string;
}

interface BatchRun {
  id: number;
  batch_type: string;
  batch_mode?: string;
  season_year: number;
  week: number;
  season_type?: string;
  started_at?: string;
  completed_at?: string;
  duration_seconds?: number;
  status: string;
  games_processed?: number;
  game_logs_added?: number;
  predictions_generated?: number;
  predictions_skipped?: number;
  odds_synced?: number;
  api_calls_made?: number;
  errors_encountered?: number;
  triggered_by?: string;
  steps?: BatchStep[];
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? '';

const STATUS_COLORS: Record<string, string> = {
  success: '#10b981',
  partial: '#eab308',
  failed: '#ef4444',
  running: '#3b82f6',
};

function StepBadge({ status }: { status: string }) {
  const colorMap: Record<string, string> = {
    success: 'bg-sr-success/15 text-sr-success border-sr-success/30',
    failed: 'bg-sr-danger/15 text-sr-danger border-sr-danger/30',
    running: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
    skipped: 'bg-sr-surface text-sr-text-muted border-sr-border',
    pending: 'bg-sr-surface text-sr-text-muted border-sr-border',
  };
  const cls = colorMap[status] ?? colorMap.pending;
  return (
    <span className={`px-1.5 py-0.5 rounded border text-[0.65rem] font-medium ${cls}`}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

export default function BatchHistoryTab() {
  const [batchHistory, setBatchHistory] = useState<BatchRun[]>([]);
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  const [selectedLog, setSelectedLog] = useState<{ stepName: string; log: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');

  const formatDuration = (seconds?: number) => {
    if (!seconds) return 'N/A';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
  };

  const getTimeAgo = (isoString?: string) => {
    if (!isoString) return '';
    const diffMs = Date.now() - new Date(isoString).getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays > 0) return `${diffDays}d ago`;
    if (diffHours > 0) return `${diffHours}h ago`;
    if (diffMins > 0) return `${diffMins}m ago`;
    return 'Just now';
  };

  useEffect(() => {
    async function loadBatchHistory() {
      try {
        setLoading(true);
        const response = await fetch(`${API_URL}/api/admin/batch-runs/history?limit=50`);
        if (!response.ok) throw new Error(`History API failed: ${response.status}`);
        const data = await response.json();
        setBatchHistory(data.batch_runs || []);
      } catch {
        // silent
      } finally {
        setLoading(false);
      }
    }
    loadBatchHistory();
    const interval = setInterval(loadBatchHistory, 30000);
    return () => clearInterval(interval);
  }, []);

  const toggleRow = async (batchId: number) => {
    const newExpanded = new Set(expandedRows);
    if (expandedRows.has(batchId)) {
      newExpanded.delete(batchId);
    } else {
      newExpanded.add(batchId);
      const batch = batchHistory.find((b) => b.id === batchId);
      if (batch && !batch.steps) {
        try {
          const response = await fetch(
            `${API_URL}/api/admin/batch-runs/${batchId}?include_steps=true`
          );
          const data = await response.json();
          setBatchHistory((prev) =>
            prev.map((b) => (b.id === batchId ? { ...b, steps: data.steps } : b))
          );
        } catch {
          // silent
        }
      }
    }
    setExpandedRows(newExpanded);
  };

  const filteredHistory = batchHistory.filter(
    (batch) => filter === 'all' || batch.status === filter
  );

  const FILTERS = ['all', 'success', 'partial', 'failed', 'running'];

  if (loading) {
    return (
      <div className="py-8 text-center">
        <div className="h-1 bg-sr-surface rounded-full overflow-hidden mb-4">
          <div className="h-full bg-sr-primary animate-pulse w-3/4 rounded-full" />
        </div>
        <p className="text-sr-text-muted text-sm">Loading batch history...</p>
      </div>
    );
  }

  return (
    <div>
      {/* Filters */}
      <SurfaceCard className="mb-4 p-3">
        <div className="flex gap-1 flex-wrap">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={
                filter === f
                  ? 'px-3 py-1.5 text-xs font-medium rounded-lg bg-sr-primary text-white transition-colors'
                  : 'px-3 py-1.5 text-xs font-medium rounded-lg text-sr-text-muted hover:text-white transition-colors'
              }
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </SurfaceCard>

      {/* Batch List */}
      <SurfaceCard>
        {filteredHistory.length === 0 ? (
          <p className="text-sr-text-muted text-sm text-center py-8">
            No actions found for the selected filter.
          </p>
        ) : (
          filteredHistory.map((batch) => (
            <div key={batch.id} className="border-b border-sr-border last:border-b-0">
              {/* Main Row */}
              <div
                onClick={() => toggleRow(batch.id)}
                className="flex items-center justify-between p-4 cursor-pointer hover:bg-[rgba(55,65,81,0.3)] transition-colors"
              >
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <span
                    className="w-2 h-2 rounded-full flex-shrink-0"
                    style={{
                      backgroundColor: STATUS_COLORS[batch.status] ?? '#6b7280',
                    }}
                  />
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-sm text-white font-medium">
                        {batch.batch_type.replace('_', ' ')}
                      </span>
                      {batch.batch_mode && (
                        <span className="px-1.5 py-0.5 text-[0.65rem] rounded bg-[#374151] text-gray-300">
                          {batch.batch_mode}
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-sr-text-muted">
                      {batch.season_year} Week {batch.week} · {getTimeAgo(batch.started_at)}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                  <span className="text-xs text-sr-text-muted nums">
                    {formatDuration(batch.duration_seconds)}
                  </span>
                  <ChevronDown
                    size={16}
                    className={`text-sr-text-muted transition-transform ${expandedRows.has(batch.id) ? 'rotate-180' : ''}`}
                  />
                </div>
              </div>

              {/* Expanded */}
              {expandedRows.has(batch.id) && (
                <div className="bg-[rgba(31,41,55,0.2)] border-t border-sr-border p-4">
                  {/* Metrics */}
                  {(batch.games_processed ||
                    batch.game_logs_added ||
                    batch.predictions_generated ||
                    batch.odds_synced ||
                    batch.errors_encountered) && (
                    <div className="flex flex-wrap gap-4 mb-4">
                      {batch.games_processed != null && batch.games_processed > 0 && (
                        <span className="text-xs">
                          <span className="text-sr-text-muted">Games </span>
                          <span className="text-white font-medium nums">{batch.games_processed}</span>
                        </span>
                      )}
                      {batch.game_logs_added != null && batch.game_logs_added > 0 && (
                        <span className="text-xs">
                          <span className="text-sr-text-muted">Logs </span>
                          <span className="text-white font-medium nums">{batch.game_logs_added}</span>
                        </span>
                      )}
                      {batch.predictions_generated != null && batch.predictions_generated > 0 && (
                        <span className="text-xs">
                          <span className="text-sr-text-muted">Predictions </span>
                          <span className="text-white font-medium nums">{batch.predictions_generated}</span>
                        </span>
                      )}
                      {batch.odds_synced != null && batch.odds_synced > 0 && (
                        <span className="text-xs">
                          <span className="text-sr-text-muted">Odds </span>
                          <span className="text-white font-medium nums">{batch.odds_synced}</span>
                        </span>
                      )}
                      {batch.errors_encountered != null && batch.errors_encountered > 0 && (
                        <span className="text-xs">
                          <span className="text-sr-danger">Errors </span>
                          <span className="text-sr-danger font-medium nums">{batch.errors_encountered}</span>
                        </span>
                      )}
                    </div>
                  )}

                  {/* Steps */}
                  {batch.steps && (
                    <div>
                      <p className="text-xs font-medium text-gray-300 mb-2">Steps</p>
                      <div className="flex flex-col gap-2">
                        {batch.steps.map((step) => (
                          <div
                            key={step.id}
                            className="bg-sr-surface/40 border border-[#374151] rounded-xl p-3"
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-3 flex-1 min-w-0">
                                <span className="text-[0.7rem] text-sr-text-dim w-5 flex-shrink-0">
                                  {step.step_order}
                                </span>
                                <div className="min-w-0">
                                  <div className="flex items-center gap-2 mb-0.5">
                                    <span className="text-xs text-white font-medium">
                                      {step.step_name}
                                    </span>
                                    <StepBadge status={step.status} />
                                  </div>
                                  {step.error_message && (
                                    <p className="text-[0.7rem] text-sr-danger">{step.error_message}</p>
                                  )}
                                </div>
                              </div>
                              <div className="flex items-center gap-3 flex-shrink-0">
                                <span className="text-[0.7rem] text-sr-text-muted nums">
                                  {formatDuration(step.duration_seconds)}
                                </span>
                                <span className="text-[0.7rem] text-sr-text-muted nums">
                                  {step.records_processed} rec
                                </span>
                                {step.output_log && (
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setSelectedLog({ stepName: step.step_name, log: step.output_log! });
                                    }}
                                    className="text-[0.7rem] text-sr-primary hover:text-sr-primary/80 transition-colors"
                                  >
                                    Logs
                                  </button>
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))
        )}
      </SurfaceCard>

      {/* Log Modal */}
      {selectedLog && (
        <LogViewerModal
          stepName={selectedLog.stepName}
          log={selectedLog.log}
          onClose={() => setSelectedLog(null)}
        />
      )}
    </div>
  );
}
