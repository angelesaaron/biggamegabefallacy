'use client';

import { useState } from 'react';
import { Container, Box, Tabs, Tab, Typography } from '@mui/material';
import OverviewTab from '@/components/system-status/OverviewTab';
import ActionsTab from '@/components/system-status/ActionsTab';
import BatchHistoryTab from '@/components/system-status/BatchHistoryTab';

export default function SystemStatus() {
  const [activeTab, setActiveTab] = useState(0);

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" sx={{ color: 'white', mb: 1, fontWeight: 600 }}>
          System Status & Admin
        </Typography>
        <Typography variant="body2" sx={{ color: '#9ca3af' }}>
          Data readiness, batch execution, and admin controls
        </Typography>
      </Box>

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: '#1f2937', mb: 4 }}>
        <Tabs
          value={activeTab}
          onChange={handleTabChange}
          sx={{
            '& .MuiTabs-indicator': {
              backgroundColor: '#9333ea',
            },
            '& .MuiTab-root': {
              color: '#9ca3af',
              textTransform: 'none',
              fontSize: '0.875rem',
              fontWeight: 500,
              minHeight: 48,
              '&.Mui-selected': {
                color: '#9333ea',
              },
              '&:hover': {
                color: '#d8b4fe',
              }
            }
          }}
        >
          <Tab label="Overview" />
          <Tab label="Actions" />
          <Tab label="Batch History" />
        </Tabs>
      </Box>

      {/* Tab Content */}
      <Box>
        {activeTab === 0 && <OverviewTab />}
        {activeTab === 1 && <ActionsTab />}
        {activeTab === 2 && <BatchHistoryTab />}
      </Box>
    </Container>
  );
}
