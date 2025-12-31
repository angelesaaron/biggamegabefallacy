'use client';

import { useEffect, useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Chip,
  Typography,
  Collapse,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  ToggleButton,
  ToggleButtonGroup,
  LinearProgress,
  Button,
} from '@mui/material';
import {
  CheckCircle,
  Cancel,
  Warning,
  Schedule,
  ExpandMore as ExpandMoreIcon,
  Visibility as VisibilityIcon,
} from '@mui/icons-material';
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
  odds_synced?: number;
  triggered_by?: string;
  steps?: BatchStep[];
}

export default function BatchHistoryTab() {
  const [batchHistory, setBatchHistory] = useState<BatchRun[]>([]);
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  const [selectedLog, setSelectedLog] = useState<{ stepName: string; log: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  useEffect(() => {
    async function loadBatchHistory() {
      try {
        setLoading(true);
        const response = await fetch(`${API_URL}/api/admin/batch-runs/history?limit=50`);

        if (!response.ok) {
          throw new Error(`History API failed: ${response.status}`);
        }

        const data = await response.json();
        setBatchHistory(data.batch_runs || []);
      } catch (err) {
        console.error('Failed to load batch history:', err);
      } finally {
        setLoading(false);
      }
    }

    loadBatchHistory();
    const interval = setInterval(loadBatchHistory, 30000);
    return () => clearInterval(interval);
  }, [API_URL]);

  const toggleRow = async (batchId: number) => {
    const newExpanded = new Set(expandedRows);

    if (expandedRows.has(batchId)) {
      newExpanded.delete(batchId);
    } else {
      newExpanded.add(batchId);

      const batch = batchHistory.find((b) => b.id === batchId);
      if (batch && !batch.steps) {
        try {
          const response = await fetch(`${API_URL}/api/admin/batch-runs/${batchId}?include_steps=true`);
          const data = await response.json();

          setBatchHistory((prev) =>
            prev.map((b) => (b.id === batchId ? { ...b, steps: data.steps } : b))
          );
        } catch (err) {
          console.error('Failed to load batch steps:', err);
        }
      }
    }

    setExpandedRows(newExpanded);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success':
        return <CheckCircle sx={{ color: '#10b981' }} />;
      case 'partial':
        return <Warning sx={{ color: '#eab308' }} />;
      case 'failed':
        return <Cancel sx={{ color: '#ef4444' }} />;
      case 'running':
        return <Schedule sx={{ color: '#3b82f6' }} className="animate-spin" />;
      default:
        return <Warning sx={{ color: '#6b7280' }} />;
    }
  };

  const getStepStatusChip = (status: string) => {
    const statusConfig: Record<string, { label: string; color: any }> = {
      success: { label: '✓ Success', color: 'success' },
      failed: { label: '✗ Failed', color: 'error' },
      running: { label: '⏳ Running', color: 'info' },
      skipped: { label: '⊘ Skipped', color: 'default' },
      pending: { label: '⏸ Pending', color: 'default' },
    };

    const config = statusConfig[status] || statusConfig.pending;
    return <Chip label={config.label} color={config.color} size="small" />;
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

  const handleFilterChange = (_event: React.MouseEvent<HTMLElement>, newFilter: string | null) => {
    if (newFilter !== null) {
      setFilter(newFilter);
    }
  };

  const filteredHistory = batchHistory.filter((batch) => {
    if (filter === 'all') return true;
    return batch.status === filter;
  });

  if (loading) {
    return (
      <Box sx={{ py: 8, textAlign: 'center' }}>
        <LinearProgress sx={{ mb: 2, bgcolor: '#1f2937', '& .MuiLinearProgress-bar': { bgcolor: '#9333ea' } }} />
        <Typography sx={{ color: '#9ca3af' }}>Loading batch history...</Typography>
      </Box>
    );
  }

  return (
    <Box>
      {/* Filters */}
      <Card sx={{ mb: 3, bgcolor: 'rgba(17, 24, 39, 0.4)', backdropFilter: 'blur(8px)', border: '1px solid #1f2937' }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Typography variant="body2" sx={{ color: '#9ca3af' }}>
              Filter by status:
            </Typography>
            <ToggleButtonGroup
              value={filter}
              exclusive
              onChange={handleFilterChange}
              size="small"
              sx={{
                '& .MuiToggleButton-root': {
                  color: '#9ca3af',
                  borderColor: '#374151',
                  textTransform: 'capitalize',
                  px: 2,
                  py: 0.5,
                  '&.Mui-selected': {
                    bgcolor: '#9333ea',
                    color: 'white',
                    '&:hover': {
                      bgcolor: '#7e22ce',
                    }
                  },
                  '&:hover': {
                    bgcolor: '#374151',
                  }
                }
              }}
            >
              <ToggleButton value="all">All</ToggleButton>
              <ToggleButton value="success">Success</ToggleButton>
              <ToggleButton value="partial">Partial</ToggleButton>
              <ToggleButton value="failed">Failed</ToggleButton>
              <ToggleButton value="running">Running</ToggleButton>
            </ToggleButtonGroup>
          </Box>
        </CardContent>
      </Card>

      {/* Action History */}
      <Card sx={{ bgcolor: 'rgba(17, 24, 39, 0.4)', backdropFilter: 'blur(8px)', border: '1px solid #1f2937' }}>
        {filteredHistory.length === 0 ? (
          <CardContent>
            <Typography sx={{ color: '#9ca3af', textAlign: 'center', py: 4 }}>
              No actions found for the selected filter.
            </Typography>
          </CardContent>
        ) : (
          <Box>
            {filteredHistory.map((batch) => (
              <Box key={batch.id} sx={{ borderBottom: '1px solid #1f2937', '&:last-child': { borderBottom: 'none' } }}>
                {/* Main Row */}
                <Box
                  onClick={() => toggleRow(batch.id)}
                  sx={{
                    p: 2,
                    cursor: 'pointer',
                    transition: 'background-color 0.2s',
                    '&:hover': {
                      bgcolor: 'rgba(55, 65, 81, 0.4)',
                    }
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flex: 1 }}>
                      {getStatusIcon(batch.status)}

                      <Box sx={{ flex: 1 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 0.5 }}>
                          <Typography variant="body1" sx={{ color: 'white', fontWeight: 500 }}>
                            {batch.batch_type.replace('_', ' ').toUpperCase()}
                          </Typography>
                          {batch.batch_mode && (
                            <Chip
                              label={batch.batch_mode}
                              size="small"
                              sx={{ bgcolor: '#374151', color: '#d1d5db', height: 20, fontSize: '0.7rem' }}
                            />
                          )}
                        </Box>
                        <Typography variant="body2" sx={{ color: '#9ca3af' }}>
                          {batch.season_year} Week {batch.week} • {getTimeAgo(batch.started_at)}
                        </Typography>
                      </Box>
                    </Box>

                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                      <Typography variant="body2" sx={{ color: '#9ca3af' }}>
                        {formatDuration(batch.duration_seconds)}
                      </Typography>
                      <IconButton
                        size="small"
                        sx={{
                          color: '#9ca3af',
                          transform: expandedRows.has(batch.id) ? 'rotate(180deg)' : 'rotate(0deg)',
                          transition: 'transform 0.3s',
                        }}
                      >
                        <ExpandMoreIcon />
                      </IconButton>
                    </Box>
                  </Box>
                </Box>

                {/* Expanded Step Details */}
                <Collapse in={expandedRows.has(batch.id)} timeout="auto" unmountOnExit>
                  {batch.steps && (
                    <Box sx={{ bgcolor: 'rgba(31, 41, 55, 0.2)', borderTop: '1px solid #1f2937', p: 2 }}>
                      <Typography variant="body2" sx={{ color: '#d1d5db', fontWeight: 500, mb: 2 }}>
                        Execution Steps:
                      </Typography>
                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                        {batch.steps.map((step) => (
                          <Card
                            key={step.id}
                            sx={{
                              bgcolor: 'rgba(17, 24, 39, 0.4)',
                              border: '1px solid #374151',
                            }}
                          >
                            <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flex: 1 }}>
                                  <Typography variant="body2" sx={{ color: '#6b7280', minWidth: 24 }}>
                                    {step.step_order}
                                  </Typography>

                                  <Box sx={{ flex: 1 }}>
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: step.error_message ? 0.5 : 0 }}>
                                      <Typography variant="body2" sx={{ color: 'white', fontWeight: 500 }}>
                                        {step.step_name}
                                      </Typography>
                                      {getStepStatusChip(step.status)}
                                    </Box>
                                    {step.error_message && (
                                      <Typography variant="caption" sx={{ color: '#f87171' }}>
                                        {step.error_message}
                                      </Typography>
                                    )}
                                  </Box>
                                </Box>

                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                  <Typography variant="body2" sx={{ color: '#9ca3af' }}>
                                    {formatDuration(step.duration_seconds)}
                                  </Typography>
                                  <Typography variant="body2" sx={{ color: '#9ca3af' }}>
                                    {step.records_processed} records
                                  </Typography>
                                  {step.output_log && (
                                    <Button
                                      size="small"
                                      startIcon={<VisibilityIcon />}
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        setSelectedLog({ stepName: step.step_name, log: step.output_log! });
                                      }}
                                      sx={{
                                        color: '#c084fc',
                                        textTransform: 'none',
                                        '&:hover': {
                                          color: '#e9d5ff',
                                        }
                                      }}
                                    >
                                      View Logs
                                    </Button>
                                  )}
                                </Box>
                              </Box>
                            </CardContent>
                          </Card>
                        ))}
                      </Box>
                    </Box>
                  )}
                </Collapse>
              </Box>
            ))}
          </Box>
        )}
      </Card>

      {/* Log Viewer Modal */}
      {selectedLog && (
        <LogViewerModal
          stepName={selectedLog.stepName}
          log={selectedLog.log}
          onClose={() => setSelectedLog(null)}
        />
      )}
    </Box>
  );
}
