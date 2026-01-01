'use client';

import { useEffect, useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  LinearProgress,
  Chip,
} from '@mui/material';
import {
  CheckCircle,
  Cancel,
  Warning,
  Schedule,
  TrendingUp,
} from '@mui/icons-material';

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
  fanduel_odds_available: boolean;
  games_count: number;
  game_logs_count: number;
  predictions_count: number;
  draftkings_odds_count: number;
  fanduel_odds_count: number;
  last_updated?: string;
}

export default function OverviewTab() {
  const [latestBatch, setLatestBatch] = useState<BatchRun | null>(null);
  const [dataReadiness, setDataReadiness] = useState<DataReadiness | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentWeek, setCurrentWeek] = useState<{ year: number; week: number; season_type: string } | null>(null);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  useEffect(() => {
    async function loadOverviewData() {
      try {
        setLoading(true);

        const batchRes = await fetch(`${API_URL}/api/admin/batch-runs/latest`);
        if (!batchRes.ok) {
          throw new Error(`Batch API failed: ${batchRes.status}`);
        }
        const batchData = await batchRes.json();
        setLatestBatch(batchData.batch_run);

        const readinessRes = await fetch(`${API_URL}/api/admin/data-readiness/current`);
        if (!readinessRes.ok) {
          throw new Error(`Readiness API failed: ${readinessRes.status}`);
        }
        const readinessData = await readinessRes.json();
        setDataReadiness(readinessData.data_readiness);
        setCurrentWeek(readinessData.current_week);
      } catch (err) {
        console.error('Failed to load overview data:', err);
      } finally {
        setLoading(false);
      }
    }

    loadOverviewData();
    const interval = setInterval(loadOverviewData, 30000);
    return () => clearInterval(interval);
  }, [API_URL]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success':
        return <CheckCircle sx={{ color: '#10b981', fontSize: 28 }} />;
      case 'partial':
        return <Warning sx={{ color: '#eab308', fontSize: 28 }} />;
      case 'failed':
        return <Cancel sx={{ color: '#ef4444', fontSize: 28 }} />;
      case 'running':
        return <Schedule sx={{ color: '#3b82f6', fontSize: 28 }} className="animate-spin" />;
      default:
        return <Warning sx={{ color: '#6b7280', fontSize: 28 }} />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success':
        return '#10b981';
      case 'partial':
        return '#eab308';
      case 'failed':
        return '#ef4444';
      case 'running':
        return '#3b82f6';
      default:
        return '#6b7280';
    }
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return 'N/A';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
  };

  const formatDateTime = (isoString?: string) => {
    if (!isoString) return 'N/A';
    const date = new Date(isoString);
    return date.toLocaleString();
  };

  const getTimeAgo = (isoString?: string) => {
    if (!isoString) return '';
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffDays > 0) return `${diffDays}d ago`;
    if (diffHours > 0) return `${diffHours}h ago`;
    if (diffMins > 0) return `${diffMins}m ago`;
    return 'Just now';
  };

  if (loading) {
    return (
      <Box sx={{ py: 8, textAlign: 'center' }}>
        <LinearProgress sx={{ mb: 2, bgcolor: '#1f2937', '& .MuiLinearProgress-bar': { bgcolor: '#9333ea' } }} />
        <Typography sx={{ color: '#9ca3af' }}>Loading overview data...</Typography>
      </Box>
    );
  }

  const isHealthy =
    dataReadiness?.schedule_complete &&
    dataReadiness?.predictions_available &&
    (dataReadiness?.draftkings_odds_available || dataReadiness?.fanduel_odds_available);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {/* Current Week Status Card */}
      <Card sx={{ bgcolor: 'rgba(17, 24, 39, 0.4)', backdropFilter: 'blur(8px)', border: '1px solid #1f2937', borderRadius: 3 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2.5 }}>
            <Box>
              <Typography variant="h5" sx={{ color: 'white', fontWeight: 500 }}>
                {currentWeek && `${currentWeek.year} Week ${currentWeek.week}`}
                {currentWeek?.season_type === 'post' && (
                  <Chip
                    label="Playoffs"
                    size="small"
                    sx={{ ml: 1.5, bgcolor: '#eab308', color: '#000', fontWeight: 600, height: 24 }}
                  />
                )}
              </Typography>
              <Typography variant="body2" sx={{ color: '#9ca3af', mt: 0.25, fontSize: '0.875rem' }}>
                Current NFL Week
              </Typography>
            </Box>
            <Box sx={{ textAlign: 'right' }}>
              {isHealthy && (
                <Chip
                  label="READY"
                  sx={{
                    bgcolor: 'rgba(16, 185, 129, 0.15)',
                    color: '#10b981',
                    fontWeight: 600,
                    fontSize: '0.75rem',
                    border: '1px solid rgba(16, 185, 129, 0.3)'
                  }}
                />
              )}
            </Box>
          </Box>

          {dataReadiness ? (
            <>
              <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                <Box sx={{ flex: '1 1 calc(50% - 8px)', minWidth: '200px' }}>
                  <DataIndicator
                    label="Schedule"
                    available={dataReadiness.schedule_complete}
                    count={dataReadiness.games_count}
                  />
                </Box>
                <Box sx={{ flex: '1 1 calc(50% - 8px)', minWidth: '200px' }}>
                  <DataIndicator
                    label="Prior Week Logs"
                    available={dataReadiness.game_logs_available}
                    count={dataReadiness.game_logs_count}
                  />
                </Box>
                <Box sx={{ flex: '1 1 calc(50% - 8px)', minWidth: '200px' }}>
                  <DataIndicator
                    label="Predictions"
                    available={dataReadiness.predictions_available}
                    count={dataReadiness.predictions_count}
                  />
                </Box>
                <Box sx={{ flex: '1 1 calc(50% - 8px)', minWidth: '200px' }}>
                  <DataIndicator
                    label="DraftKings"
                    available={dataReadiness.draftkings_odds_available}
                    count={dataReadiness.draftkings_odds_count}
                  />
                </Box>
                <Box sx={{ flex: '1 1 calc(50% - 8px)', minWidth: '200px' }}>
                  <DataIndicator
                    label="FanDuel"
                    available={dataReadiness.fanduel_odds_available}
                    count={dataReadiness.fanduel_odds_count}
                  />
                </Box>
              </Box>

              {dataReadiness.last_updated && (
                <Typography variant="caption" sx={{ color: '#6b7280', mt: 2, display: 'block' }}>
                  Last updated: {getTimeAgo(dataReadiness.last_updated)}
                </Typography>
              )}
            </>
          ) : (
            <Typography sx={{ color: '#9ca3af' }}>No data readiness information available</Typography>
          )}
        </CardContent>
      </Card>

      {/* Latest Batch Run */}
      {latestBatch && (
        <Card sx={{ bgcolor: 'rgba(17, 24, 39, 0.4)', backdropFilter: 'blur(8px)', border: '1px solid #1f2937', borderRadius: 3 }}>
          <CardContent>
            <Typography variant="body1" sx={{ color: 'white', fontWeight: 500, mb: 2 }}>
              Latest Batch Run
            </Typography>

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              <InfoRow label="Status">
                <Chip
                  label={latestBatch.status.toUpperCase()}
                  size="small"
                  sx={{
                    bgcolor: `${getStatusColor(latestBatch.status)}20`,
                    color: getStatusColor(latestBatch.status),
                    fontWeight: 600,
                    fontSize: '0.75rem',
                    border: `1px solid ${getStatusColor(latestBatch.status)}40`
                  }}
                />
              </InfoRow>

              <InfoRow label="Type">
                <Typography sx={{ color: 'white', fontSize: '0.875rem' }}>
                  {latestBatch.batch_type.replace('_', ' ')}
                </Typography>
              </InfoRow>

              {latestBatch.batch_mode && (
                <InfoRow label="Mode">
                  <Typography sx={{ color: 'white', fontSize: '0.875rem' }}>{latestBatch.batch_mode}</Typography>
                </InfoRow>
              )}

              <InfoRow label="Week">
                <Typography sx={{ color: 'white', fontSize: '0.875rem' }}>
                  {latestBatch.season_year} Week {latestBatch.week}
                </Typography>
              </InfoRow>

              <InfoRow label="Started">
                <Typography sx={{ color: 'white', fontSize: '0.875rem' }}>
                  {formatDateTime(latestBatch.started_at)}
                </Typography>
              </InfoRow>

              <InfoRow label="Duration">
                <Typography sx={{ color: 'white', fontSize: '0.875rem' }}>{formatDuration(latestBatch.duration_seconds)}</Typography>
              </InfoRow>

              {/* Metrics */}
              {(latestBatch.games_processed || latestBatch.predictions_generated) && (
                <Box sx={{ borderTop: '1px solid #374151', pt: 1.5, mt: 0.5 }}>
                  <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap', fontSize: '0.875rem' }}>
                    {latestBatch.games_processed !== undefined && latestBatch.games_processed > 0 && (
                      <Box>
                        <Typography component="span" sx={{ color: '#9ca3af', fontSize: '0.75rem' }}>Games </Typography>
                        <Typography component="span" sx={{ color: 'white', fontWeight: 500 }}>{latestBatch.games_processed}</Typography>
                      </Box>
                    )}
                    {latestBatch.game_logs_added !== undefined && latestBatch.game_logs_added > 0 && (
                      <Box>
                        <Typography component="span" sx={{ color: '#9ca3af', fontSize: '0.75rem' }}>Logs </Typography>
                        <Typography component="span" sx={{ color: 'white', fontWeight: 500 }}>{latestBatch.game_logs_added}</Typography>
                      </Box>
                    )}
                    {latestBatch.predictions_generated !== undefined && latestBatch.predictions_generated > 0 && (
                      <Box>
                        <Typography component="span" sx={{ color: '#9ca3af', fontSize: '0.75rem' }}>Predictions </Typography>
                        <Typography component="span" sx={{ color: 'white', fontWeight: 500 }}>{latestBatch.predictions_generated}</Typography>
                      </Box>
                    )}
                    {latestBatch.odds_synced !== undefined && latestBatch.odds_synced > 0 && (
                      <Box>
                        <Typography component="span" sx={{ color: '#9ca3af', fontSize: '0.75rem' }}>Odds </Typography>
                        <Typography component="span" sx={{ color: 'white', fontWeight: 500 }}>{latestBatch.odds_synced}</Typography>
                      </Box>
                    )}
                  </Box>
                </Box>
              )}

              {/* Warnings */}
              {latestBatch.warnings && latestBatch.warnings.length > 0 && (
                <Box sx={{ borderTop: '1px solid #374151', pt: 1.5, mt: 0.5 }}>
                  <Typography variant="caption" sx={{ color: '#eab308', fontWeight: 500, display: 'block', mb: 1 }}>
                    Warnings
                  </Typography>
                  {latestBatch.warnings.map((warning, idx) => (
                    <Typography key={idx} variant="caption" sx={{ color: '#9ca3af', mb: 0.5, display: 'block', fontSize: '0.75rem' }}>
                      <Typography component="span" sx={{ color: '#6b7280' }}>
                        [{warning.step}]
                      </Typography>{' '}
                      {warning.message}
                    </Typography>
                  ))}
                </Box>
              )}

              {/* Error */}
              {latestBatch.error_message && (
                <Box sx={{ borderTop: '1px solid #374151', pt: 1.5, mt: 0.5 }}>
                  <Typography variant="caption" sx={{ color: '#ef4444', fontWeight: 500, display: 'block', mb: 1 }}>
                    Error
                  </Typography>
                  <Typography variant="caption" sx={{ color: '#9ca3af', fontSize: '0.75rem' }}>
                    {latestBatch.error_message}
                  </Typography>
                </Box>
              )}
            </Box>
          </CardContent>
        </Card>
      )}
    </Box>
  );
}

function DataIndicator({ label, available, count, subtitle }: { label: string; available: boolean; count: number; subtitle?: string }) {
  return (
    <Card sx={{ bgcolor: 'rgba(31, 41, 55, 0.4)', border: '1px solid #374151', borderRadius: 2 }}>
      <CardContent sx={{ p: 1.75, '&:last-child': { pb: 1.75 } }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.75 }}>
          <Typography variant="caption" sx={{ color: '#9ca3af', fontSize: '0.75rem' }}>
            {label}
          </Typography>
          <Box
            sx={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              bgcolor: available ? '#10b981' : '#4b5563'
            }}
          />
        </Box>
        <Typography variant="h6" sx={{ color: 'white', fontWeight: 600 }}>
          {count}
        </Typography>
      </CardContent>
    </Card>
  );
}

function InfoRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <Typography sx={{ color: '#9ca3af', fontSize: '0.875rem' }}>{label}</Typography>
      {children}
    </Box>
  );
}
