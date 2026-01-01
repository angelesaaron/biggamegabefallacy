import { Box, Avatar, Typography, Card, useTheme, useMediaQuery } from '@mui/material';

interface Player {
  id: string;
  name: string;
  team: string;
  position: string;
  jersey: number;
  imageUrl: string;
  tdsThisSeason: number;
  gamesPlayed: number;
  targets: number;
  tdRate: string;
}

interface PlayerHeaderProps {
  player: Player;
}

export function PlayerHeader({ player }: PlayerHeaderProps) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  return (
    <Card
      sx={{
        bgcolor: 'rgba(17, 24, 39, 0.4)',
        backdropFilter: 'blur(8px)',
        border: '1px solid #1f2937',
        borderRadius: 3,
        p: { xs: 2, md: 3 },
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: { xs: 2, md: 3 },
          flexDirection: { xs: 'column', md: 'row' },
          ...(isMobile && {
            alignItems: 'center',
          }),
        }}
      >
        {/* Player Image */}
        <Avatar
          src={player.imageUrl}
          alt={player.name}
          sx={{
            width: { xs: 80, md: 96 },
            height: { xs: 80, md: 96 },
            border: '2px solid #9333ea',
            flexShrink: 0,
          }}
        />

        {/* Player Info */}
        <Box
          sx={{
            flex: 1,
            width: '100%',
            ...(isMobile && {
              textAlign: 'center',
            }),
          }}
        >
          <Typography
            variant={isMobile ? 'h5' : 'h4'}
            sx={{
              color: '#fff',
              mb: 1,
              fontWeight: 500,
            }}
          >
            {player.name}
          </Typography>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: { xs: 1.5, md: 2 },
              color: '#9ca3af',
              fontSize: { xs: '0.875rem', md: '1rem' },
              mb: { xs: 2, md: 2 },
              ...(isMobile && {
                justifyContent: 'center',
              }),
            }}
          >
            <Typography variant="body2" sx={{ color: '#9ca3af' }}>
              {player.team}
            </Typography>
            <Typography variant="body2" sx={{ color: '#9ca3af' }}>
              •
            </Typography>
            <Typography variant="body2" sx={{ color: '#9ca3af' }}>
              {player.position}
            </Typography>
          </Box>

          {/* Quick Stats */}
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: { xs: 'repeat(2, 1fr)', md: 'repeat(4, 1fr)' },
              gap: { xs: 2, md: 3 },
            }}
          >
            <Box>
              <Typography
                variant={isMobile ? 'h6' : 'h5'}
                sx={{ color: '#fff', fontWeight: 600 }}
              >
                {player.tdsThisSeason}
              </Typography>
              <Typography
                variant="caption"
                sx={{
                  color: '#6b7280',
                  display: 'block',
                  fontSize: { xs: '0.7rem', md: '0.875rem' },
                }}
              >
                TDs This Season
              </Typography>
            </Box>
            <Box>
              <Typography
                variant={isMobile ? 'h6' : 'h5'}
                sx={{ color: '#fff', fontWeight: 600 }}
              >
                {player.gamesPlayed}
              </Typography>
              <Typography
                variant="caption"
                sx={{
                  color: '#6b7280',
                  display: 'block',
                  fontSize: { xs: '0.7rem', md: '0.875rem' },
                }}
              >
                Games Played
              </Typography>
            </Box>
            <Box>
              <Typography
                variant={isMobile ? 'h6' : 'h5'}
                sx={{ color: '#fff', fontWeight: 600 }}
              >
                {player.targets}
              </Typography>
              <Typography
                variant="caption"
                sx={{
                  color: '#6b7280',
                  display: 'block',
                  fontSize: { xs: '0.7rem', md: '0.875rem' },
                }}
              >
                Targets
              </Typography>
            </Box>
            <Box>
              <Typography
                variant={isMobile ? 'h6' : 'h5'}
                sx={{ color: '#fff', fontWeight: 600 }}
              >
                {player.tdRate}
              </Typography>
              <Typography
                variant="caption"
                sx={{
                  color: '#6b7280',
                  display: 'block',
                  fontSize: { xs: '0.7rem', md: '0.875rem' },
                }}
              >
                TD Rate
              </Typography>
            </Box>
          </Box>
        </Box>
      </Box>
    </Card>
  );
}
