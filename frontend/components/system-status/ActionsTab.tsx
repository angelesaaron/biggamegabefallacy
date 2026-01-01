'use client';

import { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  TextField,
  Typography,
  Button,
  Alert,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  CircularProgress,
  Divider,
} from '@mui/material';

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
      <Card sx={{ bgcolor: 'rgba(17, 24, 39, 0.4)', backdropFilter: 'blur(8px)', border: '1px solid #1f2937', borderRadius: 3 }}>
        <CardContent sx={{ py: 2.5 }}>
          <TextField
            type="password"
            label="Admin Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Required for all actions"
            fullWidth
            size="small"
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
        </CardContent>
      </Card>

      {/* Result Display */}
      {result && (
        <Alert
          severity={result.type === 'success' ? 'success' : 'error'}
          sx={{
            bgcolor: result.type === 'success' ? 'rgba(5, 150, 105, 0.1)' : 'rgba(239, 68, 68, 0.1)',
            border: `1px solid ${result.type === 'success' ? '#059669' : '#dc2626'}`,
            color: result.type === 'success' ? '#10b981' : '#ef4444',
            borderRadius: 2,
            '& .MuiAlert-icon': {
              color: result.type === 'success' ? '#10b981' : '#ef4444',
            },
          }}
        >
          {result.message}
        </Alert>
      )}

      {/* Quick Actions */}
      <Card sx={{ bgcolor: 'rgba(17, 24, 39, 0.4)', backdropFilter: 'blur(8px)', border: '1px solid #1f2937', borderRadius: 3 }}>
        <CardContent>
          <Typography variant="body1" sx={{ color: 'white', fontWeight: 500, mb: 2 }}>
            Quick Actions
          </Typography>

          <Box sx={{ display: 'flex', gap: 2, flexDirection: { xs: 'column', md: 'row' } }}>
            <Box sx={{ flex: 1 }}>
              <ActionButton
                title="Run Full Batch Update"
                description="Schedule, logs, predictions, and odds"
                onClick={() => triggerBatchUpdate()}
                loading={loading}
                variant="primary"
              />
            </Box>

            <Box sx={{ flex: 1 }}>
              <ActionButton
                title="Refresh Rosters"
                description="Fetch latest player data"
                onClick={triggerRefreshRosters}
                loading={loading}
                variant="secondary"
              />
            </Box>

          </Box>
        </CardContent>
      </Card>

      {/* Complete Backfill with Parameters */}
      <Card sx={{ bgcolor: 'rgba(17, 24, 39, 0.4)', backdropFilter: 'blur(8px)', border: '1px solid #1f2937', borderRadius: 3 }}>
        <CardContent>
          <Typography variant="body1" sx={{ color: 'white', fontWeight: 500, mb: 2 }}>
            Historical Backfill
          </Typography>

          {/* Week/Year Selection */}
          <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
            <Box sx={{ flex: 1 }}>
              <FormControl fullWidth size="small">
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
            </Box>

            <Box sx={{ flex: 1 }}>
              <FormControl fullWidth size="small">
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
            </Box>
          </Box>

          <Box sx={{ display: 'flex', gap: 2, flexDirection: { xs: 'column', md: 'row' } }}>
            <Box sx={{ flex: 1 }}>
              <ActionButton
                title="Backfill Last 5 Weeks"
                description="Current season"
                onClick={() => triggerBackfillComplete(5)}
                loading={loading}
                variant="secondary"
              />
            </Box>

            <Box sx={{ flex: 1 }}>
              <ActionButton
                title={`Backfill ${selectedYear} Week ${selectedWeek}`}
                description="Selected week"
                onClick={() => triggerBackfillComplete(undefined, selectedWeek, selectedYear)}
                loading={loading}
                variant="secondary"
              />
            </Box>
          </Box>
        </CardContent>
      </Card>

      {/* Advanced Actions */}
      <Card sx={{ bgcolor: 'rgba(17, 24, 39, 0.4)', backdropFilter: 'blur(8px)', border: '1px solid #1f2937', borderRadius: 3 }}>
        <CardContent>
          <Typography variant="body1" sx={{ color: 'white', fontWeight: 500, mb: 2 }}>
            Advanced Actions
          </Typography>

          {/* Week/Year Selection */}
          <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
            <Box sx={{ flex: 1 }}>
              <FormControl fullWidth size="small">
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
            </Box>

            <Box sx={{ flex: 1 }}>
              <FormControl fullWidth size="small">
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
            </Box>
          </Box>

          {/* Advanced Action Buttons */}
          <Box sx={{ display: 'flex', gap: 2, flexDirection: { xs: 'column', md: 'row' } }}>
            <Box sx={{ flex: 1 }}>
              <ActionButton
                title="Update Specific Week"
                description={`${selectedYear} Week ${selectedWeek}`}
                onClick={() => triggerBatchUpdate(undefined, selectedWeek, selectedYear)}
                loading={loading}
                variant="secondary"
              />
            </Box>

            <Box sx={{ flex: 1 }}>
              <ActionButton
                title="Refresh Odds Only"
                description={`${selectedYear} Week ${selectedWeek}`}
                onClick={() => triggerBatchUpdate('odds_only', selectedWeek, selectedYear)}
                loading={loading}
                variant="secondary"
              />
            </Box>
          </Box>
        </CardContent>
      </Card>
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
        px: 2.5,
        py: 1.75,
        textAlign: 'left',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        textTransform: 'none',
        bgcolor: variant === 'primary' ? '#9333ea' : '#1f2937',
        border: `1px solid ${variant === 'primary' ? '#7e22ce' : '#374151'}`,
        borderRadius: 2,
        color: 'white',
        transition: 'all 0.15s ease',
        '&:hover': {
          bgcolor: variant === 'primary' ? '#7e22ce' : '#374151',
          borderColor: variant === 'primary' ? '#6b21a8' : '#4b5563',
        },
        '&:disabled': {
          opacity: 0.6,
          cursor: 'not-allowed',
          bgcolor: variant === 'primary' ? '#9333ea' : '#1f2937',
          color: 'white',
        },
      }}
    >
      <Box sx={{ flex: 1 }}>
        <Typography variant="body2" sx={{ fontWeight: 500, mb: 0.25, fontSize: '0.875rem' }}>
          {title}
        </Typography>
        <Typography variant="caption" sx={{ color: '#9ca3af', fontSize: '0.75rem' }}>
          {description}
        </Typography>
      </Box>
      {loading && <CircularProgress size={16} sx={{ color: 'white', ml: 2 }} />}
    </Button>
  );
}
