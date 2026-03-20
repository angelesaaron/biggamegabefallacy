'use client';

import { useEffect, useRef, useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { usePredictions } from '@/hooks/usePredictions';
import { TierSection } from '@/components/weekly/TierSection';
import { TeaserBanner } from '@/components/weekly/TeaserBanner';
import { TierPlayerCard } from '@/components/weekly/TierPlayerCard';
import { GamblingDisclaimer } from '@/components/shared/GamblingDisclaimer';
import { PlayerWeekToggle } from '@/components/weekly/PlayerWeekToggle';
import { SurfaceCard } from '@/components/ui/SurfaceCard';
import { AlertTriangle } from 'lucide-react';

interface WeeklyValueProps {
  currentWeek: number | null;
  currentYear: number | null;
  weekSource: 'admin_override' | 'pipeline' | 'default' | null;
  onPlayerClick: (playerId: string) => void;
}

export function WeeklyValue({ currentWeek, currentYear, weekSource, onPlayerClick }: WeeklyValueProps) {
  const { isSubscriber } = useAuth();
  const [selectedWeek, setSelectedWeek] = useState<number | null>(null);
  const initialized = useRef(false);

  useEffect(() => {
    if (!initialized.current && currentWeek !== null) {
      setSelectedWeek(currentWeek);
      initialized.current = true;
    }
  }, [currentWeek]);

  const effectiveYear = currentYear ?? 2026;
  const isEarlySeason = selectedWeek !== null && selectedWeek <= 3;
  const isHistorical = currentWeek !== null && selectedWeek !== null && selectedWeek < currentWeek;

  const { predictions, teaser, loading, error } = usePredictions(effectiveYear, selectedWeek);

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
        <SurfaceCard className={`mb-4 p-4 md:p-6${isHistorical ? ' border-sr-primary/30' : ''}`}>
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div className="flex-1">
              <h1 className="text-xl md:text-3xl font-semibold text-white mb-1">
                {selectedWeek !== null ? `Week ${selectedWeek}` : 'Loading…'} — ATTD Targets
              </h1>
              <p className="text-sm text-sr-text-muted">
                {selectedWeek !== null
                  ? `Model-ranked anytime TD plays for Week ${selectedWeek}. Updated Tuesday.`
                  : 'Fetching current week…'}
              </p>
            </div>
            {selectedWeek !== null && (
              <PlayerWeekToggle
                currentWeek={currentWeek ?? selectedWeek}
                currentYear={effectiveYear}
                selectedWeek={selectedWeek}
                onWeekChange={setSelectedWeek}
              />
            )}
          </div>
        </SurfaceCard>

        {/* Early season banner */}
        {isEarlySeason && selectedWeek !== null && !loading && !error && predictions.length > 0 && (
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
            {isSubscriber ? (
              <TierSection
                tier="high_conviction"
                label="High Conviction"
                descriptor="Model's highest-confidence plays this week."
                accentClass="border-sr-success/40"
                headerTextClass="text-sr-success"
                predictions={tier1}
                onPlayerClick={onPlayerClick}
              />
            ) : (
              <TeaserBanner
                label="High Conviction"
                count={teaser?.high_conviction ?? 0}
                noun="play"
                accentClass="border-sr-success/40"
                headerTextClass="text-sr-success"
                descriptor="Model's highest-confidence plays this week."
              />
            )}

            {/* Tier 2 — Value Plays (paid) */}
            {isSubscriber ? (
              <TierSection
                tier="value_play"
                label="Value Plays"
                descriptor="Positive edge, meaningful model confidence."
                accentClass="border-amber-500/40"
                headerTextClass="text-amber-400"
                predictions={tier2}
                onPlayerClick={onPlayerClick}
              />
            ) : (
              <TeaserBanner
                label="Value Plays"
                count={teaser?.value_play ?? 0}
                noun="play"
                accentClass="border-amber-500/40"
                headerTextClass="text-amber-400"
                descriptor="Positive edge, meaningful model confidence."
              />
            )}

            {/* Tier 3 — On the Radar (always visible to everyone) */}
            <TierSection
              tier="on_the_radar"
              label="On the Radar"
              descriptor="Model is warm. Not a strong signal, but worth knowing."
              accentClass="border-sr-border"
              headerTextClass="text-white"
              predictions={tier3}
              onPlayerClick={onPlayerClick}
            />

            {/* Tier 4 — Fade List (paid) */}
            {isSubscriber ? (
              <TierSection
                tier="fade_volume_trap"
                label="Fade List"
                descriptor="Players the model is cold on. Book may be overpricing them."
                accentClass="border-sr-danger/40"
                headerTextClass="text-sr-danger"
                predictions={[]}
                onPlayerClick={onPlayerClick}
              >
                {hasFades && (
                  <>
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
                  </>
                )}
              </TierSection>
            ) : (
              <TeaserBanner
                label="Fade List"
                count={teaser?.fade ?? 0}
                noun="player"
                accentClass="border-sr-danger/40"
                headerTextClass="text-sr-danger"
                descriptor="Players the model is cold on."
              />
            )}
          </>
        )}

        <GamblingDisclaimer />
      </div>

    </div>
  );
}
