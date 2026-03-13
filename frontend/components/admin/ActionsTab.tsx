'use client';

import { useState } from 'react';
import { SurfaceCard } from '@/components/ui/SurfaceCard';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Alert } from '@/components/ui/alert';
import { Loader2 } from 'lucide-react';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? '';

export default function ActionsTab() {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [selectedWeek, setSelectedWeek] = useState<number>(18);
  const [selectedYear, setSelectedYear] = useState<number>(2025);

  const triggerBatchUpdate = async (mode?: string, customWeek?: number, customYear?: number) => {
    if (!password) {
      setResult({ type: 'error', message: 'Admin password is required' });
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      const body: Record<string, unknown> = { password };
      if (customWeek) body.week = customWeek;
      if (customYear) body.year = customYear;
      const response = await fetch(`${API_URL}/api/admin/actions/run-batch-update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await response.json();
      if (response.ok) {
        setResult({ type: 'success', message: `${data.message}. Process ID: ${data.process_id}` });
        setPassword('');
      } else {
        setResult({ type: 'error', message: data.detail || 'Failed to trigger batch update' });
      }
    } catch (error) {
      setResult({ type: 'error', message: error instanceof Error ? error.message : 'Network error' });
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
        setResult({ type: 'success', message: `${data.message}. Process ID: ${data.process_id}` });
        setPassword('');
      } else {
        setResult({ type: 'error', message: data.detail || 'Failed to refresh rosters' });
      }
    } catch (error) {
      setResult({ type: 'error', message: error instanceof Error ? error.message : 'Network error' });
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
      const body: Record<string, unknown> = { password };
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
        setResult({ type: 'success', message: `${data.message}. Process ID: ${data.process_id}` });
        setPassword('');
      } else {
        setResult({ type: 'error', message: data.detail || 'Failed to backfill data' });
      }
    } catch (error) {
      setResult({ type: 'error', message: error instanceof Error ? error.message : 'Network error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Password Input */}
      <SurfaceCard className="p-4">
        <Input
          type="password"
          placeholder="Admin password — required for all actions"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </SurfaceCard>

      {/* Result */}
      {result && (
        <Alert variant={result.type === 'success' ? 'success' : 'destructive'}>
          {result.message}
        </Alert>
      )}

      {/* Quick Actions */}
      <SurfaceCard className="p-6">
        <p className="text-sm font-medium text-white mb-4">Quick Actions</p>
        <div className="flex flex-col md:flex-row gap-3">
          <ActionButton
            title="Run Full Batch Update"
            description="Schedule, logs, predictions, and odds"
            onClick={() => triggerBatchUpdate()}
            loading={loading}
            variant="primary"
          />
          <ActionButton
            title="Refresh Rosters"
            description="Fetch latest player data"
            onClick={triggerRefreshRosters}
            loading={loading}
            variant="secondary"
          />
        </div>
      </SurfaceCard>

      {/* Historical Backfill */}
      <SurfaceCard className="p-6">
        <p className="text-sm font-medium text-white mb-4">Historical Backfill</p>
        <div className="flex gap-3 mb-4">
          <select
            value={selectedWeek}
            onChange={(e) => setSelectedWeek(Number(e.target.value))}
            className="flex-1 h-9 rounded-lg border border-sr-border bg-sr-surface px-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-sr-primary"
          >
            {Array.from({ length: 18 }, (_, i) => i + 1).map((week) => (
              <option key={week} value={week}>Week {week}</option>
            ))}
          </select>
          <select
            value={selectedYear}
            onChange={(e) => setSelectedYear(Number(e.target.value))}
            className="flex-1 h-9 rounded-lg border border-sr-border bg-sr-surface px-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-sr-primary"
          >
            <option value={2024}>2024</option>
            <option value={2025}>2025</option>
            <option value={2026}>2026</option>
          </select>
        </div>
        <div className="flex flex-col md:flex-row gap-3">
          <ActionButton
            title="Backfill Last 5 Weeks"
            description="Current season"
            onClick={() => triggerBackfillComplete(5)}
            loading={loading}
            variant="secondary"
          />
          <ActionButton
            title={`Backfill ${selectedYear} Week ${selectedWeek}`}
            description="Selected week"
            onClick={() => triggerBackfillComplete(undefined, selectedWeek, selectedYear)}
            loading={loading}
            variant="secondary"
          />
        </div>
      </SurfaceCard>

      {/* Advanced Actions */}
      <SurfaceCard className="p-6">
        <p className="text-sm font-medium text-white mb-4">Advanced Actions</p>
        <div className="flex gap-3 mb-4">
          <select
            value={selectedWeek}
            onChange={(e) => setSelectedWeek(Number(e.target.value))}
            className="flex-1 h-9 rounded-lg border border-sr-border bg-sr-surface px-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-sr-primary"
          >
            {Array.from({ length: 18 }, (_, i) => i + 1).map((week) => (
              <option key={week} value={week}>Week {week}</option>
            ))}
          </select>
          <select
            value={selectedYear}
            onChange={(e) => setSelectedYear(Number(e.target.value))}
            className="flex-1 h-9 rounded-lg border border-sr-border bg-sr-surface px-3 text-sm text-white focus:outline-none focus:ring-1 focus:ring-sr-primary"
          >
            <option value={2024}>2024</option>
            <option value={2025}>2025</option>
            <option value={2026}>2026</option>
          </select>
        </div>
        <div className="flex flex-col md:flex-row gap-3">
          <ActionButton
            title="Update Specific Week"
            description={`${selectedYear} Week ${selectedWeek}`}
            onClick={() => triggerBatchUpdate(undefined, selectedWeek, selectedYear)}
            loading={loading}
            variant="secondary"
          />
          <ActionButton
            title="Refresh Odds Only"
            description={`${selectedYear} Week ${selectedWeek}`}
            onClick={() => triggerBatchUpdate('odds_only', selectedWeek, selectedYear)}
            loading={loading}
            variant="secondary"
          />
        </div>
      </SurfaceCard>
    </div>
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
  const cls =
    variant === 'primary'
      ? 'flex-1 flex items-center justify-between px-4 py-3 rounded-lg bg-sr-primary border border-purple-700 text-white text-left hover:bg-sr-primary/90 transition-colors disabled:opacity-60 disabled:cursor-not-allowed'
      : 'flex-1 flex items-center justify-between px-4 py-3 rounded-lg bg-sr-surface border border-sr-border text-white text-left hover:bg-sr-surface-raised transition-colors disabled:opacity-60 disabled:cursor-not-allowed';
  return (
    <button onClick={onClick} disabled={loading} className={cls}>
      <div>
        <p className="text-sm font-medium">{title}</p>
        <p className="text-xs text-sr-text-muted mt-0.5">{description}</p>
      </div>
      {loading && <Loader2 size={16} className="animate-spin ml-3 flex-shrink-0" />}
    </button>
  );
}
