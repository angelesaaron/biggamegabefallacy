'use client';

import { useEffect, useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
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
      <Card sx={{ bgcolor: 'rgba(17, 24, 39, 0.4)', backdropFilter: 'blur(8px)', border: '1px solid #1f2937' }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
            <Box>
              <Typography variant="h4" sx={{ color: 'white', fontWeight: 600 }}>
                {currentWeek && `${currentWeek.year} Week ${currentWeek.week}`}
                {currentWeek?.season_type === 'post' && (
                  <Chip
                    label="Playoffs"
                    size="small"
                    sx={{ ml: 2, bgcolor: '#eab308', color: '#000', fontWeight: 600 }}
                  />
                )}
              </Typography>
              <Typography variant="body2" sx={{ color: '#9ca3af', mt: 0.5 }}>
                Current NFL Week
              </Typography>
            </Box>
            <Box sx={{ textAlign: 'right' }}>
              {isHealthy ? (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, color: '#10b981' }}>
                  <CheckCircle sx={{ fontSize: 32 }} />
                  <Typography variant="h5" sx={{ fontWeight: 700 }}>
                    READY
                  </Typography>
                </Box>
              ) : (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, color: '#eab308' }}>
                  <Warning sx={{ fontSize: 32 }} />
                  <Typography variant="h5" sx={{ fontWeight: 700 }}>
                    PARTIAL
                  </Typography>
                </Box>
              )}
            </Box>
          </Box>

          {dataReadiness ? (
            <>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6} md={2.4}>
                  <DataIndicator
                    label="Schedule"
                    available={dataReadiness.schedule_complete}
                    count={dataReadiness.games_count}
                  />
                </Grid>
                <Grid item xs={12} sm={6} md={2.4}>
                  <DataIndicator
                    label="Prior Week Logs"
                    available={dataReadiness.game_logs_available}
                    count={dataReadiness.game_logs_count}
                  />
                </Grid>
                <Grid item xs={12} sm={6} md={2.4}>
                  <DataIndicator
                    label="Predictions"
                    available={dataReadiness.predictions_available}
                    count={dataReadiness.predictions_count}
                  />
                </Grid>
                <Grid item xs={12} sm={6} md={2.4}>
                  <DataIndicator
                    label="DraftKings"
                    available={dataReadiness.draftkings_odds_available}
                    count={dataReadiness.draftkings_odds_count}
                  />
                </Grid>
                <Grid item xs={12} sm={6} md={2.4}>
                  <DataIndicator
                    label="FanDuel"
                    available={dataReadiness.fanduel_odds_available}
                    count={dataReadiness.fanduel_odds_count}
                  />
                </Grid>
              </Grid>

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
        <Card sx={{ bgcolor: 'rgba(17, 24, 39, 0.4)', backdropFilter: 'blur(8px)', border: '1px solid #1f2937' }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3 }}>
              <TrendingUp sx={{ color: '#9333ea' }} />
              <Typography variant="h6" sx={{ color: 'white', fontWeight: 600 }}>
                Latest Batch Run
              </Typography>
            </Box>

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <InfoRow label="Status">
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                  {getStatusIcon(latestBatch.status)}
                  <Typography sx={{ color: getStatusColor(latestBatch.status), fontWeight: 600 }}>
                    {latestBatch.status.toUpperCase()}
                  </Typography>
                </Box>
              </InfoRow>

              <InfoRow label="Type">
                <Typography sx={{ color: 'white' }}>
                  {latestBatch.batch_type.replace('_', ' ')}
                </Typography>
              </InfoRow>

              {latestBatch.batch_mode && (
                <InfoRow label="Mode">
                  <Typography sx={{ color: 'white' }}>{latestBatch.batch_mode}</Typography>
                </InfoRow>
              )}

              <InfoRow label="Week">
                <Typography sx={{ color: 'white' }}>
                  {latestBatch.season_year} Week {latestBatch.week}
                </Typography>
              </InfoRow>

              <InfoRow label="Started">
                <Typography sx={{ color: 'white', fontSize: '0.875rem' }}>
                  {formatDateTime(latestBatch.started_at)}
                </Typography>
              </InfoRow>

              <InfoRow label="Duration">
                <Typography sx={{ color: 'white' }}>{formatDuration(latestBatch.duration_seconds)}</Typography>
              </InfoRow>

              {/* Metrics */}
              {(latestBatch.games_processed || latestBatch.predictions_generated) && (
                <Box sx={{ borderTop: '1px solid #374151', pt: 2, mt: 1 }}>
                  <Typography variant="body2" sx={{ color: '#9ca3af', mb: 1.5 }}>
                    Metrics
                  </Typography>
                  <Grid container spacing={2} sx={{ fontSize: '0.875rem' }}>
                    {latestBatch.games_processed && (
                      <Grid item xs={6}>
                        <Typography component="span" sx={{ color: '#9ca3af' }}>Games: </Typography>
                        <Typography component="span" sx={{ color: 'white' }}>{latestBatch.games_processed}</Typography>
                      </Grid>
                    )}
                    {latestBatch.game_logs_added && (
                      <Grid item xs={6}>
                        <Typography component="span" sx={{ color: '#9ca3af' }}>Logs Added: </Typography>
                        <Typography component="span" sx={{ color: 'white' }}>{latestBatch.game_logs_added}</Typography>
                      </Grid>
                    )}
                    {latestBatch.predictions_generated && (
                      <Grid item xs={6}>
                        <Typography component="span" sx={{ color: '#9ca3af' }}>Predictions: </Typography>
                        <Typography component="span" sx={{ color: 'white' }}>{latestBatch.predictions_generated}</Typography>
                      </Grid>
                    )}
                    {latestBatch.odds_synced && (
                      <Grid item xs={6}>
                        <Typography component="span" sx={{ color: '#9ca3af' }}>Odds: </Typography>
                        <Typography component="span" sx={{ color: 'white' }}>{latestBatch.odds_synced}</Typography>
                      </Grid>
                    )}
                  </Grid>
                </Box>
              )}

              {/* Warnings */}
              {latestBatch.warnings && latestBatch.warnings.length > 0 && (
                <Box sx={{ borderTop: '1px solid #374151', pt: 2, mt: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
                    <Warning sx={{ color: '#eab308', fontSize: 18 }} />
                    <Typography variant="body2" sx={{ color: '#eab308', fontWeight: 500 }}>
                      Warnings
                    </Typography>
                  </Box>
                  {latestBatch.warnings.map((warning, idx) => (
                    <Typography key={idx} variant="body2" sx={{ color: '#9ca3af', mb: 0.5 }}>
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
                <Box sx={{ borderTop: '1px solid #374151', pt: 2, mt: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
                    <Cancel sx={{ color: '#ef4444', fontSize: 18 }} />
                    <Typography variant="body2" sx={{ color: '#ef4444', fontWeight: 500 }}>
                      Error
                    </Typography>
                  </Box>
                  <Typography variant="body2" sx={{ color: '#9ca3af' }}>
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
    <Card sx={{ bgcolor: 'rgba(31, 41, 55, 0.4)', border: '1px solid #374151' }}>
      <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          {available ? (
            <CheckCircle sx={{ color: '#10b981', fontSize: 16 }} />
          ) : (
            <Cancel sx={{ color: '#4b5563', fontSize: 16 }} />
          )}
          <Box sx={{ flex: 1 }}>
            <Typography variant="caption" sx={{ color: '#9ca3af', display: 'block' }}>
              {label}
            </Typography>
            {subtitle && (
              <Typography variant="caption" sx={{ color: '#6b7280', fontSize: '0.65rem', fontStyle: 'italic' }}>
                {subtitle}
              </Typography>
            )}
          </Box>
        </Box>
        <Typography variant="h5" sx={{ color: 'white', fontWeight: 700 }}>
          {count}
        </Typography>
      </CardContent>
    </Card>
  );
}

function InfoRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <Typography sx={{ color: '#9ca3af' }}>{label}</Typography>
      {children}
    </Box>
  );
}
