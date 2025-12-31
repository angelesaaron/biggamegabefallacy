'use client';

import { useState, useEffect } from 'react';
import WeeklyValue from '@/components/WeeklyValue';
import { PlayerModel } from '@/components/PlayerModel';
import SystemStatus from '@/components/SystemStatus';
import { Box, Tabs, Tab, Avatar, Typography, Container, AppBar } from '@mui/material';

export default function Home() {
  const [activeTab, setActiveTab] = useState<'player' | 'weekly' | 'status'>('player');
  const [selectedPlayerId, setSelectedPlayerId] = useState<string | null>(null);
  const [currentWeek, setCurrentWeek] = useState<number | null>(null);

  const handlePlayerClick = (playerId: string) => {
    setSelectedPlayerId(playerId);
    setActiveTab('player');
  };

  // Fetch current week on mount
  useEffect(() => {
    async function fetchCurrentWeek() {
      try {
        const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        // Use the same endpoint as System Status for consistency
        const response = await fetch(`${API_URL}/api/admin/data-readiness/current`);
        const data = await response.json();
        const currentWeekData = data.current_week;

        if (currentWeekData) {
          setCurrentWeek(currentWeekData.week);
        }
      } catch (error) {
        console.error('Failed to fetch current week:', error);
      }
    }

    fetchCurrentWeek();
  }, []);

  const tabValue = activeTab === 'player' ? 0 : activeTab === 'weekly' ? 1 : 2;

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    const tabs: ('player' | 'weekly' | 'status')[] = ['player', 'weekly', 'status'];
    setActiveTab(tabs[newValue]);
  };

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: '#0a0a0a', color: 'white' }}>
      {/* Top Navigation */}
      <AppBar
        position="sticky"
        sx={{
          borderBottom: '1px solid #1f2937',
          bgcolor: 'rgba(0, 0, 0, 0.4)',
          backdropFilter: 'blur(8px)',
          boxShadow: 'none'
        }}
      >
        <Container maxWidth="xl">
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 64 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: { xs: 2, sm: 4 }, flex: 1 }}>
              {/* Logo with Gabe Davis headshot */}
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <Avatar
                  src="/gabe-davis-headshot.png"
                  alt="Gabe Davis"
                  sx={{
                    width: { xs: 40, sm: 48 },
                    height: { xs: 40, sm: 48 },
                    border: '2px solid #9333ea'
                  }}
                />
                <Typography
                  variant="h6"
                  sx={{
                    fontWeight: 400,
                    letterSpacing: '-0.025em',
                    fontSize: { xs: '1.25rem', sm: '1.5rem' },
                    display: { xs: 'none', sm: 'block' }
                  }}
                >
                  BGGTDM
                </Typography>
              </Box>

              {/* Tabs */}
              <Tabs
                value={tabValue}
                onChange={handleTabChange}
                sx={{
                  minHeight: 48,
                  '& .MuiTabs-indicator': {
                    backgroundColor: '#9333ea',
                  },
                  '& .MuiTab-root': {
                    color: '#9ca3af',
                    minHeight: 48,
                    textTransform: 'none',
                    fontSize: { xs: '0.75rem', sm: '0.875rem' },
                    px: { xs: 1.5, sm: 2 },
                    minWidth: { xs: 'auto', sm: 120 },
                    '&.Mui-selected': {
                      color: '#fff',
                    },
                    '&:hover': {
                      color: '#fff',
                    }
                  }
                }}
              >
                <Tab label="Player Model" />
                <Tab label="Weekly Value" />
                <Tab label="System Status" />
              </Tabs>
            </Box>

            {/* Current Week Indicator */}
            {currentWeek && (
              <Typography
                variant="h3"
                sx={{
                  fontWeight: 700,
                  fontSize: { xs: '1.5rem', sm: '2.5rem' },
                  ml: 2
                }}
              >
                {currentWeek}
              </Typography>
            )}
          </Box>
        </Container>
      </AppBar>

      {/* Main Content */}
      {activeTab === 'player' && <PlayerModel initialPlayerId={selectedPlayerId} />}
      {activeTab === 'weekly' && <WeeklyValue onPlayerClick={handlePlayerClick} />}
      {activeTab === 'status' && <SystemStatus />}
    </Box>
  );
}
