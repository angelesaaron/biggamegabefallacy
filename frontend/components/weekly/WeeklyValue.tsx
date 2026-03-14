'use client';

import { useEffect, useState } from 'react';
import { TierSection } from '@/components/weekly/TierSection';
import { TierPlayerCard } from '@/components/weekly/TierPlayerCard';
import { GamblingDisclaimer } from '@/components/shared/GamblingDisclaimer';
import { PlayerWeekToggle } from '@/components/weekly/PlayerWeekToggle';
import { SurfaceCard } from '@/components/ui/SurfaceCard';
import { AlertTriangle } from 'lucide-react';
import type { PredictionResponse } from '@/types/backend';

interface WeeklyValueProps {
  currentWeek: number | null;
  currentYear: number | null;
  onPlayerClick: (playerId: string) => void;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? '';

function FadeGate({ count, children }: { count: number; children: React.ReactNode }) {
  const devBypass = process.env.NEXT_PUBLIC_DEV_BYPASS_PAYWALL === 'true';
  if (devBypass) return <>{children}</>;
  return (
    <div className="relative overflow-hidden rounded-card mt-2">
      <div className="pointer-events-none select-none" style={{ filter: 'blur(6px)' }} aria-hidden="true">
        {children}
      </div>
      <div
        className="absolute inset-0 flex flex-col items-center justify-end pb-10"
        style={{ background: 'linear-gradient(to bottom, transparent 0%, rgba(10,10,10,0.95) 30%)' }}
      >
        <div className="text-center px-6 max-w-md">
          <h3 className="text-white text-lg font-semibold mb-2">
            {count} player{count !== 1 ? 's' : ''} flagged as fades this week
          </h3>
          <p className="text-sr-text-muted text-sm mb-5">Know who to avoid →</p>
          <button className="bg-sr-primary text-white px-8 py-2.5 rounded-card font-semibold hover:bg-purple-600 transition-colors text-sm">
            Get Access
          </button>
        </div>
      </div>
    </div>
  );
}

export function WeeklyValue({ currentWeek, currentYear, onPlayerClick }: WeeklyValueProps) {
  const [predictions, setPredictions] = useState<PredictionResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedWeek, setSelectedWeek] = useState<number>(18);

  useEffect(() => {
    if (currentWeek !== null) setSelectedWeek(currentWeek);
  }, [currentWeek]);

  const effectiveYear = currentYear ?? 2025;
  const isEarlySeason = selectedWeek <= 3;

  useEffect(() => {
    async function loadPredictions() {
      try {
        setLoading(true);
        setError(null);
        const res = await fetch(`${API_URL}/api/predictions/${effectiveYear}/${selectedWeek}`);
        if (!res.ok) throw new Error('Failed to fetch predictions');
        const data = await res.json();
        setPredictions(data.predictions ?? []);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load predictions');
      } finally {
        setLoading(false);
      }
    }
    loadPredictions();
  }, [selectedWeek, effectiveYear]);

  const tier1 = predictions.filter((p) => p.tier === 'high_conviction');
  const tier2 = predictions.filter((p) => p.tier === 'value_play');
  const tier3 = predictions.filter((p) => p.tier === 'on_the_radar');
  const fadeVolumeTraps = predictions.filter((p) => p.tier === 'fade_volume_trap');
  const fadeOverpriced = predictions.filter((p) => p.tier === 'fade_overpriced');
  const hasFades = fadeVolumeTraps.length > 0 || fadeOverpriced.length > 0;

  return (
    <div className="relative">
      {/* Hero gradient */}
      <div
        className="absolute top-0 left-0 w-full hidden md:block"
        style={{
          height: 320,
          background: 'linear-gradient(135deg, #1a0533 0%, #0d1117 40%, #0a0a0a 100%)',
        }}
      />

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        {/* Page header */}
        <SurfaceCard className="mb-4 p-4 md:p-6">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div className="flex-1">
              <h1 className="text-xl md:text-3xl font-semibold text-white mb-1">
                Week {selectedWeek} — ATTD Targets
              </h1>
              <p className="text-sm text-sr-text-muted">
                Model-ranked anytime TD plays for Week {selectedWeek}. Updated Tuesday.
              </p>
            </div>
            <PlayerWeekToggle
              currentWeek={currentWeek ?? 18}
              currentYear={effectiveYear}
              selectedWeek={selectedWeek}
              onWeekChange={setSelectedWeek}
            />
          </div>
        </SurfaceCard>

        {/* Early season banner */}
        {isEarlySeason && !loading && !error && predictions.length > 0 && (
          <div className="mb-4 rounded-card border border-amber-500/40 bg-amber-500/10 p-4 text-sm">
            <p className="text-amber-400 font-semibold mb-1">
              Projection Mode — Week {selectedWeek}
            </p>
            <p className="text-sr-text-muted">
              Predictions use prior-season carry-forward data. Model transitions to live rolling
              features from Week 4. Confidence intervals are wider than mid-season.
            </p>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="flex flex-col gap-2 mb-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-16 rounded-card bg-sr-surface animate-pulse" />
            ))}
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mb-4 bg-sr-danger/10 border border-sr-danger/30 rounded-card p-4 text-sr-danger flex items-center gap-2">
            <AlertTriangle size={16} />
            <span>{error}</span>
          </div>
        )}

        {/* No predictions */}
        {!loading && !error && predictions.length === 0 && (
          <SurfaceCard className="p-12 text-center mb-4">
            <AlertTriangle size={24} className="text-yellow-500 mx-auto mb-2" />
            <p className="text-sr-text-muted">
              Week {selectedWeek} predictions haven&apos;t been generated yet. Check back after
              Thursday&apos;s pipeline run.
            </p>
          </SurfaceCard>
        )}

        {/* Tier sections */}
        {!loading && !error && predictions.length > 0 && (
          <>
            {/* Tier 1 — High Conviction (paid) */}
            <TierSection
              tier="high_conviction"
              label="High Conviction"
              descriptor="Model's highest-confidence plays this week."
              accentClass="border-sr-success/40"
              headerTextClass="text-sr-success"
              predictions={tier1}
              isPaywalled
              ctaTitle={`${tier1.length} high conviction play${tier1.length !== 1 ? 's' : ''} this week`}
              ctaBody="Subscribe to see them →"
              onPlayerClick={onPlayerClick}
            />

            {/* Tier 2 — Value Plays (paid) */}
            <TierSection
              tier="value_play"
              label="Value Plays"
              descriptor="Positive edge, meaningful model confidence."
              accentClass="border-amber-500/40"
              headerTextClass="text-amber-400"
              predictions={tier2}
              isPaywalled
              ctaTitle={`${tier2.length} value play${tier2.length !== 1 ? 's' : ''} identified`}
              ctaBody="See the full list →"
              onPlayerClick={onPlayerClick}
            />

            {/* Tier 3 — On the Radar (free) */}
            <TierSection
              tier="on_the_radar"
              label="On the Radar"
              descriptor="Model is warm. Not a strong signal, but worth knowing."
              accentClass="border-sr-border"
              headerTextClass="text-white"
              predictions={tier3}
              isPaywalled={false}
              onPlayerClick={onPlayerClick}
            />

            {/* Tier 4 — Fade List (paid) */}
            <section className="mb-8">
              <div className="flex items-baseline gap-3 mb-3 pb-2 border-b border-sr-danger/40">
                <h2 className="text-base font-semibold text-sr-danger">Fade List</h2>
                <span className="text-sr-text-dim text-xs">
                  Players the model is cold on. Book may be overpricing them.
                </span>
              </div>

              {!hasFades ? (
                <p className="text-sr-text-muted text-sm py-4 px-2">
                  No fade plays identified this week.
                </p>
              ) : (
                <FadeGate count={fadeVolumeTraps.length + fadeOverpriced.length}>
                  {fadeVolumeTraps.length > 0 && (
                    <div className="mb-4">
                      <p className="text-xs font-semibold text-sr-danger/70 uppercase tracking-wide mb-2 px-1">
                        Volume Traps
                      </p>
                      <p className="text-xs text-sr-text-dim mb-2 px-1">
                        High-profile players the model doesn&apos;t trust this week.
                      </p>
                      <div className="flex flex-col gap-2">
                        {fadeVolumeTraps.map((pred) => (
                          <TierPlayerCard key={pred.player_id} prediction={pred} onClick={onPlayerClick} />
                        ))}
                      </div>
                    </div>
                  )}

                  {fadeOverpriced.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-sr-danger/70 uppercase tracking-wide mb-2 px-1">
                        Overpriced Depth
                      </p>
                      <p className="text-xs text-sr-text-dim mb-2 px-1">
                        Book is pricing these players too high relative to model.
                      </p>
                      <div className="flex flex-col gap-2">
                        {fadeOverpriced.map((pred) => (
                          <TierPlayerCard key={pred.player_id} prediction={pred} onClick={onPlayerClick} />
                        ))}
                      </div>
                    </div>
                  )}
                </FadeGate>
              )}
            </section>
          </>
        )}

        <GamblingDisclaimer />
      </div>
    </div>
  );
}
