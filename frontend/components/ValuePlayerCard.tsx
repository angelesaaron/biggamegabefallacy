import { TrendingUp, TrendingDown, Remove } from '@mui/icons-material';
import { Box, Card, Avatar, Typography, Chip, Grid, useTheme, useMediaQuery } from '@mui/material';

interface ValuePlayerCardProps {
  player_id: string;
  player_name: string;
  team_name: string | null;
  position: string | null;
  headshot_url: string | null;
  td_likelihood: number;
  model_odds: string;
  sportsbook_odds?: number;
  edge_value?: number;
  rank: number;
  onClick?: (playerId: string) => void;
}

export function ValuePlayerCard({
  player_id,
  player_name,
  team_name,
  position,
  headshot_url,
  td_likelihood,
  model_odds,
  sportsbook_odds,
  edge_value,
  rank,
  onClick,
}: ValuePlayerCardProps) {
  const edgeType =
    edge_value && edge_value > 0
      ? 'positive'
      : edge_value && edge_value < 0
      ? 'negative'
      : 'neutral';

  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const getEdgeColor = () => {
    if (edgeType === 'positive') return '#10b981';
    if (edgeType === 'negative') return '#ef4444';
    return '#6b7280';
  };

  const getEdgeIcon = () => {
    const iconProps = { sx: { fontSize: 20 } };
    if (edgeType === 'positive') return <TrendingUp {...iconProps} />;
    if (edgeType === 'negative') return <TrendingDown {...iconProps} />;
    return <Remove {...iconProps} />;
  };

  const getEdgeBgColor = () => {
    if (edgeType === 'positive') return 'rgba(16, 185, 129, 0.1)';
    if (edgeType === 'negative') return 'rgba(239, 68, 68, 0.1)';
    return 'rgba(107, 114, 128, 0.1)';
  };

  const getEdgeBorderColor = () => {
    if (edgeType === 'positive') return 'rgba(16, 185, 129, 0.3)';
    if (edgeType === 'negative') return 'rgba(239, 68, 68, 0.3)';
    return 'rgba(107, 114, 128, 0.3)';
  };

  // Format sportsbook odds to American odds string
  const formatSportsbookOdds = (odds?: number) => {
    if (!odds) return 'N/A';
    return odds > 0 ? `+${odds}` : `${odds}`;
  };

  // Format model odds to American odds string with + prefix and rounding
  const formatModelOdds = (odds: string) => {
    const numOdds = parseFloat(odds);
    if (isNaN(numOdds)) return odds;
    const rounded = Math.round(numOdds);
    return rounded > 0 ? `+${rounded}` : `${rounded}`;
  };

  return (
    <Card
      onClick={() => onClick?.(player_id)}
      sx={{
        bgcolor: 'rgba(17, 24, 39, 0.4)',
        backdropFilter: 'blur(8px)',
        border: '1px solid #1f2937',
        borderRadius: 3,
        p: { xs: 2, md: 3 },
        cursor: 'pointer',
        transition: 'all 0.2s',
        '&:hover': {
          borderColor: 'rgba(147, 51, 234, 0.5)',
        }
      }}
    >
      {isMobile ? (
        /* Mobile Layout - Stacked */
        <Box>
          {/* Top Row: Rank + Player Info */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
            <Typography variant="h5" sx={{ color: '#6b7280', width: 40, textAlign: 'center', flexShrink: 0 }}>
              #{rank}
            </Typography>
            <Avatar
              src={headshot_url || '/placeholder-player.png'}
              alt={player_name}
              sx={{
                width: 48,
                height: 48,
                border: '2px solid #374151',
                flexShrink: 0
              }}
            />
            <Box sx={{ minWidth: 0, flex: 1 }}>
              <Typography variant="body1" sx={{ color: '#fff', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {player_name}
              </Typography>
              <Typography variant="body2" sx={{ color: '#9ca3af' }}>
                {team_name || 'N/A'} • {position || 'N/A'}
              </Typography>
            </Box>
          </Box>

          {/* Stats Grid */}
          <Grid container spacing={1}>
            <Grid item xs={6}>
              <Box sx={{ textAlign: 'center', bgcolor: 'rgba(17, 24, 39, 0.5)', borderRadius: 2, p: 1.5 }}>
                <Typography variant="caption" sx={{ color: '#6b7280', display: 'block', mb: 0.5 }}>
                  Model %
                </Typography>
                <Typography variant="h6" sx={{ color: '#a78bfa', fontWeight: 600 }}>
                  {(td_likelihood * 100).toFixed(1)}%
                </Typography>
              </Box>
            </Grid>
            {edge_value !== undefined && (
              <Grid item xs={6}>
                <Box sx={{
                  textAlign: 'center',
                  bgcolor: getEdgeBgColor(),
                  border: `1px solid ${getEdgeBorderColor()}`,
                  borderRadius: 2,
                  p: 1.5
                }}>
                  <Typography variant="caption" sx={{ color: '#6b7280', display: 'block', mb: 0.5 }}>
                    Edge
                  </Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
                    <Box sx={{ color: getEdgeColor(), display: 'flex' }}>
                      {getEdgeIcon()}
                    </Box>
                    <Typography variant="h6" sx={{ color: getEdgeColor(), fontWeight: 600 }}>
                      {edgeType === 'positive' ? '+' : ''}
                      {(edge_value * 100).toFixed(1)}%
                    </Typography>
                  </Box>
                </Box>
              </Grid>
            )}
            <Grid item xs={6}>
              <Box sx={{ textAlign: 'center', bgcolor: 'rgba(17, 24, 39, 0.5)', borderRadius: 2, p: 1.5 }}>
                <Typography variant="caption" sx={{ color: '#6b7280', display: 'block', mb: 0.5 }}>
                  Model Odds
                </Typography>
                <Typography variant="h6" sx={{ color: '#a78bfa', fontWeight: 600 }}>
                  {formatModelOdds(model_odds)}
                </Typography>
              </Box>
            </Grid>
            {sportsbook_odds !== undefined && (
              <Grid item xs={6}>
                <Box sx={{ textAlign: 'center', bgcolor: 'rgba(17, 24, 39, 0.5)', borderRadius: 2, p: 1.5 }}>
                  <Typography variant="caption" sx={{ color: '#6b7280', display: 'block', mb: 0.5 }}>
                    Sportsbook
                  </Typography>
                  <Typography variant="h6" sx={{ color: '#fff', fontWeight: 600 }}>
                    {formatSportsbookOdds(sportsbook_odds)}
                  </Typography>
                </Box>
              </Grid>
            )}
          </Grid>
        </Box>
      ) : (
        /* Desktop Layout - Horizontal */
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 3 }}>
          <Typography variant="h4" sx={{ color: '#6b7280', width: 48, textAlign: 'center', flexShrink: 0 }}>
            #{rank}
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flex: 1, minWidth: 0 }}>
            <Avatar
              src={headshot_url || '/placeholder-player.png'}
              alt={player_name}
              sx={{
                width: 64,
                height: 64,
                border: '2px solid #374151',
                flexShrink: 0
              }}
            />
            <Box sx={{ minWidth: 0, flex: 1 }}>
              <Typography variant="h6" sx={{ color: '#fff', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {player_name}
              </Typography>
              <Typography variant="body2" sx={{ color: '#9ca3af' }}>
                {team_name || 'N/A'} • {position || 'N/A'}
              </Typography>
            </Box>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 3 }}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="caption" sx={{ color: '#6b7280', display: 'block', mb: 0.5 }}>
                Model %
              </Typography>
              <Typography variant="h5" sx={{ color: '#a78bfa', fontWeight: 600 }}>
                {(td_likelihood * 100).toFixed(1)}%
              </Typography>
            </Box>
            {edge_value !== undefined && (
              <Box sx={{
                textAlign: 'center',
                bgcolor: getEdgeBgColor(),
                border: `1px solid ${getEdgeBorderColor()}`,
                borderRadius: 2,
                px: 3,
                py: 1.5
              }}>
                <Typography variant="caption" sx={{ color: '#6b7280', display: 'block', mb: 0.5 }}>
                  Edge
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1 }}>
                  <Box sx={{ color: getEdgeColor(), display: 'flex' }}>
                    {getEdgeIcon()}
                  </Box>
                  <Typography variant="h6" sx={{ color: getEdgeColor(), fontWeight: 600 }}>
                    {edgeType === 'positive' ? '+' : ''}
                    {(edge_value * 100).toFixed(1)}%
                  </Typography>
                </Box>
              </Box>
            )}
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="caption" sx={{ color: '#6b7280', display: 'block', mb: 0.5 }}>
                Model Odds
              </Typography>
              <Typography variant="h6" sx={{ color: '#a78bfa', fontWeight: 600 }}>
                {formatModelOdds(model_odds)}
              </Typography>
            </Box>
            {sportsbook_odds !== undefined && (
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="caption" sx={{ color: '#6b7280', display: 'block', mb: 0.5 }}>
                  Sportsbook
                </Typography>
                <Typography variant="h6" sx={{ color: '#fff', fontWeight: 600 }}>
                  {formatSportsbookOdds(sportsbook_odds)}
                </Typography>
              </Box>
            )}
          </Box>
        </Box>
      )}
    </Card>
  );
}
