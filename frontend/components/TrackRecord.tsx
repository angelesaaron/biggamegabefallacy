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
import { MetricCard } from './ui/MetricCard';
import { SurfaceCard } from './ui/SurfaceCard';
import { PaywallGate } from './PaywallGate';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? '';

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
  weeks: WeekRecord[];
  season_summary: {
    total_predictions: number;
    overall_hit_rate: number;
    high_confidence_hit_rate: number;
    mean_calibration_error: number;
  };
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
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
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
            Track Record data will appear after the first full season of predictions.
          </p>
        </SurfaceCard>
      </div>
    );
  }

  const { season_summary, weeks } = data;

  const chartData = weeks.map((w) => ({
    week: w.week,
    hitRate:
      w.predictions_count > 0
        ? Math.round((w.hits / (w.hits + w.misses || 1)) * 100)
        : 0,
    aboveBaseline:
      w.predictions_count > 0 &&
      w.hits / (w.hits + w.misses || 1) >= 0.33,
  }));

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Section 1: Summary metrics */}
      <div>
        <h2 className="text-2xl font-semibold text-white mb-4">
          Season {data.season} Track Record
        </h2>
        <p className="text-xs text-sr-text-muted mb-4 italic">
          Backtested results — not indicative of live performance
        </p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard
            label="Season Hit Rate"
            value={`${(season_summary.overall_hit_rate * 100).toFixed(1)}%`}
            sublabel="Actionable calls (≥15%)"
          />
          <MetricCard
            label="High Conf. Hit Rate"
            value={`${(season_summary.high_confidence_hit_rate * 100).toFixed(1)}%`}
            sublabel="Calls ≥30%"
          />
          <MetricCard
            label="Weeks Tracked"
            value={`${weeks.length}`}
          />
          <MetricCard
            label="Mean Calibration Error"
            value={`${(season_summary.mean_calibration_error * 100).toFixed(1)}%`}
            sublabel="Lower is better"
          />
        </div>
      </div>

      {/* Section 2: Week-by-week bar chart */}
      <SurfaceCard className="p-6">
        <h3 className="text-lg font-medium text-white mb-4">Hit Rate by Week</h3>
        <p className="text-xs text-sr-text-dim mb-4 italic">Backtested results</p>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart
            data={chartData}
            margin={{ top: 4, right: 16, left: 0, bottom: 4 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(255,255,255,0.06)"
            />
            <XAxis
              dataKey="week"
              tick={{ fill: '#9ca3af', fontSize: 12 }}
              label={{
                value: 'Week',
                position: 'insideBottom',
                offset: -2,
                fill: '#6b7280',
                fontSize: 11,
              }}
            />
            <YAxis
              domain={[0, 100]}
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
              formatter={(value: number | string | undefined) => [`${value ?? 0}%`, 'Hit Rate'] as [string, string]}
            />
            <ReferenceLine
              y={33}
              stroke="#6b7280"
              strokeDasharray="4 4"
              label={{ value: 'NFL avg 33%', fill: '#6b7280', fontSize: 11 }}
            />
            <Bar dataKey="hitRate" radius={[4, 4, 0, 0]}>
              {chartData.map((d, i) => (
                <Cell
                  key={i}
                  fill={d.aboveBaseline ? '#10b981cc' : '#f43f5ecc'}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </SurfaceCard>

      {/* Section 3: Accuracy by confidence band */}
      <SurfaceCard className="p-6">
        <h3 className="text-lg font-medium text-white mb-4">
          Accuracy by Confidence Band
        </h3>
        <p className="text-xs text-sr-text-dim mb-4 italic">Backtested results</p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-sr-text-muted text-left border-b border-sr-border">
                <th className="pb-2 font-medium">Band</th>
                <th className="pb-2 font-medium text-right nums">Predictions</th>
                <th className="pb-2 font-medium text-right nums">Hit Rate</th>
                <th className="pb-2 font-medium text-right">vs. Baseline</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-sr-border">
              {weeks.length > 0 &&
                (() => {
                  const hitRate = season_summary.overall_hit_rate;
                  const vsBaseline = hitRate - 0.33;
                  return (
                    <tr>
                      <td className="py-3 text-sr-text-muted">
                        All Actionable (≥15%)
                      </td>
                      <td className="py-3 text-right text-white nums">
                        {season_summary.total_predictions}
                      </td>
                      <td className="py-3 text-right text-white nums">
                        {(hitRate * 100).toFixed(1)}%
                      </td>
                      <td
                        className={`py-3 text-right nums font-semibold ${
                          vsBaseline >= 0 ? 'text-sr-success' : 'text-sr-danger'
                        }`}
                      >
                        {vsBaseline >= 0 ? '+' : ''}
                        {(vsBaseline * 100).toFixed(1)}%
                      </td>
                    </tr>
                  );
                })()}
              {weeks.length > 0 &&
                (() => {
                  const hcHitRate = season_summary.high_confidence_hit_rate;
                  const vsBaseline = hcHitRate - 0.33;
                  const hcTotal = weeks.reduce(
                    (s, w) => s + w.high_confidence_total,
                    0
                  );
                  return (
                    <tr>
                      <td className="py-3 text-sr-text-muted">
                        High Confidence (≥30%)
                      </td>
                      <td className="py-3 text-right text-white nums">
                        {hcTotal}
                      </td>
                      <td className="py-3 text-right text-white nums">
                        {(hcHitRate * 100).toFixed(1)}%
                      </td>
                      <td
                        className={`py-3 text-right nums font-semibold ${
                          vsBaseline >= 0 ? 'text-sr-success' : 'text-sr-danger'
                        }`}
                      >
                        {vsBaseline >= 0 ? '+' : ''}
                        {(vsBaseline * 100).toFixed(1)}%
                      </td>
                    </tr>
                  );
                })()}
            </tbody>
          </table>
        </div>
      </SurfaceCard>

      {/* Section 4: Paywall — current week preview */}
      <PaywallGate feature="current-week-predictions">
        <SurfaceCard className="p-6">
          <h3 className="text-lg font-medium text-white mb-4">
            This Week&apos;s Predictions
          </h3>
          <p className="text-sr-text-muted text-sm">
            Subscribe to see full per-player breakdown with edge values.
          </p>
        </SurfaceCard>
      </PaywallGate>

      {/* Disclaimer */}
      <p className="text-xs text-sr-text-dim text-center pb-4">
        For entertainment purposes only. Not financial or gambling advice.
      </p>
    </div>
  );
}
