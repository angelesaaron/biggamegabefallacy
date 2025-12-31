'use client';

import { useEffect, useState } from 'react';
import { CheckCircle, XCircle, AlertCircle, Clock, Database, TrendingUp } from 'lucide-react';
import {
  Box,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Alert as MuiAlert,
  CircularProgress
} from '@mui/material';

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

export default function SystemStatus() {
  const [latestBatch, setLatestBatch] = useState<BatchRun | null>(null);
  const [dataReadiness, setDataReadiness] = useState<DataReadiness | null>(null);
  const [batchHistory, setBatchHistory] = useState<BatchRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentWeek, setCurrentWeek] = useState<{ year: number; week: number; season_type: string } | null>(null);

  // Admin action state
  const [showPasswordDialog, setShowPasswordDialog] = useState(false);
  const [currentAction, setCurrentAction] = useState<'refresh-rosters' | 'backfill-odds' | 'batch-update' | null>(null);
  const [password, setPassword] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  useEffect(() => {
    loadSystemStatus();
    // Auto-refresh every 30 seconds
    const interval = setInterval(loadSystemStatus, 30000);
    return () => clearInterval(interval);
  }, [API_URL]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'partial':
        return <AlertCircle className="w-5 h-5 text-yellow-500" />;
      case 'failed':
        return <XCircle className="w-5 h-5 text-red-500" />;
      case 'running':
        return <Clock className="w-5 h-5 text-blue-500 animate-spin" />;
      default:
        return <AlertCircle className="w-5 h-5 text-gray-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success':
        return 'text-green-500';
      case 'partial':
        return 'text-yellow-500';
      case 'failed':
        return 'text-red-500';
      case 'running':
        return 'text-blue-500';
      default:
        return 'text-gray-500';
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

  const handleActionClick = (action: 'refresh-rosters' | 'backfill-odds' | 'batch-update') => {
    setCurrentAction(action);
    setPassword('');
    setActionError(null);
    setActionSuccess(null);
    setShowPasswordDialog(true);
  };

  const handlePasswordDialogClose = () => {
    setShowPasswordDialog(false);
    setPassword('');
    setActionError(null);
  };

  const handleExecuteAction = async () => {
    if (!currentAction || !password) return;

    setActionLoading(true);
    setActionError(null);

    try {
      const endpoint = `/api/admin/actions/${currentAction}`;
      const response = await fetch(`${API_URL}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ password }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Action failed');
      }

      const result = await response.json();
      setActionSuccess(result.message);
      setShowPasswordDialog(false);
      setPassword('');

      // Reload system status after a short delay
      setTimeout(() => {
        loadSystemStatus();
      }, 2000);
    } catch (err: any) {
      setActionError(err.message || 'Failed to execute action');
    } finally {
      setActionLoading(false);
    }
  };

  const loadSystemStatus = async () => {
    try {
      setLoading(true);

      // Fetch latest batch run
      const batchRes = await fetch(`${API_URL}/api/admin/batch-runs/latest`);
      const batchData = await batchRes.json();
      setLatestBatch(batchData.batch_run);

      // Fetch current week data readiness
      const readinessRes = await fetch(`${API_URL}/api/admin/data-readiness/current`);
      const readinessData = await readinessRes.json();
      setDataReadiness(readinessData.data_readiness);
      setCurrentWeek(readinessData.current_week);

      // Fetch batch history
      const historyRes = await fetch(`${API_URL}/api/admin/batch-runs/history?limit=5`);
      const historyData = await historyRes.json();
      setBatchHistory(historyData.batch_runs || []);
    } catch (err) {
      console.error('Failed to load system status:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="text-white text-xl">Loading system status...</div>
      </div>
    );
  }

  // Calculate overall health
  const isHealthy =
    dataReadiness?.schedule_complete &&
    dataReadiness?.predictions_available &&
    (dataReadiness?.draftkings_odds_available || dataReadiness?.fanduel_odds_available);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h2 className="text-3xl text-white mb-2">System Status</h2>
        <p className="text-gray-400">Data readiness and batch execution monitoring</p>
      </div>

      {/* Admin Actions - Always visible at top */}
      <div className="bg-gray-900/40 backdrop-blur-sm border border-gray-800 rounded-xl p-6 mb-6">
        <h3 className="text-lg font-semibold mb-4">Admin Actions</h3>

        {actionSuccess && (
          <MuiAlert severity="success" sx={{ mb: 2 }} onClose={() => setActionSuccess(null)}>
            {actionSuccess}
          </MuiAlert>
        )}

        <Box sx={{ display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 2 }}>
          <Button
            variant="contained"
            onClick={() => handleActionClick('refresh-rosters')}
            sx={{
              bgcolor: '#9333ea',
              '&:hover': { bgcolor: '#7e22ce' },
              textTransform: 'none',
              flex: 1
            }}
          >
            Refresh Rosters
          </Button>
          <Button
            variant="contained"
            onClick={() => handleActionClick('backfill-odds')}
            sx={{
              bgcolor: '#9333ea',
              '&:hover': { bgcolor: '#7e22ce' },
              textTransform: 'none',
              flex: 1
            }}
          >
            Backfill Historical Odds
          </Button>
          <Button
            variant="contained"
            onClick={() => handleActionClick('batch-update')}
            sx={{
              bgcolor: '#9333ea',
              '&:hover': { bgcolor: '#7e22ce' },
              textTransform: 'none',
              flex: 1
            }}
          >
            Run Batch Update
          </Button>
        </Box>
      </div>

      {/* Current Week Status Card */}
      <div className="bg-gray-900/40 backdrop-blur-sm border border-gray-800 rounded-xl p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-xl font-semibold">
              {currentWeek && `${currentWeek.year} Week ${currentWeek.week}`}
              {currentWeek?.season_type === 'post' && <span className="text-yellow-500 ml-2">(Playoffs)</span>}
            </h3>
            <p className="text-sm text-gray-400">Current NFL Week</p>
          </div>
          <div className="text-right">
            {isHealthy ? (
              <div className="flex items-center gap-2 text-green-500">
                <CheckCircle className="w-6 h-6" />
                <span className="font-semibold">READY</span>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-yellow-500">
                <AlertCircle className="w-6 h-6" />
                <span className="font-semibold">PARTIAL</span>
              </div>
            )}
          </div>
        </div>

        {dataReadiness ? (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <DataIndicator
              label="Schedule"
              available={dataReadiness.schedule_complete}
              count={dataReadiness.games_count}
            />
            <DataIndicator
              label="Game Logs"
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
            <DataIndicator
              label="FanDuel"
              available={dataReadiness.fanduel_odds_available}
              count={dataReadiness.fanduel_odds_count}
            />
          </div>
        ) : (
          <p className="text-gray-400">No data readiness information available</p>
        )}

        {dataReadiness?.last_updated && (
          <p className="text-xs text-gray-500 mt-4">
            Last updated: {getTimeAgo(dataReadiness.last_updated)}
          </p>
        )}
      </div>

      {/* Latest Batch Run */}
      {latestBatch && (
        <div className="bg-gray-900/40 backdrop-blur-sm border border-gray-800 rounded-xl p-6 mb-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5" />
            Latest Batch Run
          </h3>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-gray-400">Status</span>
              <div className="flex items-center gap-2">
                {getStatusIcon(latestBatch.status)}
                <span className={`font-semibold ${getStatusColor(latestBatch.status)}`}>
                  {latestBatch.status.toUpperCase()}
                </span>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-gray-400">Type</span>
              <span className="text-white">{latestBatch.batch_type.replace('_', ' ')}</span>
            </div>

            {latestBatch.batch_mode && (
              <div className="flex items-center justify-between">
                <span className="text-gray-400">Mode</span>
                <span className="text-white">{latestBatch.batch_mode}</span>
              </div>
            )}

            <div className="flex items-center justify-between">
              <span className="text-gray-400">Week</span>
              <span className="text-white">
                {latestBatch.season_year} Week {latestBatch.week}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-gray-400">Started</span>
              <span className="text-white text-sm">{formatDateTime(latestBatch.started_at)}</span>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-gray-400">Duration</span>
              <span className="text-white">{formatDuration(latestBatch.duration_seconds)}</span>
            </div>

            {/* Metrics */}
            {(latestBatch.api_calls_made || latestBatch.games_processed || latestBatch.predictions_generated) && (
              <div className="border-t border-gray-700 pt-3 mt-3">
                <p className="text-sm text-gray-400 mb-2">Metrics</p>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  {latestBatch.api_calls_made && (
                    <div>
                      <span className="text-gray-400">API Calls:</span>{' '}
                      <span className="text-white">{latestBatch.api_calls_made}</span>
                    </div>
                  )}
                  {latestBatch.games_processed && (
                    <div>
                      <span className="text-gray-400">Games:</span>{' '}
                      <span className="text-white">{latestBatch.games_processed}</span>
                    </div>
                  )}
                  {latestBatch.game_logs_added && (
                    <div>
                      <span className="text-gray-400">Logs Added:</span>{' '}
                      <span className="text-white">{latestBatch.game_logs_added}</span>
                    </div>
                  )}
                  {latestBatch.predictions_generated && (
                    <div>
                      <span className="text-gray-400">Predictions:</span>{' '}
                      <span className="text-white">{latestBatch.predictions_generated}</span>
                    </div>
                  )}
                  {latestBatch.predictions_skipped && (
                    <div>
                      <span className="text-gray-400">Skipped:</span>{' '}
                      <span className="text-white">{latestBatch.predictions_skipped}</span>
                    </div>
                  )}
                  {latestBatch.odds_synced && (
                    <div>
                      <span className="text-gray-400">Odds:</span>{' '}
                      <span className="text-white">{latestBatch.odds_synced}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Warnings */}
            {latestBatch.warnings && latestBatch.warnings.length > 0 && (
              <div className="border-t border-gray-700 pt-3 mt-3">
                <p className="text-sm text-yellow-500 mb-2 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4" />
                  Warnings
                </p>
                {latestBatch.warnings.map((warning, idx) => (
                  <div key={idx} className="text-sm text-gray-400 mb-1">
                    <span className="text-gray-500">[{warning.step}]</span> {warning.message}
                  </div>
                ))}
              </div>
            )}

            {/* Error */}
            {latestBatch.error_message && (
              <div className="border-t border-gray-700 pt-3 mt-3">
                <p className="text-sm text-red-500 mb-2 flex items-center gap-2">
                  <XCircle className="w-4 h-4" />
                  Error
                </p>
                <p className="text-sm text-gray-400">{latestBatch.error_message}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Batch History */}
      {batchHistory.length > 0 && (
        <div className="bg-gray-900/40 backdrop-blur-sm border border-gray-800 rounded-xl p-6 mb-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Database className="w-5 h-5" />
            Recent Batch History
          </h3>

          <div className="space-y-3">
            {batchHistory.map((batch) => (
              <div
                key={batch.id}
                className="flex items-center justify-between p-3 bg-gray-800/40 rounded-lg"
              >
                <div className="flex items-center gap-3">
                  {getStatusIcon(batch.status)}
                  <div>
                    <p className="text-white text-sm font-medium">
                      {batch.batch_type.replace('_', ' ')}
                      {batch.batch_mode && ` (${batch.batch_mode})`}
                    </p>
                    <p className="text-gray-400 text-xs">
                      {batch.season_year} Week {batch.week} • {getTimeAgo(batch.started_at)}
                    </p>
                  </div>
                </div>
                <div className="text-right text-xs text-gray-400">
                  {formatDuration(batch.duration_seconds)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Password Dialog */}
      <Dialog
        open={showPasswordDialog}
        onClose={handlePasswordDialogClose}
        PaperProps={{
          sx: {
            bgcolor: '#1f2937',
            color: 'white',
            border: '1px solid #374151'
          }
        }}
      >
        <DialogTitle>Admin Authentication Required</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            {actionError && (
              <MuiAlert severity="error" sx={{ mb: 2 }}>
                {actionError}
              </MuiAlert>
            )}
            <TextField
              autoFocus
              margin="dense"
              label="Admin Password"
              type="password"
              fullWidth
              variant="outlined"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter' && password) {
                  handleExecuteAction();
                }
              }}
              sx={{
                '& .MuiOutlinedInput-root': {
                  color: 'white',
                  '& fieldset': {
                    borderColor: '#374151',
                  },
                  '&:hover fieldset': {
                    borderColor: '#9333ea',
                  },
                  '&.Mui-focused fieldset': {
                    borderColor: '#9333ea',
                  },
                },
                '& .MuiInputLabel-root': {
                  color: '#9ca3af',
                  '&.Mui-focused': {
                    color: '#9333ea',
                  },
                },
              }}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handlePasswordDialogClose} sx={{ color: '#9ca3af' }}>
            Cancel
          </Button>
          <Button
            onClick={handleExecuteAction}
            disabled={!password || actionLoading}
            sx={{
              color: '#9333ea',
              '&:hover': { bgcolor: 'rgba(147, 51, 234, 0.1)' }
            }}
          >
            {actionLoading ? <CircularProgress size={20} sx={{ color: '#9333ea' }} /> : 'Execute'}
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  );
}

function DataIndicator({ label, available, count }: { label: string; available: boolean; count: number }) {
  return (
    <div className="bg-gray-800/40 rounded-lg p-3">
      <div className="flex items-center gap-2 mb-1">
        {available ? (
          <CheckCircle className="w-4 h-4 text-green-500" />
        ) : (
          <XCircle className="w-4 h-4 text-gray-600" />
        )}
        <span className="text-xs text-gray-400">{label}</span>
      </div>
      <p className="text-lg font-semibold text-white">{count}</p>
    </div>
  );
}
