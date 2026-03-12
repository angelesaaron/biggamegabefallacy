'use client';

import { useState } from 'react';
import OverviewTab from '@/components/system-status/OverviewTab';
import ActionsTab from '@/components/system-status/ActionsTab';
import BatchHistoryTab from '@/components/system-status/BatchHistoryTab';

const TABS = ['Overview', 'Actions', 'History'];

export default function SystemStatus() {
  const [activeTab, setActiveTab] = useState(0);

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-4">
        <h2 className="text-xl font-medium text-white">System Status</h2>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-sr-border mb-6">
        {TABS.map((label, i) => (
          <button
            key={label}
            onClick={() => setActiveTab(i)}
            className={
              activeTab === i
                ? 'px-4 py-2 text-sm font-medium text-sr-primary border-b-2 border-sr-primary transition-colors'
                : 'px-4 py-2 text-sm font-medium text-sr-text-muted hover:text-white transition-colors'
            }
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div>
        {activeTab === 0 && <OverviewTab />}
        {activeTab === 1 && <ActionsTab />}
        {activeTab === 2 && <BatchHistoryTab />}
      </div>
    </div>
  );
}
