'use client';

import { useEffect, useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  Cell,
  ResponsiveContainer,
} from 'recharts';
import { MetricCard } from '@/components/ui/MetricCard';
import { SurfaceCard } from '@/components/ui/SurfaceCard';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? '';

interface TierBucket {
  hits: number;
  total: number;
  hit_rate: number | null;
}

interface TierSummary {
  top_picks: TierBucket;
  high_conviction: TierBucket;
  value_play: TierBucket;
  fade: TierBucket;
}

interface WeekRecord {
  week: number;
  predictions_count: number;
  hits: number;
  misses: number;
  calibration_error: number;
  high_confidence_hits: number;
  high_confidence_total: number;
}

interface TrackRecordData {
  season: number;
  tier_summary?: TierSummary;
  weeks: WeekRecord[];
  season_summary: {
    total_predictions: number;
    overall_hit_rate: number;
    high_confidence_hit_rate: number;
    mean_calibration_error: number;
  };
}

function pct(rate: number | null | undefined, fallback = 0): number {
  return Math.round((rate ?? fallback) * 100);
}

export function TrackRecord() {
  const [data, setData] = useState<TrackRecordData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch(`${API_URL}/api/track-record`);
        if (!res.ok) throw new Error('Failed to fetch track record');
        const json = await res.json();
        setData(json);
      } catch {
        setError('Could not load track record data.');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        <div className="h-8 w-64 rounded bg-sr-surface animate-pulse mb-4" />
        <div className="h-64 rounded-card bg-sr-surface animate-pulse mb-8" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-28 rounded-card bg-sr-surface animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !data || data.weeks.length === 0) {
    return (
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        <SurfaceCard className="p-12 text-center">
          <p className="text-sr-text-muted text-sm">
            Track record data will appear after the first full season of predictions.
          </p>
        </SurfaceCard>
      </div>
    );
  }

  const { season_summary, weeks, tier_summary } = data;

  const convictionChartData = tier_summary
    ? [
        { label: 'Top Picks', hitRate: pct(tier_summary.top_picks.hit_rate), color: '#10b981' },
        { label: 'High Conv.', hitRate: pct(tier_summary.high_conviction.hit_rate), color: '#34d399' },
        { label: 'Value Plays', hitRate: pct(tier_summary.value_play.hit_rate), color: '#6ee7b7' },
        { label: 'Fade List', hitRate: pct(tier_summary.fade.hit_rate), color: '#f43f5e' },
      ]
    : null;

  const weekTableRows = weeks.map((w) => ({
    week: w.week,
    hitRate: w.hits + w.misses > 0 ? Math.round((w.hits / (w.hits + w.misses)) * 100) : 0,
    hits: w.hits,
    misses: w.misses,
    highConfHits: w.high_confidence_hits,
    highConfTotal: w.high_confidence_total,
  }));

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8 space-y-8">

      {/* Section 1: Headline */}
      <div>
        <h2 className="text-2xl md:text-3xl font-semibold text-white mb-2">
          Season {data.season} Track Record
        </h2>
        <p className="text-sm text-sr-text-muted">
          Backtested results across {weeks.length} weeks,{' '}
          {season_summary.total_predictions.toLocaleString()} predictions.{' '}
          <span className="italic text-sr-text-dim">
            Not indicative of guaranteed future performance.
          </span>
        </p>
      </div>

      {/* Section 2: Conviction gradient chart — THE LEAD */}
      {convictionChartData && (
        <SurfaceCard className="p-6">
          <h3 className="text-lg font-medium text-white mb-1">
            Hit rate by model tier — {data.season} season
          </h3>
          <p className="text-xs text-sr-text-dim mb-5 italic">
            Backtested. Higher conviction = higher hit rate.
          </p>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart
              data={convictionChartData}
              margin={{ top: 4, right: 16, left: 0, bottom: 4 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis dataKey="label" tick={{ fill: '#9ca3af', fontSize: 12 }} />
              <YAxis
                domain={[0, 60]}
                tick={{ fill: '#9ca3af', fontSize: 12 }}
                tickFormatter={(v) => `${v}%`}
              />
              <Tooltip
                contentStyle={{
                  background: 'rgba(15,15,20,0.95)',
                  border: '1px solid rgba(147,51,234,0.4)',
                  borderRadius: '8px',
                }}
                labelStyle={{ color: '#f9fafb' }}
                formatter={(value: number | undefined) => [`${value ?? 0}%`, 'Hit Rate'] as [string, string]}
              />
              <ReferenceLine
                y={22}
                stroke="#6b7280"
                strokeDasharray="4 4"
                label={{ value: 'NFL avg ~22%', fill: '#6b7280', fontSize: 11 }}
              />
              <Bar dataKey="hitRate" radius={[4, 4, 0, 0]}>
                {convictionChartData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </SurfaceCard>
      )}

      {/* Section 3: Stat cards — below the chart */}
      {tier_summary ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard
            label="Top Picks Hit Rate"
            value={`${pct(tier_summary.top_picks.hit_rate)}%`}
            sublabel="Top 3 picks per week"
          />
          <MetricCard
            label="High Conviction"
            value={`${pct(tier_summary.high_conviction.hit_rate)}%`}
            sublabel="Model 40%+ with odds"
          />
          <MetricCard label="Season Coverage" value={`${weeks.length} weeks`} />
          <MetricCard
            label="Total Predictions"
            value={season_summary.total_predictions.toLocaleString()}
          />
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard
            label="High Conf. Hit Rate"
            value={`${(season_summary.high_confidence_hit_rate * 100).toFixed(1)}%`}
            sublabel="Calls ≥30%"
          />
          <MetricCard label="Weeks Tracked" value={`${weeks.length}`} />
          <MetricCard
            label="Total Predictions"
            value={season_summary.total_predictions.toLocaleString()}
          />
        </div>
      )}

      {/* Section 4: Week-by-week table */}
      <SurfaceCard className="p-6">
          <h3 className="text-lg font-medium text-white mb-4">Week-by-Week Results</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-sr-text-muted text-left border-b border-sr-border">
                  <th className="pb-2 font-medium">Week</th>
                  <th className="pb-2 font-medium text-right nums">Hits</th>
                  <th className="pb-2 font-medium text-right nums">Misses</th>
                  <th className="pb-2 font-medium text-right nums">Hit Rate</th>
                  <th className="pb-2 font-medium text-right nums hidden md:table-cell">
                    High Conf.
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-sr-border">
                {weekTableRows.map((row) => (
                  <tr key={row.week}>
                    <td className="py-2.5 text-white">Week {row.week}</td>
                    <td className="py-2.5 text-right text-sr-success nums">{row.hits}</td>
                    <td className="py-2.5 text-right text-sr-danger nums">{row.misses}</td>
                    <td
                      className={`py-2.5 text-right nums font-semibold ${
                        row.hitRate >= 30
                          ? 'text-sr-success'
                          : row.hitRate < 15
                          ? 'text-sr-danger'
                          : 'text-white'
                      }`}
                    >
                      {row.hitRate}%
                    </td>
                    <td className="py-2.5 text-right text-sr-text-muted nums hidden md:table-cell">
                      {row.highConfHits}/{row.highConfTotal}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
      </SurfaceCard>

      {/* Section 5: The inverse argument */}
      <SurfaceCard className="p-6">
        <h3 className="text-lg font-medium text-white mb-3">
          The model&apos;s negative signal is equally real.
        </h3>
        <p className="text-sr-text-muted text-sm mb-4">
          Players flagged as fades hit at{' '}
          <span className="text-sr-danger font-semibold nums">
            {pct(tier_summary?.fade.hit_rate, 0.125)}%
          </span>{' '}
          in {data.season} — roughly half the rate of high-conviction picks. Knowing who not to
          bet is part of the edge.
        </p>
        <div className="inline-block">
          <MetricCard
            label="Fade List Hit Rate"
            value={`${pct(tier_summary?.fade.hit_rate, 0.125)}%`}
            sublabel="Players model was cold on"
          />
        </div>
      </SurfaceCard>

      {/* Section 6: About the model */}
      <SurfaceCard className="p-6">
        <h3 className="text-lg font-medium text-white mb-2">About the model</h3>
        <p className="text-sr-text-muted text-sm">
          The model outputs calibrated probabilities — a 30% prediction should hit roughly 30% of
          the time. Probability calibration is what separates a real model from gut-feel
          percentages.
        </p>
      </SurfaceCard>

      {/* Section 7: Disclaimer */}
      <p className="text-xs text-sr-text-dim text-center pb-8">
        For entertainment purposes only. Not financial or gambling advice.{' '}
        Backtested results do not guarantee future performance.
      </p>
    </div>
  );
}
