'use client';

import { useEffect, useState } from 'react';
import { SurfaceCard } from '@/components/ui/SurfaceCard';
import { Progress } from '@/components/ui/progress';

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
  api_calls_made?: number;
  games_processed?: number;
  game_logs_added?: number;
  predictions_generated?: number;
  predictions_skipped?: number;
  odds_synced?: number;
  errors_encountered?: number;
  warnings?: Array<{ step: string; message: string }>;
  error_message?: string;
  triggered_by?: string;
}

interface DataReadiness {
  season_year: number;
  week: number;
  season_type: string;
  schedule_complete: boolean;
  game_logs_available: boolean;
  predictions_available: boolean;
  draftkings_odds_available: boolean;
  games_count: number;
  game_logs_count: number;
  predictions_count: number;
  draftkings_odds_count: number;
  last_updated?: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? '';

function StatusBadge({ status }: { status: string }) {
  const colorMap: Record<string, string> = {
    success: 'bg-sr-success/15 text-sr-success border-sr-success/30',
    partial: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
    failed: 'bg-sr-danger/15 text-sr-danger border-sr-danger/30',
    running: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  };
  const cls = colorMap[status] ?? 'bg-sr-surface text-sr-text-muted border-sr-border';
  return (
    <span className={`px-2 py-0.5 rounded-badge border text-xs font-semibold ${cls}`}>
      {status.toUpperCase()}
    </span>
  );
}

function DataIndicator({
  label,
  available,
  count,
}: {
  label: string;
  available: boolean;
  count: number;
}) {
  return (
    <div className="bg-sr-surface/40 border border-sr-border rounded-xl p-3">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-sr-text-muted">{label}</span>
        <span
          className={`w-2 h-2 rounded-full ${available ? 'bg-sr-success' : 'bg-sr-text-dim'}`}
        />
      </div>
      <span className="text-base font-semibold text-white nums">{count}</span>
    </div>
  );
}

function InfoRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-sr-text-muted">{label}</span>
      {children}
    </div>
  );
}

export default function OverviewTab() {
  const [latestBatch, setLatestBatch] = useState<BatchRun | null>(null);
  const [dataReadiness, setDataReadiness] = useState<DataReadiness | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentWeek, setCurrentWeek] = useState<{
    year: number;
    week: number;
    season_type: string;
  } | null>(null);

  const formatDuration = (seconds?: number) => {
    if (!seconds) return 'N/A';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
  };

  const formatDateTime = (isoString?: string) => {
    if (!isoString) return 'N/A';
    return new Date(isoString).toLocaleString();
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
    async function loadOverviewData() {
      try {
        setLoading(true);
        const [batchRes, readinessRes] = await Promise.all([
          fetch(`${API_URL}/api/admin/batch-runs/latest`),
          fetch(`${API_URL}/api/admin/data-readiness/current`),
        ]);
        if (batchRes.ok) {
          const batchData = await batchRes.json();
          setLatestBatch(batchData.batch_run);
        }
        if (readinessRes.ok) {
          const readinessData = await readinessRes.json();
          setDataReadiness(readinessData.data_readiness);
          setCurrentWeek(readinessData.current_week);
        }
      } catch {
        // silent
      } finally {
        setLoading(false);
      }
    }
    loadOverviewData();
    const interval = setInterval(loadOverviewData, 30000);
    return () => clearInterval(interval);
  }, []);

  const isHealthy =
    dataReadiness?.schedule_complete &&
    dataReadiness?.predictions_available &&
    dataReadiness?.draftkings_odds_available;

  if (loading) {
    return (
      <div className="py-8 text-center">
        <Progress value={undefined} className="mb-4 w-full" />
        <p className="text-sr-text-muted text-sm">Loading overview data...</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Current Week Status Card */}
      <SurfaceCard className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-medium text-white">
              {currentWeek && `${currentWeek.year} Week ${currentWeek.week}`}
              {currentWeek?.season_type === 'post' && (
                <span className="ml-2 px-2 py-0.5 bg-yellow-500 text-black text-xs font-semibold rounded-badge">
                  Playoffs
                </span>
              )}
            </h3>
            <p className="text-sm text-sr-text-muted mt-0.5">Current NFL Week</p>
          </div>
          {isHealthy && (
            <span className="px-3 py-1 bg-sr-success/15 text-sr-success text-xs font-semibold rounded-badge border border-sr-success/30">
              READY
            </span>
          )}
        </div>

        {dataReadiness ? (
          <>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              <DataIndicator
                label="Schedule"
                available={dataReadiness.schedule_complete}
                count={dataReadiness.games_count}
              />
              <DataIndicator
                label="Prior Week Logs"
                available={dataReadiness.game_logs_available}
                count={dataReadiness.game_logs_count}
              />
              <DataIndicator
                label="Predictions"
                available={dataReadiness.predictions_available}
                count={dataReadiness.predictions_count}
              />
              <DataIndicator
                label="DraftKings"
                available={dataReadiness.draftkings_odds_available}
                count={dataReadiness.draftkings_odds_count}
              />
            </div>
            {dataReadiness.last_updated && (
              <p className="text-xs text-sr-text-dim mt-4">
                Last updated: {getTimeAgo(dataReadiness.last_updated)}
              </p>
            )}
          </>
        ) : (
          <p className="text-sr-text-muted text-sm">No data readiness information available</p>
        )}
      </SurfaceCard>

      {/* Latest Batch Run */}
      {latestBatch && (
        <SurfaceCard className="p-6">
          <p className="text-sm font-medium text-white mb-4">Latest Batch Run</p>
          <div className="flex flex-col gap-3">
            <InfoRow label="Status">
              <StatusBadge status={latestBatch.status} />
            </InfoRow>
            <InfoRow label="Type">
              <span className="text-sm text-white">{latestBatch.batch_type.replace('_', ' ')}</span>
            </InfoRow>
            {latestBatch.batch_mode && (
              <InfoRow label="Mode">
                <span className="text-sm text-white">{latestBatch.batch_mode}</span>
              </InfoRow>
            )}
            <InfoRow label="Week">
              <span className="text-sm text-white nums">
                {latestBatch.season_year} Week {latestBatch.week}
              </span>
            </InfoRow>
            <InfoRow label="Started">
              <span className="text-sm text-white">{formatDateTime(latestBatch.started_at)}</span>
            </InfoRow>
            <InfoRow label="Duration">
              <span className="text-sm text-white nums">
                {formatDuration(latestBatch.duration_seconds)}
              </span>
            </InfoRow>

            {(latestBatch.games_processed || latestBatch.predictions_generated) && (
              <div className="border-t border-sr-border pt-3 mt-1">
                <div className="flex gap-4 flex-wrap text-sm">
                  {latestBatch.games_processed != null && latestBatch.games_processed > 0 && (
                    <span>
                      <span className="text-sr-text-muted text-xs">Games </span>
                      <span className="text-white font-medium nums">{latestBatch.games_processed}</span>
                    </span>
                  )}
                  {latestBatch.game_logs_added != null && latestBatch.game_logs_added > 0 && (
                    <span>
                      <span className="text-sr-text-muted text-xs">Logs </span>
                      <span className="text-white font-medium nums">{latestBatch.game_logs_added}</span>
                    </span>
                  )}
                  {latestBatch.predictions_generated != null && latestBatch.predictions_generated > 0 && (
                    <span>
                      <span className="text-sr-text-muted text-xs">Predictions </span>
                      <span className="text-white font-medium nums">{latestBatch.predictions_generated}</span>
                    </span>
                  )}
                  {latestBatch.odds_synced != null && latestBatch.odds_synced > 0 && (
                    <span>
                      <span className="text-sr-text-muted text-xs">Odds </span>
                      <span className="text-white font-medium nums">{latestBatch.odds_synced}</span>
                    </span>
                  )}
                </div>
              </div>
            )}

            {latestBatch.warnings && latestBatch.warnings.length > 0 && (
              <div className="border-t border-sr-border pt-3 mt-1">
                <p className="text-xs font-medium text-yellow-400 mb-2">Warnings</p>
                {latestBatch.warnings.map((w, idx) => (
                  <p key={idx} className="text-xs text-sr-text-muted mb-1">
                    <span className="text-sr-text-dim">[{w.step}]</span> {w.message}
                  </p>
                ))}
              </div>
            )}

            {latestBatch.error_message && (
              <div className="border-t border-sr-border pt-3 mt-1">
                <p className="text-xs font-medium text-sr-danger mb-1">Error</p>
                <p className="text-xs text-sr-text-muted">{latestBatch.error_message}</p>
              </div>
            )}
          </div>
        </SurfaceCard>
      )}
    </div>
  );
}
