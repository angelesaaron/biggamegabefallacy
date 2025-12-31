'use client';

import { useEffect, useState } from 'react';
import { ValuePlayerCard } from '@/components/ValuePlayerCard';
import { GamblingDisclaimer } from '@/components/GamblingDisclaimer';
import { PlayerWeekToggle } from '@/components/PlayerWeekToggle';
import { TrendingUp, TrendingDown, Warning } from '@mui/icons-material';
import {
  Box,
  Container,
  Typography,
  Card,
  CircularProgress,
  Alert,
  ToggleButtonGroup,
  ToggleButton,
  Checkbox,
  FormControlLabel,
  Stack
} from '@mui/material';

interface Prediction {
  player_id: string;
  player_name: string;
  team_name: string | null;
  position: string | null;
  headshot_url: string | null;
  season_year: number;
  week: number;
  td_likelihood: string;
  model_odds: string;
  favor: number;
  created_at: string | null;
}

interface ValuePick extends Prediction {
  sportsbook_odds?: number;
  expected_value?: number;
  has_edge?: boolean;
}

interface PredictionsMetadata {
  current_week: number;
  current_year: number;
  showing_week: number;
  showing_year: number;
  is_fallback: boolean;
}

interface WeeklyValueProps {
  onPlayerClick?: (playerId: string) => void;
}

export default function WeeklyValue({ onPlayerClick }: WeeklyValueProps) {
  const [predictions, setPredictions] = useState<ValuePick[]>([]);
  const [metadata, setMetadata] = useState<PredictionsMetadata | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSportsbook, setSelectedSportsbook] = useState<
    'draftkings' | 'fanduel'
  >('draftkings');
  const [showOnlyEdge, setShowOnlyEdge] = useState(true);
  const [currentWeek, setCurrentWeek] = useState(18);
  const [currentYear, setCurrentYear] = useState(2025);
  const [selectedWeek, setSelectedWeek] = useState(18);

  // Fetch current week on mount
  useEffect(() => {
    async function fetchCurrentWeek() {
      try {
        const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const response = await fetch(`${API_URL}/api/admin/data-readiness/current`);
        const data = await response.json();
        const currentWeekData = data.current_week;

        if (currentWeekData) {
          setCurrentWeek(currentWeekData.week);
          setCurrentYear(currentWeekData.year);
          setSelectedWeek(currentWeekData.week);
        }
      } catch (error) {
        console.error('Failed to fetch current week:', error);
      }
    }

    fetchCurrentWeek();
  }, []);

  // Load predictions when week or sportsbook changes
  useEffect(() => {
    async function loadPredictions() {
      try {
        setLoading(true);
        setError(null);

        const API_URL =
          process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

        // Build URL with week/year params
        const params = new URLSearchParams();
        params.set('week', selectedWeek.toString());
        params.set('year', currentYear.toString());
        const url = `${API_URL}/api/predictions/current?${params.toString()}`;

        const response = await fetch(url);
        if (!response.ok) throw new Error('Failed to fetch predictions');

        const data = await response.json();
        const preds: Prediction[] = data.predictions || [];
        const meta: PredictionsMetadata = data.metadata;

        setMetadata(meta);

        // If no predictions at all, show error
        if (!preds || preds.length === 0) {
          setPredictions([]);
          setLoading(false);
          return;
        }

        // Fetch odds for each prediction
        const predsWithOdds = await Promise.all(
          preds.map(async (pred: Prediction, index: number) => {
            try {
              const oddsUrl = `${API_URL}/api/odds/comparison/${pred.player_id}?week=${pred.week}&year=${pred.season_year}`;
              const oddsData = await fetch(oddsUrl).then((r) => r.json());
              const modelProb = parseFloat(pred.td_likelihood);
              const sbOdds = oddsData.sportsbook_odds?.[selectedSportsbook];

              let ev = 0;
              let hasEdge = false;

              if (sbOdds) {
                const sbImpliedProb =
                  sbOdds > 0
                    ? 100 / (sbOdds + 100)
                    : Math.abs(sbOdds) / (Math.abs(sbOdds) + 100);

                const payout =
                  sbOdds > 0 ? sbOdds / 100 : 100 / Math.abs(sbOdds);
                ev = modelProb * payout - (1 - modelProb);
                hasEdge = ev > 0 && modelProb > sbImpliedProb;
              }

              return {
                ...pred,
                sportsbook_odds: sbOdds,
                expected_value: ev,
                has_edge: hasEdge,
              };
            } catch (err) {
              return {
                ...pred,
                sportsbook_odds: undefined,
                expected_value: 0,
                has_edge: false,
              };
            }
          })
        );

        // Sort by expected value descending
        const sorted = predsWithOdds.sort(
          (a, b) => (b.expected_value || 0) - (a.expected_value || 0)
        );
        setPredictions(sorted);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to load predictions'
        );
      } finally {
        setLoading(false);
      }
    }

    loadPredictions();
  }, [selectedSportsbook, selectedWeek, currentYear]);

  const filteredPredictions = predictions.filter((p) => {
    // Filter by edge if enabled
    if (showOnlyEdge && !p.has_edge) return false;

    return true;
  });

  return (
    <Box sx={{ position: 'relative' }}>
      {/* Hero Background */}
      <Box
        sx={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: 384,
          backgroundImage: 'url(/gabe-davis-background.jpg)',
          backgroundSize: 'cover',
          backgroundPosition: 'center 15%',
          '&::after': {
            content: '""',
            position: 'absolute',
            inset: 0,
            background: 'linear-gradient(to bottom, rgba(0,0,0,0.6), rgba(0,0,0,0.75), #0a0a0a)',
          }
        }}
      />

      {/* Content */}
      <Container maxWidth="xl" sx={{ position: 'relative', py: 4 }}>
        {/* Header */}
        <Card
          sx={{
            mb: 4,
            bgcolor: 'rgba(17, 24, 39, 0.4)',
            backdropFilter: 'blur(8px)',
            border: '1px solid #1f2937',
            borderRadius: 3,
            p: { xs: 2, md: 3 }
          }}
        >
          <Box sx={{ display: 'flex', alignItems: { xs: 'flex-start', md: 'center' }, justifyContent: 'space-between', gap: 2, flexDirection: { xs: 'column', md: 'row' } }}>
            <Box sx={{ flex: 1 }}>
              <Typography variant="h4" sx={{ color: '#fff', mb: 1, fontSize: { xs: '1.5rem', md: '2rem' } }}>
                Week {selectedWeek} Value Plays
              </Typography>
              <Typography variant="body2" sx={{ color: '#9ca3af', fontSize: { xs: '0.875rem', md: '1rem' } }}>
                Players with the highest model edge vs sportsbook odds
              </Typography>
            </Box>
            <PlayerWeekToggle
              currentWeek={currentWeek}
              currentYear={currentYear}
              selectedWeek={selectedWeek}
              onWeekChange={setSelectedWeek}
            />
          </Box>
        </Card>

        {/* Loading Overlay */}
        {loading && (
          <Card sx={{ mb: 3, bgcolor: 'rgba(17, 24, 39, 0.4)', backdropFilter: 'blur(8px)', border: '1px solid #1f2937', borderRadius: 3, p: 4 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <CircularProgress sx={{ color: '#a78bfa', mr: 2 }} />
              <Typography variant="h6" sx={{ color: '#fff' }}>Loading predictions...</Typography>
            </Box>
          </Card>
        )}

        {/* Error State */}
        {error && (
          <Alert severity="error" sx={{ mb: 3, bgcolor: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: 3 }}>
            Error: {error}
          </Alert>
        )}

        {/* No Predictions Available */}
        {!loading && !error && predictions.length === 0 && (
          <Card sx={{ bgcolor: 'rgba(17, 24, 39, 0.4)', backdropFilter: 'blur(8px)', border: '1px solid #1f2937', borderRadius: 3, p: 6, textAlign: 'center' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1, mb: 2 }}>
              <Warning sx={{ fontSize: 32, color: '#eab308' }} />
              <Typography variant="h5" sx={{ color: '#eab308' }}>Predictions Not Available</Typography>
            </Box>
            <Typography variant="body1" sx={{ color: '#9ca3af', mb: 1 }}>
              Week {selectedWeek} predictions haven't been generated yet.
            </Typography>
            <Typography variant="body2" sx={{ color: '#6b7280' }}>
              Check back after the weekly batch job completes or try viewing a previous week.
            </Typography>
          </Card>
        )}

        {/* Filters - only show when we have data */}
        {!loading && !error && predictions.length > 0 && (
          <Card sx={{ mb: 3, bgcolor: 'rgba(17, 24, 39, 0.4)', backdropFilter: 'blur(8px)', border: '1px solid #1f2937', borderRadius: 3, p: 3 }}>
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} alignItems={{ xs: 'stretch', md: 'center' }}>
              <ToggleButtonGroup
                value={selectedSportsbook}
                exclusive
                onChange={(_e, newValue) => newValue && setSelectedSportsbook(newValue)}
                sx={{
                  bgcolor: 'rgba(17, 24, 39, 0.5)',
                  '& .MuiToggleButton-root': {
                    color: '#9ca3af',
                    border: 'none',
                    px: { xs: 2, md: 3 },
                    py: 1,
                    fontSize: { xs: '0.875rem', md: '1rem' },
                    '&.Mui-selected': {
                      bgcolor: '#9333ea',
                      color: '#fff',
                      '&:hover': {
                        bgcolor: '#7e22ce',
                      }
                    },
                    '&:hover': {
                      color: '#fff',
                    }
                  }
                }}
              >
                <ToggleButton value="draftkings">DraftKings</ToggleButton>
                <ToggleButton value="fanduel">FanDuel</ToggleButton>
              </ToggleButtonGroup>

              <FormControlLabel
                control={
                  <Checkbox
                    checked={showOnlyEdge}
                    onChange={(e) => setShowOnlyEdge(e.target.checked)}
                    sx={{
                      color: '#6b7280',
                      '&.Mui-checked': {
                        color: '#9333ea',
                      }
                    }}
                  />
                }
                label={<Typography variant="body2" sx={{ color: '#9ca3af', fontSize: { xs: '0.875rem', md: '1rem' } }}>Show only +EV plays</Typography>}
              />
            </Stack>
          </Card>
        )}

        {/* Value Player Cards */}
        {!loading && !error && predictions.length > 0 && (
          <>
            {filteredPredictions.length === 0 ? (
              <Card sx={{ bgcolor: 'rgba(17, 24, 39, 0.4)', backdropFilter: 'blur(8px)', border: '1px solid #1f2937', borderRadius: 3, p: 6, textAlign: 'center' }}>
                <Typography variant="h6" sx={{ color: '#9ca3af' }}>
                  No positive EV plays found for this sportsbook
                </Typography>
              </Card>
            ) : (
              <Stack spacing={2}>
                {filteredPredictions.map((prediction, index) => (
                  <ValuePlayerCard
                    key={prediction.player_id}
                    player_id={prediction.player_id}
                    player_name={prediction.player_name}
                    team_name={prediction.team_name}
                    position={prediction.position}
                    headshot_url={prediction.headshot_url}
                    td_likelihood={parseFloat(prediction.td_likelihood)}
                    model_odds={prediction.model_odds}
                    sportsbook_odds={prediction.sportsbook_odds}
                    edge_value={prediction.expected_value}
                    rank={index + 1}
                    onClick={onPlayerClick}
                  />
                ))}
              </Stack>
            )}
          </>
        )}

        {/* Legend */}
        <Card sx={{ mt: 4, bgcolor: 'rgba(17, 24, 39, 0.4)', backdropFilter: 'blur(8px)', border: '1px solid #1f2937', borderRadius: 3, p: 2 }}>
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={{ xs: 2, md: 4 }} sx={{ fontSize: '0.875rem' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <TrendingUp sx={{ fontSize: 16, color: '#10b981' }} />
              <Typography variant="body2" sx={{ color: '#9ca3af' }}>Positive Edge (Model favored)</Typography>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <TrendingDown sx={{ fontSize: 16, color: '#ef4444' }} />
              <Typography variant="body2" sx={{ color: '#9ca3af' }}>Negative Edge (Sportsbook favored)</Typography>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="body2" sx={{ color: '#9ca3af' }}>
                Edge = Expected Value vs. Sportsbook
              </Typography>
            </Box>
          </Stack>
        </Card>

        {/* Gambling Disclaimer */}
        <GamblingDisclaimer />
      </Container>
    </Box>
  );
}
