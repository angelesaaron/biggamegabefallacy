'use client';

import { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  TextField,
  Typography,
  Button,
  Grid,
  Alert,
  AlertTitle,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  CircularProgress,
} from '@mui/material';
import {
  PlayArrow,
  Info,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
} from '@mui/icons-material';

export default function ActionsTab() {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [selectedWeek, setSelectedWeek] = useState<number>(18);
  const [selectedYear, setSelectedYear] = useState<number>(2025);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  const triggerBatchUpdate = async (mode?: string, customWeek?: number, customYear?: number) => {
    if (!password) {
      setResult({ type: 'error', message: 'Admin password is required' });
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      const body: any = { password };
      if (customWeek) body.week = customWeek;
      if (customYear) body.year = customYear;

      const endpoint = mode === 'odds_only'
        ? `${API_URL}/api/admin/actions/run-batch-update`
        : `${API_URL}/api/admin/actions/run-batch-update`;

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      const data = await response.json();

      if (response.ok) {
        setResult({
          type: 'success',
          message: `${data.message}. Process ID: ${data.process_id}`,
        });
        setPassword('');
      } else {
        setResult({
          type: 'error',
          message: data.detail || 'Failed to trigger batch update',
        });
      }
    } catch (error) {
      setResult({
        type: 'error',
        message: error instanceof Error ? error.message : 'Network error',
      });
    } finally {
      setLoading(false);
    }
  };

  const triggerRefreshRosters = async () => {
    if (!password) {
      setResult({ type: 'error', message: 'Admin password is required' });
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      const response = await fetch(`${API_URL}/api/admin/actions/refresh-rosters`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      });

      const data = await response.json();

      if (response.ok) {
        setResult({
          type: 'success',
          message: `${data.message}. Process ID: ${data.process_id}`,
        });
        setPassword('');
      } else {
        setResult({
          type: 'error',
          message: data.detail || 'Failed to refresh rosters',
        });
      }
    } catch (error) {
      setResult({
        type: 'error',
        message: error instanceof Error ? error.message : 'Network error',
      });
    } finally {
      setLoading(false);
    }
  };

  const triggerBackfillComplete = async (weeksCount?: number, customWeek?: number, customYear?: number) => {
    if (!password) {
      setResult({ type: 'error', message: 'Admin password is required' });
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      const body: any = { password };
      if (weeksCount) body.weeks = weeksCount;
      if (customWeek) body.week = customWeek;
      if (customYear) body.year = customYear;

      const response = await fetch(`${API_URL}/api/admin/actions/backfill-complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      const data = await response.json();

      if (response.ok) {
        setResult({
          type: 'success',
          message: `${data.message}. Process ID: ${data.process_id}`,
        });
        setPassword('');
      } else {
        setResult({
          type: 'error',
          message: data.detail || 'Failed to backfill data',
        });
      }
    } catch (error) {
      setResult({
        type: 'error',
        message: error instanceof Error ? error.message : 'Network error',
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {/* Password Input */}
      <Card sx={{ bgcolor: 'rgba(17, 24, 39, 0.4)', backdropFilter: 'blur(8px)', border: '1px solid #1f2937' }}>
        <CardContent>
          <TextField
            type="password"
            label="Admin Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Enter admin password"
            fullWidth
            variant="outlined"
            sx={{
              '& .MuiOutlinedInput-root': {
                color: 'white',
                bgcolor: '#1f2937',
                '& fieldset': {
                  borderColor: '#374151',
                },
                '&:hover fieldset': {
                  borderColor: '#4b5563',
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
          <Typography variant="caption" sx={{ color: '#6b7280', mt: 1, display: 'block' }}>
            Required for all admin actions. Password is cleared after successful execution.
          </Typography>
        </CardContent>
      </Card>

      {/* Result Display */}
      {result && (
        <Alert
          severity={result.type === 'success' ? 'success' : 'error'}
          icon={result.type === 'success' ? <CheckCircleIcon /> : <ErrorIcon />}
          sx={{
            bgcolor: result.type === 'success' ? 'rgba(5, 150, 105, 0.1)' : 'rgba(239, 68, 68, 0.1)',
            border: `1px solid ${result.type === 'success' ? '#059669' : '#dc2626'}`,
            color: result.type === 'success' ? '#10b981' : '#ef4444',
            '& .MuiAlert-icon': {
              color: result.type === 'success' ? '#10b981' : '#ef4444',
            },
          }}
        >
          <AlertTitle sx={{ fontWeight: 600 }}>
            {result.type === 'success' ? 'Success!' : 'Error'}
          </AlertTitle>
          {result.message}
          {result.type === 'success' && (
            <Typography variant="caption" sx={{ display: 'block', mt: 1, color: '#9ca3af' }}>
              Check the Batch History tab to monitor execution progress.
            </Typography>
          )}
        </Alert>
      )}

      {/* Quick Actions */}
      <Card sx={{ bgcolor: 'rgba(17, 24, 39, 0.4)', backdropFilter: 'blur(8px)', border: '1px solid #1f2937' }}>
        <CardContent>
          <Typography variant="h6" sx={{ color: 'white', fontWeight: 600, mb: 1 }}>
            Quick Actions
          </Typography>
          <Typography variant="body2" sx={{ color: '#9ca3af', mb: 3 }}>
            One-click batch operations with default settings (current week auto-detected).
          </Typography>

          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <ActionButton
                title="Run Full Batch Update"
                description="Update schedule, game logs, and odds for current week"
                onClick={() => triggerBatchUpdate()}
                loading={loading}
                variant="primary"
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <ActionButton
                title="Refresh Rosters"
                description="Fetch latest player rosters and add new players"
                onClick={triggerRefreshRosters}
                loading={loading}
                variant="secondary"
              />
            </Grid>

          </Grid>
        </CardContent>
      </Card>

      {/* Complete Backfill with Parameters */}
      <Card sx={{ bgcolor: 'rgba(17, 24, 39, 0.4)', backdropFilter: 'blur(8px)', border: '1px solid #1f2937' }}>
        <CardContent>
          <Typography variant="h6" sx={{ color: 'white', fontWeight: 600, mb: 1 }}>
            Complete Historical Backfill
          </Typography>
          <Typography variant="body2" sx={{ color: '#9ca3af', mb: 3 }}>
            Backfill game logs, predictions, and odds for historical weeks. Efficient and idempotent.
          </Typography>

          {/* Week/Year Selection */}
          <Grid container spacing={2} sx={{ mb: 3 }}>
            <Grid item xs={6}>
              <FormControl fullWidth>
                <InputLabel
                  sx={{
                    color: '#9ca3af',
                    '&.Mui-focused': {
                      color: '#9333ea',
                    },
                  }}
                >
                  Week
                </InputLabel>
                <Select
                  value={selectedWeek}
                  onChange={(e) => setSelectedWeek(Number(e.target.value))}
                  label="Week"
                  sx={{
                    color: 'white',
                    bgcolor: '#1f2937',
                    '& .MuiOutlinedInput-notchedOutline': {
                      borderColor: '#374151',
                    },
                    '&:hover .MuiOutlinedInput-notchedOutline': {
                      borderColor: '#4b5563',
                    },
                    '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                      borderColor: '#9333ea',
                    },
                    '& .MuiSvgIcon-root': {
                      color: '#9ca3af',
                    },
                  }}
                  MenuProps={{
                    PaperProps: {
                      sx: {
                        bgcolor: '#1f2937',
                        border: '1px solid #374151',
                        '& .MuiMenuItem-root': {
                          color: 'white',
                          '&:hover': {
                            bgcolor: '#374151',
                          },
                          '&.Mui-selected': {
                            bgcolor: '#9333ea',
                            '&:hover': {
                              bgcolor: '#7e22ce',
                            },
                          },
                        },
                      },
                    },
                  }}
                >
                  {Array.from({ length: 18 }, (_, i) => i + 1).map((week) => (
                    <MenuItem key={week} value={week}>
                      Week {week}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={6}>
              <FormControl fullWidth>
                <InputLabel
                  sx={{
                    color: '#9ca3af',
                    '&.Mui-focused': {
                      color: '#9333ea',
                    },
                  }}
                >
                  Year
                </InputLabel>
                <Select
                  value={selectedYear}
                  onChange={(e) => setSelectedYear(Number(e.target.value))}
                  label="Year"
                  sx={{
                    color: 'white',
                    bgcolor: '#1f2937',
                    '& .MuiOutlinedInput-notchedOutline': {
                      borderColor: '#374151',
                    },
                    '&:hover .MuiOutlinedInput-notchedOutline': {
                      borderColor: '#4b5563',
                    },
                    '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                      borderColor: '#9333ea',
                    },
                    '& .MuiSvgIcon-root': {
                      color: '#9ca3af',
                    },
                  }}
                  MenuProps={{
                    PaperProps: {
                      sx: {
                        bgcolor: '#1f2937',
                        border: '1px solid #374151',
                        '& .MuiMenuItem-root': {
                          color: 'white',
                          '&:hover': {
                            bgcolor: '#374151',
                          },
                          '&.Mui-selected': {
                            bgcolor: '#9333ea',
                            '&:hover': {
                              bgcolor: '#7e22ce',
                            },
                          },
                        },
                      },
                    },
                  }}
                >
                  <MenuItem value={2024}>2024</MenuItem>
                  <MenuItem value={2025}>2025</MenuItem>
                  <MenuItem value={2026}>2026</MenuItem>
                </Select>
              </FormControl>
            </Grid>
          </Grid>

          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <ActionButton
                title="Backfill Last 5 Weeks (Current Season)"
                description="Backfill last 5 weeks from current NFL week (~160 API calls)"
                onClick={() => triggerBackfillComplete(5)}
                loading={loading}
                variant="secondary"
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <ActionButton
                title={`Backfill ${selectedYear} Week ${selectedWeek}`}
                description={`Complete backfill for selected week (~32 API calls)`}
                onClick={() => triggerBackfillComplete(undefined, selectedWeek, selectedYear)}
                loading={loading}
                variant="secondary"
              />
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Advanced Actions */}
      <Card sx={{ bgcolor: 'rgba(17, 24, 39, 0.4)', backdropFilter: 'blur(8px)', border: '1px solid #1f2937' }}>
        <CardContent>
          <Typography variant="h6" sx={{ color: 'white', fontWeight: 600, mb: 1 }}>
            Advanced Actions
          </Typography>
          <Typography variant="body2" sx={{ color: '#9ca3af', mb: 3 }}>
            Custom batch operations with week/year parameters.
          </Typography>

          {/* Week/Year Selection */}
          <Grid container spacing={2} sx={{ mb: 3 }}>
            <Grid item xs={6}>
              <FormControl fullWidth>
                <InputLabel
                  sx={{
                    color: '#9ca3af',
                    '&.Mui-focused': {
                      color: '#9333ea',
                    },
                  }}
                >
                  Week
                </InputLabel>
                <Select
                  value={selectedWeek}
                  onChange={(e) => setSelectedWeek(Number(e.target.value))}
                  label="Week"
                  sx={{
                    color: 'white',
                    bgcolor: '#1f2937',
                    '& .MuiOutlinedInput-notchedOutline': {
                      borderColor: '#374151',
                    },
                    '&:hover .MuiOutlinedInput-notchedOutline': {
                      borderColor: '#4b5563',
                    },
                    '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                      borderColor: '#9333ea',
                    },
                    '& .MuiSvgIcon-root': {
                      color: '#9ca3af',
                    },
                  }}
                  MenuProps={{
                    PaperProps: {
                      sx: {
                        bgcolor: '#1f2937',
                        border: '1px solid #374151',
                        '& .MuiMenuItem-root': {
                          color: 'white',
                          '&:hover': {
                            bgcolor: '#374151',
                          },
                          '&.Mui-selected': {
                            bgcolor: '#9333ea',
                            '&:hover': {
                              bgcolor: '#7e22ce',
                            },
                          },
                        },
                      },
                    },
                  }}
                >
                  {Array.from({ length: 18 }, (_, i) => i + 1).map((week) => (
                    <MenuItem key={week} value={week}>
                      Week {week}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={6}>
              <FormControl fullWidth>
                <InputLabel
                  sx={{
                    color: '#9ca3af',
                    '&.Mui-focused': {
                      color: '#9333ea',
                    },
                  }}
                >
                  Year
                </InputLabel>
                <Select
                  value={selectedYear}
                  onChange={(e) => setSelectedYear(Number(e.target.value))}
                  label="Year"
                  sx={{
                    color: 'white',
                    bgcolor: '#1f2937',
                    '& .MuiOutlinedInput-notchedOutline': {
                      borderColor: '#374151',
                    },
                    '&:hover .MuiOutlinedInput-notchedOutline': {
                      borderColor: '#4b5563',
                    },
                    '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                      borderColor: '#9333ea',
                    },
                    '& .MuiSvgIcon-root': {
                      color: '#9ca3af',
                    },
                  }}
                  MenuProps={{
                    PaperProps: {
                      sx: {
                        bgcolor: '#1f2937',
                        border: '1px solid #374151',
                        '& .MuiMenuItem-root': {
                          color: 'white',
                          '&:hover': {
                            bgcolor: '#374151',
                          },
                          '&.Mui-selected': {
                            bgcolor: '#9333ea',
                            '&:hover': {
                              bgcolor: '#7e22ce',
                            },
                          },
                        },
                      },
                    },
                  }}
                >
                  <MenuItem value={2024}>2024</MenuItem>
                  <MenuItem value={2025}>2025</MenuItem>
                  <MenuItem value={2026}>2026</MenuItem>
                </Select>
              </FormControl>
            </Grid>
          </Grid>

          {/* Advanced Action Buttons */}
          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <ActionButton
                title="Update Specific Week"
                description={`Run full batch for ${selectedYear} Week ${selectedWeek}`}
                onClick={() => triggerBatchUpdate(undefined, selectedWeek, selectedYear)}
                loading={loading}
                variant="secondary"
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <ActionButton
                title="Refresh Odds Only"
                description={`Update odds for ${selectedYear} Week ${selectedWeek}`}
                onClick={() => triggerBatchUpdate('odds_only', selectedWeek, selectedYear)}
                loading={loading}
                variant="secondary"
              />
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Info Panel */}
      <Alert
        severity="info"
        icon={<Info />}
        sx={{
          bgcolor: 'rgba(59, 130, 246, 0.1)',
          border: '1px solid #1e40af',
          color: '#93c5fd',
          '& .MuiAlert-icon': {
            color: '#60a5fa',
          },
        }}
      >
        <AlertTitle sx={{ fontWeight: 600, color: '#93c5fd' }}>Important Notes:</AlertTitle>
        <Box component="ul" sx={{ pl: 2, m: 0, fontSize: '0.75rem', color: '#93c5fd' }}>
          <li>Batch processes run in the background and may take several minutes</li>
          <li>Monitor progress in the Batch History tab (auto-refreshes every 30 seconds)</li>
          <li>Actions are rate-limited to 5 requests per minute per IP</li>
          <li>Only one batch can run at a time to prevent conflicts</li>
        </Box>
      </Alert>
    </Box>
  );
}

interface ActionButtonProps {
  title: string;
  description: string;
  onClick: () => void;
  loading: boolean;
  variant: 'primary' | 'secondary';
}

function ActionButton({ title, description, onClick, loading, variant }: ActionButtonProps) {
  return (
    <Button
      onClick={onClick}
      disabled={loading}
      fullWidth
      sx={{
        p: 2,
        textAlign: 'left',
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'flex-start',
        textTransform: 'none',
        bgcolor: variant === 'primary' ? '#9333ea' : '#1f2937',
        border: `1px solid ${variant === 'primary' ? '#7e22ce' : '#374151'}`,
        color: 'white',
        transition: 'all 0.2s',
        '&:hover': {
          bgcolor: variant === 'primary' ? '#7e22ce' : '#374151',
          transform: 'scale(1.02)',
        },
        '&:disabled': {
          opacity: 0.5,
          cursor: 'not-allowed',
          bgcolor: variant === 'primary' ? '#9333ea' : '#1f2937',
          color: 'white',
        },
      }}
    >
      <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start', width: '100%' }}>
        <Box sx={{ flexShrink: 0, mt: 0.5 }}>
          {loading ? <CircularProgress size={20} sx={{ color: 'white' }} /> : <PlayArrow />}
        </Box>
        <Box sx={{ flex: 1 }}>
          <Typography variant="body1" sx={{ fontWeight: 500, mb: 0.5 }}>
            {title}
          </Typography>
          <Typography variant="body2" sx={{ color: '#9ca3af', fontSize: '0.875rem' }}>
            {description}
          </Typography>
        </Box>
      </Box>
    </Button>
  );
}
