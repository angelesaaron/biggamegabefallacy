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
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" sx={{ color: 'white', fontWeight: 500 }}>
          System Status
        </Typography>
      </Box>

      {/* Tabs */}
      <Box sx={{ borderBottom: 1, borderColor: '#1f2937', mb: 3 }}>
        <Tabs
          value={activeTab}
          onChange={handleTabChange}
          sx={{
            minHeight: 44,
            '& .MuiTabs-indicator': {
              backgroundColor: '#9333ea',
              height: 2,
            },
            '& .MuiTab-root': {
              color: '#9ca3af',
              textTransform: 'none',
              fontSize: '0.875rem',
              fontWeight: 500,
              minHeight: 44,
              px: 2,
              '&.Mui-selected': {
                color: '#9333ea',
              },
              '&:hover': {
                color: '#a855f7',
              }
            }
          }}
        >
          <Tab label="Overview" />
          <Tab label="Actions" />
          <Tab label="History" />
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
