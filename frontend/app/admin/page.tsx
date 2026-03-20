'use client';

import { useState, useEffect, useCallback } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useIsAdmin, useAuth } from '@/hooks/useAuth';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? '';

type Panel = 'accounts' | 'health' | 'pipeline' | 'week-override';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface UserRow {
  id: string;
  email: string;
  is_subscriber: boolean;
  is_active: boolean;
  has_stripe: boolean;
  created_at: string;
}

interface GrantResult {
  created: boolean;
  user_id: string;
  email: string;
}

interface WeekSummary {
  game_logs_ingested: number;
  features_computed: number;
  predictions_generated: number;
  odds_available: number;
  players_with_game_logs: number;
  players_missing_game_logs: number;
}

interface HealthData {
  season: number;
  week: number;
  counts: Record<string, number>;
  last_updated: Record<string, string | null>;
  missing_game_log_players: { player_id: string; name: string | null }[];
  week_summary: WeekSummary;
  recent_data_quality_events: {
    id: string;
    event_type: string;
    detail: string | null;
    created_at: string;
  }[];
  available_weeks: { season: number; week: number }[];
}

interface ActionResult {
  status: string;
  n_written: number;
  n_updated: number;
  n_skipped: number;
  n_failed: number;
  events: string[];
}

interface WeekOverrideData {
  override_active: boolean;
  season: number | null;
  week: number | null;
}

interface PreSeasonStepResult {
  step: string;
  status: 'ok' | 'partial' | 'failed' | 'skipped';
  n_written: number;
  n_updated: number;
  n_failed: number;
  events: string[];
}

interface PreSeasonSetupResponse {
  new_season: number;
  prior_season: number;
  overall_status: 'ok' | 'partial' | 'failed';
  steps: PreSeasonStepResult[];
  errors: string[];
}

// ---------------------------------------------------------------------------
// Accounts Panel
// ---------------------------------------------------------------------------

function AccountsPanel() {
  const { getToken } = useAuth();
  const [users, setUsers] = useState<UserRow[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Grant access state
  const [grantEmail, setGrantEmail] = useState('');
  const [grantLoading, setGrantLoading] = useState(false);
  const [grantResult, setGrantResult] = useState<GrantResult | null>(null);
  const [grantError, setGrantError] = useState<string | null>(null);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = getToken();
      const url = search.trim()
        ? `${API_URL}/api/admin-ui/users?search=${encodeURIComponent(search.trim())}`
        : `${API_URL}/api/admin-ui/users`;
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`Failed to load users: ${res.status}`);
      const data = await res.json() as { users: UserRow[]; total: number };
      setUsers(data.users);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load users');
    } finally {
      setLoading(false);
    }
  }, [getToken, search]);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  async function toggleSubscriber(user: UserRow) {
    const prev = user.is_subscriber;
    setUsers((u) => u.map((x) => x.id === user.id ? { ...x, is_subscriber: !prev } : x));
    try {
      const token = getToken();
      const res = await fetch(`${API_URL}/api/admin-ui/users/${user.id}/subscriber`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Toggle failed');
      const updated = await res.json() as { is_subscriber: boolean; is_active: boolean };
      setUsers((u) => u.map((x) => x.id === user.id ? { ...x, is_subscriber: updated.is_subscriber } : x));
    } catch {
      setUsers((u) => u.map((x) => x.id === user.id ? { ...x, is_subscriber: prev } : x));
    }
  }

  async function toggleActive(user: UserRow) {
    const prev = user.is_active;
    setUsers((u) => u.map((x) => x.id === user.id ? { ...x, is_active: !prev } : x));
    try {
      const token = getToken();
      const res = await fetch(`${API_URL}/api/admin-ui/users/${user.id}/active`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error('Toggle failed');
      const updated = await res.json() as { is_subscriber: boolean; is_active: boolean };
      setUsers((u) => u.map((x) => x.id === user.id ? { ...x, is_active: updated.is_active } : x));
    } catch {
      setUsers((u) => u.map((x) => x.id === user.id ? { ...x, is_active: prev } : x));
    }
  }

  async function handleGrant() {
    if (!grantEmail.trim()) return;
    setGrantLoading(true);
    setGrantResult(null);
    setGrantError(null);
    try {
      const token = getToken();
      const res = await fetch(`${API_URL}/api/admin-ui/users/grant`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: grantEmail.trim() }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({})) as { detail?: string };
        throw new Error(body.detail ?? 'Grant failed');
      }
      const result = await res.json() as GrantResult;
      setGrantResult(result);
      setGrantEmail('');
      fetchUsers();
    } catch (err) {
      setGrantError(err instanceof Error ? err.message : 'Grant failed');
    } finally {
      setGrantLoading(false);
    }
  }

  const filtered = search.trim()
    ? users.filter((u) => u.email.toLowerCase().includes(search.toLowerCase()))
    : users;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <input
          type="text"
          placeholder="Search by email..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="bg-sr-bg border border-sr-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-sr-text-muted focus:outline-none focus:border-sr-primary w-72"
        />
      </div>

      {loading && <p className="text-sr-text-muted text-sm">Loading...</p>}
      {error && <p className="text-red-400 text-sm">{error}</p>}

      {!loading && !error && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-sr-border text-sr-text-muted text-left">
                <th className="pb-2 pr-4">Email</th>
                <th className="pb-2 pr-4">Subscriber</th>
                <th className="pb-2 pr-4">Active</th>
                <th className="pb-2 pr-4">Stripe</th>
                <th className="pb-2">Joined</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-sr-border">
              {filtered.map((user) => (
                <tr key={user.id} className="py-2">
                  <td className="py-2 pr-4 text-white">{user.email}</td>
                  <td className="py-2 pr-4">
                    <button
                      onClick={() => toggleSubscriber(user)}
                      className={`w-10 h-5 rounded-full transition-colors ${user.is_subscriber ? 'bg-sr-primary' : 'bg-sr-border'}`}
                      title={user.is_subscriber ? 'Subscriber — click to remove' : 'Not subscriber — click to add'}
                    >
                      <span className={`block w-4 h-4 rounded-full bg-white mx-0.5 transition-transform ${user.is_subscriber ? 'translate-x-5' : 'translate-x-0'}`} />
                    </button>
                  </td>
                  <td className="py-2 pr-4">
                    <button
                      onClick={() => toggleActive(user)}
                      className={`w-10 h-5 rounded-full transition-colors ${user.is_active ? 'bg-green-500' : 'bg-sr-border'}`}
                      title={user.is_active ? 'Active — click to disable' : 'Inactive — click to enable'}
                    >
                      <span className={`block w-4 h-4 rounded-full bg-white mx-0.5 transition-transform ${user.is_active ? 'translate-x-5' : 'translate-x-0'}`} />
                    </button>
                  </td>
                  <td className="py-2 pr-4 text-sr-text-muted">{user.has_stripe ? 'Yes' : '—'}</td>
                  <td className="py-2 text-sr-text-muted">{new Date(user.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && <p className="text-sr-text-muted text-sm mt-4">No users found.</p>}
        </div>
      )}

      {/* Grant Access */}
      <div className="border-t border-sr-border pt-6">
        <h3 className="text-white font-medium mb-3">Grant Access</h3>
        <div className="flex items-center gap-3">
          <input
            type="email"
            placeholder="user@example.com"
            value={grantEmail}
            onChange={(e) => setGrantEmail(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleGrant()}
            className="bg-sr-bg border border-sr-border rounded-lg px-3 py-2 text-sm text-white placeholder:text-sr-text-muted focus:outline-none focus:border-sr-primary w-72"
          />
          <button
            onClick={handleGrant}
            disabled={grantLoading || !grantEmail.trim()}
            className="px-4 py-2 bg-sr-primary text-white text-sm rounded-lg hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {grantLoading ? 'Granting...' : 'Grant'}
          </button>
        </div>
        {grantError && <p className="text-red-400 text-sm mt-2">{grantError}</p>}
        {grantResult && (
          <div className="mt-3 p-3 border border-sr-border rounded-lg text-sm">
            {grantResult.created ? (
              <p className="text-green-400 font-medium">Account created — reset link sent to {grantResult.email}</p>
            ) : (
              <p className="text-green-400">Access granted to existing account: {grantResult.email}</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// DB Health Panel
// ---------------------------------------------------------------------------

function HealthPanel() {
  const { getToken } = useAuth();
  const [data, setData] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [selectedSeason, setSelectedSeason] = useState<number | null>(null);
  const [selectedWeek, setSelectedWeek] = useState<number | null>(null);
  const [availableWeeks, setAvailableWeeks] = useState<{ season: number; week: number }[]>([]);

  const fetchHealth = useCallback(async (season?: number, week?: number) => {
    const s = season ?? (selectedSeason ?? undefined);
    const w = week ?? (selectedWeek ?? undefined);
    setLoading(true);
    setError(null);
    try {
      const token = getToken();
      const params = new URLSearchParams();
      if (s !== undefined) params.set('season', String(s));
      if (w !== undefined) params.set('week', String(w));
      const url = `${API_URL}/api/admin-ui/health${params.size ? '?' + params.toString() : ''}`;
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`Failed to load health: ${res.status}`);
      const d = await res.json() as HealthData;
      setData(d);
      setAvailableWeeks(d.available_weeks);
      setSelectedSeason(d.season);
      setSelectedWeek(d.week);
      setLastRefresh(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load health data');
    } finally {
      setLoading(false);
    }
  }, [getToken, selectedSeason, selectedWeek]);

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 60_000);
    return () => clearInterval(interval);
  }, [fetchHealth]);

  const currentIdx = availableWeeks.findIndex(
    (w) => w.season === data?.season && w.week === data?.week
  );
  const canPrev = currentIdx < availableWeeks.length - 1 && currentIdx !== -1;
  const canNext = currentIdx > 0;
  const prevWeek = canPrev ? availableWeeks[currentIdx + 1] : null;
  const nextWeek = canNext ? availableWeeks[currentIdx - 1] : null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        {/* Week navigator — same style as PlayerWeekToggle */}
        <div className="flex items-center gap-2 bg-sr-surface/60 border border-sr-border/50 rounded-lg p-1">
          <button
            onClick={() => prevWeek && fetchHealth(prevWeek.season, prevWeek.week)}
            disabled={loading || !canPrev}
            className={`p-2 rounded-md transition-all ${
              loading || !canPrev
                ? 'text-sr-text-dim cursor-not-allowed'
                : 'text-sr-text-muted hover:text-white hover:bg-sr-border/30'
            }`}
            aria-label="Previous week"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <div className="px-4 py-1 text-sm text-white min-w-[140px] text-center">
            {data ? (
              <>
                <span className="text-sr-text-muted">Season {data.season}, </span>
                <span className="font-semibold">Week {data.week}</span>
              </>
            ) : (
              <span className="text-sr-text-muted">Loading...</span>
            )}
          </div>
          <button
            onClick={() => nextWeek && fetchHealth(nextWeek.season, nextWeek.week)}
            disabled={loading || !canNext}
            className={`p-2 rounded-md transition-all ${
              loading || !canNext
                ? 'text-sr-text-dim cursor-not-allowed'
                : 'text-sr-text-muted hover:text-white hover:bg-sr-border/30'
            }`}
            aria-label="Next week"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        {/* Refresh + last refresh */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => fetchHealth()}
            disabled={loading}
            className="px-3 py-1.5 border border-sr-border text-sm text-white rounded-lg hover:border-sr-primary transition-colors disabled:opacity-50"
          >
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
          {lastRefresh && (
            <span className="text-sr-text-muted text-xs">
              Last refresh: {lastRefresh.toLocaleTimeString()}
            </span>
          )}
        </div>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {data && (
        <>
          {/* Record Counts */}
          <div>
            <h4 className="text-sr-text-muted text-xs uppercase tracking-wide mb-3">Record Counts</h4>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {Object.entries(data.counts).map(([table, count]) => (
                <div key={table} className="border border-sr-border rounded-lg p-3">
                  <p className="text-sr-text-muted text-xs">{table.replace(/_/g, ' ')}</p>
                  <p className="text-white font-mono text-lg tabular-nums">{count.toLocaleString()}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Week Summary */}
          <div>
            <h4 className="text-sr-text-muted text-xs uppercase tracking-wide mb-3">Week Summary</h4>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {[
                { label: 'Game Logs Ingested', value: data.week_summary.game_logs_ingested },
                { label: 'Features Computed', value: data.week_summary.features_computed },
                { label: 'Predictions Generated', value: data.week_summary.predictions_generated },
                { label: 'Odds Available', value: data.week_summary.odds_available },
                { label: 'Players w/ Game Logs', value: data.week_summary.players_with_game_logs },
                { label: 'Players Missing Logs', value: data.week_summary.players_missing_game_logs },
              ].map(({ label, value }) => (
                <div key={label} className="border border-sr-border rounded-lg p-3">
                  <p className="text-sr-text-muted text-xs">{label}</p>
                  <p className="text-white font-mono text-lg tabular-nums">{value.toLocaleString()}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Last Updated */}
          <div>
            <h4 className="text-sr-text-muted text-xs uppercase tracking-wide mb-3">Last Updated</h4>
            <div className="border border-sr-border rounded-lg divide-y divide-sr-border text-sm">
              {Object.entries(data.last_updated).map(([table, ts]) => (
                <div key={table} className="flex items-center justify-between px-4 py-2">
                  <span className="text-sr-text-muted">{table.replace(/_/g, ' ')}</span>
                  <span className="text-white tabular-nums font-mono text-xs">
                    {ts ? new Date(ts).toLocaleString() : '—'}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Missing Game Log Players */}
          {data.missing_game_log_players.length > 0 && (
            <div>
              <h4 className="text-sr-text-muted text-xs uppercase tracking-wide mb-3">
                Players Missing Game Logs — Week {data.week} ({data.missing_game_log_players.length})
              </h4>
              <div className="border border-sr-border rounded-lg divide-y divide-sr-border text-sm max-h-48 overflow-y-auto">
                {data.missing_game_log_players.map((p) => (
                  <div key={p.player_id} className="px-4 py-2 flex items-center gap-3">
                    <span className="text-white">{p.name ?? p.player_id}</span>
                    <span className="text-sr-text-muted text-xs font-mono">{p.player_id}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recent Data Quality Events */}
          <div>
            <h4 className="text-sr-text-muted text-xs uppercase tracking-wide mb-3">Recent Data Quality Events</h4>
            {data.recent_data_quality_events.length === 0 ? (
              <p className="text-sr-text-muted text-sm">No events.</p>
            ) : (
              <div className="border border-sr-border rounded-lg divide-y divide-sr-border text-sm">
                {data.recent_data_quality_events.map((e) => (
                  <div key={e.id} className="px-4 py-2">
                    <div className="flex items-center justify-between">
                      <span className="text-white font-mono text-xs">{e.event_type}</span>
                      <span className="text-sr-text-muted text-xs tabular-nums">
                        {new Date(e.created_at).toLocaleString()}
                      </span>
                    </div>
                    {e.detail && <p className="text-sr-text-muted text-xs mt-0.5">{e.detail}</p>}
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pipeline Panel
// ---------------------------------------------------------------------------

function ResultCard({ result }: { result: ActionResult }) {
  const badgeColor =
    result.status === 'completed' || result.status === 'ok'
      ? 'text-green-400 bg-green-400/10 border-green-400/30'
      : result.status === 'partial'
      ? 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30'
      : 'text-red-400 bg-red-400/10 border-red-400/30';

  return (
    <div className="mt-2 p-3 border border-sr-border rounded-lg text-xs space-y-1.5">
      <span className={`inline-block px-2 py-0.5 rounded border text-xs font-mono ${badgeColor}`}>
        {result.status}
      </span>
      <div className="flex gap-4 text-sr-text-muted font-mono tabular-nums">
        <span>written: {result.n_written}</span>
        <span>updated: {result.n_updated}</span>
        <span>skipped: {result.n_skipped}</span>
        <span>failed: {result.n_failed}</span>
      </div>
      {result.events.length > 0 && (
        <ul className="text-sr-text-muted space-y-0.5 max-h-24 overflow-y-auto">
          {result.events.map((e, i) => (
            <li key={i} className="truncate">{e}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

interface RunEntry {
  id: string;
  action: string;
  season?: number;
  week?: number;
  status: 'running' | 'completed' | 'partial' | 'failed' | 'error';
  result?: ActionResult;
  preSeasonResult?: PreSeasonSetupResponse;
  errorMessage?: string;
  startedAt: Date;
  completedAt?: Date;
}

const INPUT_CLS =
  'bg-transparent border-b border-sr-border px-1 py-0.5 text-sm font-mono text-white w-16 focus:outline-none focus:border-sr-primary';

const GHOST_BTN =
  'px-2 py-1 text-xs border border-sr-border text-sr-text-muted rounded hover:border-sr-primary hover:text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed';

const SECTION_LABEL = 'text-[10px] tracking-widest uppercase text-sr-text-dim';

function PipelinePanel() {
  const { getToken } = useAuth();
  const [runs, setRuns] = useState<RunEntry[]>([]);
  const [season, setSeason] = useState(2025);
  const [week, setWeek] = useState(1);
  const [runningAction, setRunningAction] = useState<string | null>(null);
  const [preSeasonNewSeason, setPreSeasonNewSeason] = useState(2026);
  const [preSeasonPriorSeason, setPreSeasonPriorSeason] = useState(2025);

  async function trigger(action: string, url: string, params: { season?: number; week?: number }) {
    const id = crypto.randomUUID();
    const entry: RunEntry = {
      id,
      action,
      season: params.season,
      week: params.week,
      status: 'running',
      startedAt: new Date(),
    };
    setRuns((prev) => [entry, ...prev]);
    setRunningAction(action);
    try {
      const token = getToken();
      const res = await fetch(`${API_URL}${url}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({})) as { detail?: string };
        throw new Error(body.detail ?? `Request failed: ${res.status}`);
      }
      const data = await res.json() as ActionResult;
      const resolved: RunEntry['status'] =
        data.status === 'completed' || data.status === 'ok'
          ? 'completed'
          : data.status === 'partial'
          ? 'partial'
          : 'failed';
      setRuns((prev) =>
        prev.map((r) =>
          r.id === id ? { ...r, status: resolved, result: data, completedAt: new Date() } : r
        )
      );
    } catch (err) {
      setRuns((prev) =>
        prev.map((r) =>
          r.id === id
            ? {
                ...r,
                status: 'error',
                errorMessage: err instanceof Error ? err.message : 'Failed',
                completedAt: new Date(),
              }
            : r
        )
      );
    } finally {
      setRunningAction(null);
    }
  }

  async function triggerPreSeason() {
    const id = crypto.randomUUID();
    const entry: RunEntry = {
      id,
      action: 'Pre-Season Setup',
      season: preSeasonNewSeason,
      status: 'running',
      startedAt: new Date(),
    };
    setRuns((prev) => [entry, ...prev]);
    setRunningAction('Pre-Season Setup');
    try {
      const token = getToken();
      const res = await fetch(`${API_URL}/api/admin-ui/pipeline/preseason-setup`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          new_season: preSeasonNewSeason,
          prior_season: preSeasonPriorSeason,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({})) as { detail?: string };
        throw new Error(body.detail ?? `Request failed: ${res.status}`);
      }
      const data = await res.json() as PreSeasonSetupResponse;
      const resolved: RunEntry['status'] =
        data.overall_status === 'ok' ? 'completed'
        : data.overall_status === 'partial' ? 'partial'
        : 'failed';
      setRuns((prev) =>
        prev.map((r) =>
          r.id === id
            ? { ...r, status: resolved, preSeasonResult: data, completedAt: new Date() }
            : r
        )
      );
    } catch (err) {
      setRuns((prev) =>
        prev.map((r) =>
          r.id === id
            ? {
                ...r,
                status: 'error',
                errorMessage: err instanceof Error ? err.message : 'Failed',
                completedAt: new Date(),
              }
            : r
        )
      );
    } finally {
      setRunningAction(null);
    }
  }

  const busy = runningAction !== null;

  return (
    <div className="flex h-full min-h-0">
      {/* Left column */}
      <div className="w-[280px] shrink-0 border-r border-sr-border pr-5 space-y-5">
        {/* Shared season/week selector */}
        <div className="flex items-center gap-2 pt-1">
          <span className="text-xs text-sr-text-muted font-mono">Season</span>
          <input
            type="number"
            value={season}
            onChange={(e) => setSeason(Number(e.target.value))}
            min={2020}
            max={2035}
            className={INPUT_CLS}
          />
          <span className="text-xs text-sr-text-muted font-mono ml-2">Week</span>
          <input
            type="number"
            value={week}
            onChange={(e) => setWeek(Number(e.target.value))}
            min={1}
            max={18}
            className={INPUT_CLS}
          />
        </div>

        {/* COMPUTE section */}
        <div className="space-y-2">
          <p className={SECTION_LABEL}>Compute</p>
          <div className="border-t border-sr-border" />

          {/* Compute Features */}
          <div className="flex items-center gap-2 py-0.5">
            <button
              disabled={busy}
              onClick={() =>
                trigger('Compute Features', `/api/admin-ui/pipeline/features/${season}/${week}`, { season, week })
              }
              className={GHOST_BTN}
              aria-label="Run Compute Features"
            >
              {runningAction === 'Compute Features' ? (
                <span className="inline-block w-2 h-2 rounded-full bg-current animate-pulse" />
              ) : (
                '▶ run'
              )}
            </button>
            <span className="text-sm text-white flex-1">Compute Features</span>
            <span className="text-[10px] text-sr-text-dim">DB only</span>
          </div>

          {/* Run Predictions */}
          <div className="flex items-center gap-2 py-0.5">
            <button
              disabled={busy}
              onClick={() =>
                trigger('Run Predictions', `/api/admin-ui/pipeline/predictions/${season}/${week}`, { season, week })
              }
              className={GHOST_BTN}
              aria-label="Run Predictions"
            >
              {runningAction === 'Run Predictions' ? (
                <span className="inline-block w-2 h-2 rounded-full bg-current animate-pulse" />
              ) : (
                '▶ run'
              )}
            </button>
            <span className="text-sm text-white flex-1">Run Predictions</span>
            <span className="text-[10px] text-sr-text-dim">DB only</span>
          </div>
        </div>

        {/* SYNC section */}
        <div className="space-y-2">
          <p className={SECTION_LABEL}>Sync</p>
          <div className="border-t border-sr-border" />

          {/* Roster */}
          <div className="flex items-center gap-2 py-0.5">
            <button
              disabled={busy}
              onClick={() => trigger('Roster', '/api/admin-ui/pipeline/roster', {})}
              className={GHOST_BTN}
              aria-label="Sync Roster"
            >
              {runningAction === 'Roster' ? (
                <span className="inline-block w-2 h-2 rounded-full bg-current animate-pulse" />
              ) : (
                '▶ run'
              )}
            </button>
            <span className="text-sm text-white flex-1">Roster</span>
            <span className="text-[10px] text-sr-text-dim">ext. API</span>
          </div>

          {/* Schedule */}
          <div className="flex items-center gap-2 py-0.5">
            <button
              disabled={busy}
              onClick={() =>
                trigger('Schedule', `/api/admin-ui/pipeline/schedule/${season}`, { season })
              }
              className={GHOST_BTN}
              aria-label="Sync Schedule"
            >
              {runningAction === 'Schedule' ? (
                <span className="inline-block w-2 h-2 rounded-full bg-current animate-pulse" />
              ) : (
                '▶ run'
              )}
            </button>
            <span className="text-sm text-white flex-1">Schedule</span>
            <span className="text-[10px] text-sr-text-dim">ext. API</span>
          </div>

          {/* Game Logs */}
          <div className="flex items-center gap-2 py-0.5">
            <button
              disabled={busy}
              onClick={() =>
                trigger('Game Logs', `/api/admin-ui/pipeline/gamelogs/${season}/${week}`, { season, week })
              }
              className={GHOST_BTN}
              aria-label="Sync Game Logs"
            >
              {runningAction === 'Game Logs' ? (
                <span className="inline-block w-2 h-2 rounded-full bg-current animate-pulse" />
              ) : (
                '▶ run'
              )}
            </button>
            <span className="text-sm text-white flex-1">Game Logs</span>
            <span className="text-[10px] text-sr-text-dim">ext. API</span>
          </div>

          {/* Odds */}
          <div className="flex items-center gap-2 py-0.5">
            <button
              disabled={busy}
              onClick={() =>
                trigger('Odds', `/api/admin-ui/pipeline/odds/${season}/${week}`, { season, week })
              }
              className={GHOST_BTN}
              aria-label="Sync Odds"
            >
              {runningAction === 'Odds' ? (
                <span className="inline-block w-2 h-2 rounded-full bg-current animate-pulse" />
              ) : (
                '▶ run'
              )}
            </button>
            <span className="text-sm text-white flex-1">Odds</span>
            <span className="text-[10px] text-sr-text-dim">ext. API</span>
          </div>
        </div>

        {/* SETUP section */}
        <div className="space-y-2">
          <p className={SECTION_LABEL}>Setup</p>
          <div className="border-t border-sr-border" />

          {/* Season inputs */}
          <div className="space-y-1.5 py-0.5">
            <div className="flex items-center gap-2">
              <span className="text-xs text-sr-text-muted font-mono w-20">New season</span>
              <input
                type="number"
                value={preSeasonNewSeason}
                onChange={(e) => setPreSeasonNewSeason(Number(e.target.value))}
                min={2020}
                max={2035}
                className={INPUT_CLS}
              />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-sr-text-muted font-mono w-20">Prior season</span>
              <input
                type="number"
                value={preSeasonPriorSeason}
                onChange={(e) => setPreSeasonPriorSeason(Number(e.target.value))}
                min={2019}
                max={2034}
                className={INPUT_CLS}
              />
            </div>
            {preSeasonPriorSeason !== preSeasonNewSeason - 1 && (
              <p className="text-[10px] text-red-400 font-mono">
                Prior must equal new − 1
              </p>
            )}
          </div>

          {/* Pre-Season Setup button */}
          <div className="flex items-center gap-2 py-0.5">
            <button
              disabled={busy || preSeasonPriorSeason !== preSeasonNewSeason - 1}
              onClick={() => triggerPreSeason()}
              className={GHOST_BTN}
              aria-label="Run Pre-Season Setup"
            >
              {runningAction === 'Pre-Season Setup' ? (
                <span className="inline-block w-2 h-2 rounded-full bg-current animate-pulse" />
              ) : (
                '▶ run'
              )}
            </button>
            <span className="text-sm text-white flex-1">Pre-Season Setup</span>
            <span className="text-[10px] text-sr-text-dim">ext. API</span>
          </div>
        </div>
      </div>

      {/* Right column — Run Log */}
      <div className="flex-1 pl-5 min-w-0 space-y-1">
        {/* Header */}
        <div className="flex items-center justify-between pb-1">
          <p className={SECTION_LABEL}>Run Log</p>
          {runs.length > 0 && (
            <button
              onClick={() => setRuns([])}
              className="text-[10px] text-sr-text-dim hover:text-sr-text-muted transition-colors border border-sr-border px-2 py-0.5 rounded"
            >
              Clear
            </button>
          )}
        </div>
        <div className="border-t border-sr-border" />

        {runs.length === 0 ? (
          <p className="text-sr-text-dim text-xs font-mono pt-4 text-center">No runs this session.</p>
        ) : (
          <div className="space-y-0 overflow-y-auto max-h-[calc(100vh-18rem)]">
            {runs.map((run) => (
              <RunLogEntry key={run.id} run={run} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function RunLogEntry({ run }: { run: RunEntry }) {
  const contextParts: string[] = [];
  if (run.season !== undefined) contextParts.push(`S${run.season}`);
  if (run.week !== undefined) contextParts.push(`W${run.week}`);
  const context = contextParts.join(' ');

  const statusColor =
    run.status === 'completed'
      ? 'text-green-400'
      : run.status === 'partial'
      ? 'text-yellow-400'
      : run.status === 'running'
      ? 'text-sr-text-dim'
      : 'text-red-400';

  if (run.status === 'running') {
    return (
      <div className="border-t border-sr-border pt-2 mt-2">
        <p className={`text-xs font-mono ${statusColor} animate-pulse`}>
          ▶ {run.action} {context} running...
        </p>
      </div>
    );
  }

  return (
    <div className="border-t border-sr-border pt-2 mt-2">
      <div className="flex items-baseline justify-between gap-2">
        <div className="flex items-baseline gap-2 min-w-0">
          <span className="text-sm text-white font-medium truncate">{run.action}</span>
          {context && (
            <span className="text-xs text-sr-text-dim font-mono shrink-0">{context}</span>
          )}
        </div>
        {run.completedAt && (
          <span className="text-xs text-sr-text-dim font-mono shrink-0">
            {run.completedAt.toLocaleTimeString()}
          </span>
        )}
      </div>

      {run.result && (
        <>
          <p className={`text-xs font-mono ${statusColor}`}>status: {run.result.status}</p>
          <p className="text-xs font-mono text-sr-text-muted">
            written {run.result.n_written}&nbsp;&nbsp;updated {run.result.n_updated}&nbsp;&nbsp;skipped {run.result.n_skipped}&nbsp;&nbsp;failed {run.result.n_failed}
          </p>
          {run.result.events.length > 0 && (
            <ul className="space-y-0.5">
              {run.result.events.map((e, i) => (
                <li key={i} className="text-xs font-mono text-sr-text-dim truncate">
                  · {e}
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      {run.preSeasonResult && (
        <div className="space-y-0.5 mt-1">
          {run.preSeasonResult.steps.map((step) => {
            const stepColor =
              step.status === 'ok' ? 'text-green-400'
              : step.status === 'partial' ? 'text-yellow-400'
              : step.status === 'skipped' ? 'text-sr-text-dim'
              : 'text-red-400';
            return (
              <div key={step.step} className="flex items-baseline gap-2">
                <span className={`text-xs font-mono ${stepColor}`}>{step.status}</span>
                <span className="text-xs font-mono text-sr-text-muted">{step.step.replace(/_/g, ' ')}</span>
                <span className="text-xs font-mono text-sr-text-dim">
                  +{step.n_written} ~{step.n_updated} ✗{step.n_failed}
                </span>
              </div>
            );
          })}
          {run.preSeasonResult.errors.length > 0 && (
            <ul className="space-y-0.5 mt-1">
              {run.preSeasonResult.errors.map((e, i) => (
                <li key={i} className="text-xs font-mono text-red-400 truncate">· {e}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {(run.status === 'error' || run.status === 'failed') && run.errorMessage && (
        <p className="text-xs font-mono text-red-400">{run.errorMessage}</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pipeline Week Status component
// ---------------------------------------------------------------------------

function PipelineWeekStatus() {
  const { getToken } = useAuth();
  const [data, setData] = useState<{ active: boolean; season: number | null; week: number | null; updated_at: string | null } | null>(null);
  const [clearing, setClearing] = useState(false);

  useEffect(() => {
    async function fetch_() {
      const token = getToken();
      const res = await fetch(`${API_URL}/api/admin-ui/active-display-week`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setData(await res.json());
    }
    fetch_();
  }, [getToken]);

  async function handleClear() {
    setClearing(true);
    const token = getToken();
    const res = await fetch(`${API_URL}/api/admin-ui/active-display-week`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) setData(await res.json());
    setClearing(false);
  }

  if (!data) return <p className="text-xs font-mono text-sr-text-dim">Loading...</p>;

  if (!data.active) {
    return <p className="text-xs font-mono text-sr-text-muted">Not set (pipeline hasn&apos;t run)</p>;
  }

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className="text-sm font-mono text-white">S{data.season} W{data.week}</span>
      {data.updated_at && (
        <span className="text-[10px] text-sr-text-dim font-mono">
          {new Date(data.updated_at).toLocaleString()}
        </span>
      )}
      <button
        onClick={handleClear}
        disabled={clearing}
        className="text-xs text-sr-text-dim hover:text-red-400 underline transition-colors disabled:opacity-50 ml-1"
      >
        {clearing ? 'clearing...' : 'clear'}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Week Override Panel
// ---------------------------------------------------------------------------

function WeekOverridePanel() {
  const { getToken } = useAuth();
  const [data, setData] = useState<WeekOverrideData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [season, setSeason] = useState<number>(2025);
  const [week, setWeek] = useState<number>(1);
  const [saving, setSaving] = useState(false);
  const [clearing, setClearing] = useState(false);

  const fetchOverride = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = getToken();
      const res = await fetch(`${API_URL}/api/admin-ui/week-override`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`Failed: ${res.status}`);
      const d = await res.json() as WeekOverrideData;
      setData(d);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load override');
    } finally {
      setLoading(false);
    }
  }, [getToken]);

  useEffect(() => { fetchOverride(); }, [fetchOverride]);

  async function handleSet() {
    setSaving(true);
    setError(null);
    try {
      const token = getToken();
      const res = await fetch(`${API_URL}/api/admin-ui/week-override`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ season, week }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({})) as { detail?: string };
        throw new Error(body.detail ?? 'Failed to set override');
      }
      const d = await res.json() as WeekOverrideData;
      setData(d);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed');
    } finally {
      setSaving(false);
    }
  }

  async function handleClear() {
    setClearing(true);
    setError(null);
    try {
      const token = getToken();
      const res = await fetch(`${API_URL}/api/admin-ui/week-override`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`Failed: ${res.status}`);
      const d = await res.json() as WeekOverrideData;
      setData(d);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed');
    } finally {
      setClearing(false);
    }
  }

  return (
    <div className="space-y-5 max-w-sm">
      {/* CURRENT WEEK */}
      <div>
        <p className={SECTION_LABEL}>Current Week</p>
        <div className="border-t border-sr-border my-2" />
        {loading && (
          <p className="text-sm font-mono text-sr-text-muted">Loading...</p>
        )}
        {!loading && data && (
          data.override_active ? (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-mono text-white">Override active</span>
              <span className="text-sr-text-dim">·</span>
              <span className="text-xs font-mono text-sr-primary">
                S{data.season} W{data.week}
              </span>
              <button
                onClick={handleClear}
                disabled={clearing}
                className="text-xs text-sr-text-dim hover:text-red-400 underline transition-colors disabled:opacity-50 ml-1"
              >
                {clearing ? 'clearing...' : 'clear'}
              </button>
            </div>
          ) : (
            <p className="text-sm font-mono text-sr-text-muted">
              Auto-detected (no override active)
            </p>
          )
        )}
        {error && <p className="text-red-400 text-xs font-mono mt-1">{error}</p>}
      </div>

      {/* SET OVERRIDE */}
      <div>
        <p className={SECTION_LABEL}>Set Override</p>
        <div className="border-t border-sr-border my-2" />
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-sr-text-muted font-mono">Season</span>
          <input
            type="number"
            value={season}
            onChange={(e) => setSeason(Number(e.target.value))}
            min={2020}
            max={2035}
            className={INPUT_CLS}
          />
          <span className="text-xs text-sr-text-muted font-mono ml-1">Week</span>
          <input
            type="number"
            value={week}
            onChange={(e) => setWeek(Number(e.target.value))}
            min={1}
            max={22}
            className={INPUT_CLS}
          />
          <button
            onClick={handleSet}
            disabled={saving}
            className="px-3 py-1 text-xs border border-sr-border text-sr-text-muted rounded hover:border-sr-primary hover:text-white transition-colors disabled:opacity-50 ml-1"
          >
            {saving ? 'applying...' : 'apply'}
          </button>
        </div>
      </div>

      {/* Pipeline week */}
      <div>
        <p className={SECTION_LABEL}>Pipeline Set</p>
        <div className="border-t border-sr-border my-2" />
        <PipelineWeekStatus />
      </div>

      <p className="text-[10px] text-sr-text-dim font-mono mt-4">
        · Overrides the week the app and pipeline consider &quot;current&quot;.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Admin Page
// ---------------------------------------------------------------------------

export default function AdminPage() {
  const isAdmin = useIsAdmin();
  const [activePanel, setActivePanel] = useState<Panel>('accounts');

  const sidebarItems: { id: Panel; label: string }[] = [
    { id: 'accounts', label: 'Accounts' },
    { id: 'health', label: 'DB Health' },
    { id: 'pipeline', label: 'Pipeline' },
    { id: 'week-override', label: 'Week Override' },
  ];

  if (!isAdmin) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <p className="text-sr-text-muted">You do not have permission to view this page.</p>
      </div>
    );
  }

  return (
    <div className="flex gap-6 min-h-[calc(100vh-8rem)]">
      {/* Sidebar */}
      <nav className="w-48 shrink-0">
        <ul className="space-y-1">
          {sidebarItems.map(({ id, label }) => (
            <li key={id}>
              <button
                onClick={() => setActivePanel(id)}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors capitalize ${
                  activePanel === id
                    ? 'bg-sr-primary/10 text-sr-primary font-medium'
                    : 'text-sr-text-muted hover:text-white'
                }`}
              >
                {label}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {/* Content */}
      <div className="flex-1 min-w-0">
        {activePanel === 'accounts' && <AccountsPanel />}
        {activePanel === 'health' && <HealthPanel />}
        {activePanel === 'pipeline' && <PipelinePanel />}
        {activePanel === 'week-override' && <WeekOverridePanel />}
      </div>
    </div>
  );
}
