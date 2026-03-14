# Big Game Gabe — Product & Content Design Spec

**Version**: 1.0  
**Date**: 2026-03-13  
**Purpose**: Content, layout, and UX spec for the frontend redesign. Complements `frontend-refactor.md` (technical/MUI migration). Auth and paywall permission logic is deferred — use placeholder `isSubscribed = false` flags throughout. Structure must be correct now so wiring permissions later requires no layout changes.

---

## 1. Strategic Context

### What the product actually is

Big Game Gabe is an NFL anytime touchdown (ATTD) prediction model for wide receivers and tight ends. The model generates ~300 predictions per week. The core insight from 2025 season data:

- Top 3 model picks per week (high conviction + positive edge) hit at **42.6%** across 18 weeks
- All high-conviction picks (model 40%+) hit at **29.2%**
- Picks where the model is negative (fade list) hit at **~12.5%**
- The gradient from conviction to fade is the product's entire value proposition

### What the product is NOT

- Not a "ranked list of 300 players sorted by edge vs. sportsbook"
- Not a tracker of who scored last week
- Not a system that claims winners — it surfaces probability gradients

### The sales angle

> "We don't pretend every wide receiver is a bet. We surface the 3–5 players the model is most confident about — and our top picks hit nearly twice as often as random. You still lose some weeks. But you're playing with better information."

The "avoid" angle is equally important and underused in this space. Nobody tells you who the books are overpricing. The fade list is a distinct product feature, not a footnote.

### Voice

Precise, confident-not-hyped, sharp-but-accessible, honest. Never: "LOCKS", "GUARANTEED", "CAN'T MISS". The product earns trust through transparency about what the model is and isn't.

---

## 2. Navigation & Page Structure

Three tabs. No additional pages for now.

| Tab label | Route state | Default |
|---|---|---|
| This Week | `'weekly'` | ✓ Yes |
| Player Lookup | `'player'` | — |
| Track Record | `'track'` | — |

The "This Week" tab is the product. It's what a subscriber checks every week. It should be the default landing state.

---

## 3. This Week Page

### 3.1 Overview

Replaces the current `WeeklyValue.tsx` ranked list. The page is organized into **four named tiers** displayed as distinct sections, not a single sorted table. The tier a player lands in tells you what to do — you should not need to read a number to understand it.

The `+EV only` checkbox filter is removed. Filtering is baked into the tier structure itself.

### 3.2 Page header

```
Week {N} — ATTD Targets
[week selector toggle — same as current PlayerWeekToggle behavior]
"Model-ranked anytime TD plays for Week N. Updated [day]."
```

Do not show "Players with the highest model edge vs DraftKings odds" — this framing caused the +1400 problem. The product leads with model conviction, not edge vs. book.

### 3.3 Tier definitions

Four tiers rendered in this order, top to bottom. Each tier is a visually distinct section with a header label and a short descriptor line. Player cards within each tier are sorted by `final_prob_pct` descending.

---

#### Tier 1 — High Conviction

**Label**: `High Conviction`  
**Descriptor**: "Model's highest-confidence plays this week."  
**Color accent**: Green (`sr-success`)  
**Player count**: 3–5  
**Filter logic**:
- `final_prob_pct >= 45`
- `favor > 0` (positive model edge vs. book implied prob)
- `completeness_score >= 0.8`
- Has sportsbook odds (exclude players with no odds line)
- Exclude `is_low_confidence = true`

**Paywall**: Gated (paid). Free users see a blurred version of this section with count visible: "3 high conviction plays this week — subscribe to unlock."

**Historical accuracy tooltip** (on the tier label): "Top picks historically hit at 42.6% — roughly 2x the league average ATTD rate."

---

#### Tier 2 — Value Plays

**Label**: `Value Plays`  
**Descriptor**: "Positive edge, meaningful model confidence."  
**Color accent**: Amber (`sr-ev`)  
**Player count**: 5–8  
**Filter logic**:
- `final_prob_pct >= 35` and `< 45`
- `favor > 0`
- Has sportsbook odds at +200 or better (i.e., `dk_implied_prob_pct <= 33`) — this eliminates the "+1400 edge noise" problem where the model looks positive purely because the book doesn't price depth guys
- Exclude `is_low_confidence = true`

**Paywall**: Gated (paid).

---

#### Tier 3 — On the Radar

**Label**: `On the Radar`  
**Descriptor**: "Model is warm. Not a strong signal, but worth knowing."  
**Color accent**: None (neutral)  
**Player count**: 5–10  
**Filter logic**:
- `final_prob_pct >= 30` and `< 35`
- OR: `final_prob_pct >= 35` but model edge is negative/neutral (model is warm but book disagrees)
- Has sportsbook odds

**Paywall**: Free. This is the free user's weekly reason to return. They see player names, team, position, and model tier label. Model probability and odds are not shown in free tier — just the names and tier membership.

---

#### Tier 4 — Fade List

**Label**: `Fade List`  
**Descriptor**: "Players the model is cold on. Book may be overpricing them."  
**Color accent**: Red (`sr-danger`)  
**Player count**: 5–10  
**Sub-buckets** (displayed as two groups within the section):

**Volume Traps** — "High-profile players the model doesn't trust this week."
- `final_prob_pct < 35`
- `dk_implied_prob_pct >= 35` (book has them -175 or shorter — inflated by name value)
- This catches the "Ja'Marr Chase at -140 but model says 25%" situations

**Overpriced depth** — "Book is pricing these players too high relative to model."
- `final_prob_pct < 25`
- `favor < -10` (model is meaningfully below implied prob)
- Has odds (so the book is actively offering a line)

**Paywall**: Gated (paid). This section is arguably the most unique feature — no public tool explicitly shows you who to fade.

---

### 3.4 Early season treatment (Weeks 1–3)

Weeks 1–3 use carry-forward features from prior season end-state. The model is less differentiated and many players cluster together. This needs explicit communication in the UI.

- Show a banner above the tier sections: `"Week {N} — Projection Mode: Predictions are based on prior-season data. Live rolling features activate from Week 4."`
- Reduce tier thresholds for weeks 1–3 (no players may qualify for Tier 1 at normal thresholds)
- Consider making weeks 1–3 fully free to reduce subscriber churn expectations early in the season

### 3.5 Empty states

- No players qualify for a tier: `"No {tier name} plays identified this week."` — show this, don't hide the section
- No predictions yet for the selected week: `"Week {N} predictions haven't been generated yet. Check back after Thursday's pipeline run."`
- Week is in the future: `"Predictions for Week {N} will be available after the weekly data update."`

### 3.6 Player card redesign

Each tier uses the same card component with tier-aware styling.

**Card anatomy (left to right)**:

```
[Rank #] [Headshot] [Name / Team · Position] [Tier badge] ... [Model %] [Model odds] [Book odds]
```

**Fields shown by tier**:

| Field | Free (On Radar) | Paid tiers |
|---|---|---|
| Rank | ✓ | ✓ |
| Headshot | ✓ | ✓ |
| Name | ✓ | ✓ |
| Team / Position | ✓ | ✓ |
| Tier badge | ✓ | ✓ |
| Model probability % | ✗ (blurred) | ✓ |
| Model odds | ✗ | ✓ |
| Book odds | ✓ (always visible) | ✓ |
| Edge value | ✗ | ✓ |

**Tier badge colors**:
- High Conviction: green background, `High Conv.`
- Value Play: amber background, `Value`
- On the Radar: gray background, `Radar`
- Fade: red background, `Fade`

**Fade card treatment**: The card background gets a very subtle red tint (`sr-danger/5`). The rank number is not shown (not meaningful for fades). Instead of model odds, show the implied probability gap: `"Book: 38% · Model: 21%"` format.

**Implementation note**: `// TODO: replace isSubscribed=false with auth hook when JWT wired`

---

## 4. Track Record Page

### 4.1 The narrative

The track record page makes a single coherent argument in sequence. Do not show isolated stat cards floating next to a graph. Every element connects.

**The argument**: When the model is highly confident and has positive edge, it hits at nearly 2x the league average. As conviction falls, so does hit rate. When the model is cold (fade territory), hit rate drops to ~12.5%. The model's signal is real — and it's directional.

### 4.2 Page structure (top to bottom)

**Section 1: The headline**

Simple text, not a card:
```
Season 2025 Track Record
Backtested results across 18 weeks, 5,368 predictions.
```

Small italic disclaimer inline: `"Backtested results — not indicative of guaranteed future performance."`

**Section 2: The main chart** — conviction × edge hit rate gradient

One horizontal bar chart. X-axis: tier/bucket. Y-axis: hit rate %.

Bars left to right:
1. Top Picks (high conv. + positive edge, top 3/week): **42.6%**
2. High Conviction (model 40%+, with odds): **29.2%**
3. Value Plays (35–45%, positive edge): **~22%** (compute from data)
4. On the Radar (30–35%): **~18%** (compute from data)
5. NFL Baseline (dashed reference line): **~20–25%** for priced players
6. Negative Edge: **~15%**
7. Fade List: **12.5%**

Bar colors: Green ramp for above-baseline tiers, gray for baseline, red ramp for fade territory. This gradient IS the pitch.

Chart title: `"Hit rate by model tier — 2025 season"`  
Subtitle: `"Backtested. Higher conviction = higher hit rate."`

**Section 3: Summary stat cards** (below the chart, not above it)

Four cards in a 2×2 or 4×1 grid:
- `42.6%` — Top picks hit rate / "Top 3 picks per week"
- `29.2%` — High conviction hit rate / "Model 40%+ with odds"
- `18 weeks` — Season coverage
- `5,368` — Total predictions analyzed

These cards support the chart above — they don't replace it.

**Section 4: Week-by-week table** (paid — gated for subscribers)

Columns: Week | High Conv. picks | Hit | Value picks | Hit | Fade picks | Miss rate

This is for auditors and trust-builders. Free users see the first 3 weeks blurred and a "Subscribe to see full breakdown" CTA.

**Section 5: The inverse argument** (fade list accuracy)

Short paragraph + small stat:
```
The model's negative signal is equally real.

Players flagged as fades hit at 12.5% in 2025 — roughly half the rate of 
high-conviction picks. Knowing who not to bet is part of the edge.
```
Stat card: `12.5%` — Fade list hit rate / "Players model was cold on"

This closes the loop. Track record isn't just about picking winners — it's about the full spectrum.

**Section 6: Calibration note**

Short text block (not a chart for now):
```
About the model
The model outputs calibrated probabilities — a 30% prediction should hit roughly 
30% of the time. Probability calibration is what separates a real model from 
gut-feel percentages.
```

No calibration curve chart yet — too much to explain without proper context. Add in a future iteration.

**Section 7: Disclaimer**

```
For entertainment purposes only. Not financial or gambling advice. 
Backtested results do not guarantee future performance.
```

### 4.3 What NOT to show on track record

- Do not show overall hit rate on all 300+ weekly predictions — this number (~15%) looks terrible and is not the right framing
- Do not show "Mean Calibration Error" as a headline stat — non-intuitive for users
- Do not show week-by-week bar chart of total hit rate — individual bad weeks look punitive without tier context
- Do not show a raw P&L or ROI figure

---

## 5. Player Lookup Page

Mostly unchanged from current implementation. Key content decisions:

### 5.1 Player header

Show current week tier badge prominently. If player is in High Conviction this week, the badge should be the first thing you see.

### 5.2 Current week section

```
Week {N} prediction
[Tier badge] [Model %] [Model odds] [Book odds] [Edge]
```

If player has no prediction this week: `"No prediction generated for Week {N}. Player may be inactive, on bye, or data not yet available."`

### 5.3 Season trend (paid)

Week-by-week model probability chart for the selected player. Useful for seeing if a player is trending up or down in the model.

### 5.4 Free vs. paid on player lookup

- Free: Search, current week tier label, book odds
- Paid: Model %, model odds, edge value, season trend chart, snap/RZ breakdown

---

## 6. Microcopy Reference

All copy for tooltips, labels, empty states, CTAs, and disclaimers.

### 6.1 Tier tooltips (on hover/tap of tier label)

| Tier | Tooltip text |
|---|---|
| High Conviction | "Model probability 45%+, positive edge vs. book, high data completeness. Historically hit at 42.6%." |
| Value Play | "Model probability 35–45% with meaningful positive edge. Book is underpricing relative to model." |
| On the Radar | "Model is warm on this player. Not a strong signal, but worth watching if you like the matchup." |
| Fade List | "Model is cold here. Book may be overpricing due to name value or recency. Historically hit at 12.5%." |
| Volume Trap | "High-usage player the model doesn't trust for a TD this week specifically." |

### 6.2 Edge value display

Always show sign explicitly: `+7.2%` or `-4.8%`. Never just `7.2%`.

Label: `Edge` (not "EV", not "Expected Value" — too jargony for casual users)

Tooltip: `"Edge = model probability minus book's implied probability. Positive means model sees more value than the line offers."`

### 6.3 Paywall CTA copy

**Tier 1 gate (This Week page)**:
```
3 high conviction plays this week
Subscribe to see them →
```

**Tier 2 gate**:
```
5 value plays identified
See the full list →
```

**Fade list gate**:
```
7 players flagged as fades this week
Know who to avoid →
```

**Track record table gate**:
```
Full week-by-week breakdown
Subscribe for complete history →
```

**Paywall overlay headline**: `"Big Game Gabe — Season Access"`

**Paywall overlay body**: `"High conviction picks, value plays, and the fade list — every week of the NFL season. Backed by a real model, not gut picks."`

**CTA button**: `"Get Access"` (not "Subscribe", not "Unlock" — "Get Access" is the least threatening framing)

### 6.4 Early season banner

```
Projection Mode — Week {N}
Predictions use prior-season carry-forward data. Model transitions to live rolling 
features from Week 4. Confidence intervals are wider than mid-season.
```

### 6.5 Empty states

| Situation | Copy |
|---|---|
| No tier 1 picks | "No high conviction plays identified this week." |
| No predictions for week | "Week {N} predictions haven't been generated yet. Check back after the Thursday pipeline run." |
| Player inactive | "No prediction for this player in Week {N}. They may be inactive, on bye, or missing from this week's dataset." |
| Track record no data | "Track record data will appear after the first full season of predictions." |

### 6.6 Disclaimer (every page footer)

```
For entertainment purposes only. Not financial or gambling advice. 
Model predictions are probabilistic — no outcome is guaranteed.
```

Backtested data specifically:
```
Results shown are backtested on historical data and do not guarantee future performance.
```

### 6.7 Navigation labels

| Current | New |
|---|---|
| "Weekly Value" | "This Week" |
| "Player Model" | "Player Lookup" |
| "Track Record" | "Track Record" (keep) |

---

## 7. Tier Computation Logic

Backend and/or frontend filter logic for each tier. These thresholds are starting points — adjust based on how many players land per week in production.

```python
# Tier 1 — High Conviction
tier_1 = predictions.filter(
    final_prob_pct >= 45,
    favor > 0,                     # positive model edge
    completeness_score >= 0.8,
    has_sportsbook_odds == True,
    is_low_confidence == False
).order_by(final_prob_pct DESC).limit(5)

# Tier 2 — Value Plays
tier_2 = predictions.filter(
    final_prob_pct >= 35,
    final_prob_pct < 45,
    favor > 0,
    dk_implied_prob_pct <= 33,     # book at +200 or worse — filters +1400 noise
    has_sportsbook_odds == True,
    is_low_confidence == False
).exclude(player_id IN tier_1).order_by(final_prob_pct DESC).limit(8)

# Tier 3 — On the Radar
tier_3 = predictions.filter(
    final_prob_pct >= 30,
    final_prob_pct < 35,
    has_sportsbook_odds == True
).exclude(player_id IN tier_1 + tier_2).order_by(final_prob_pct DESC).limit(10)

# Tier 4a — Fade: Volume Traps
fade_volume_traps = predictions.filter(
    final_prob_pct < 35,
    dk_implied_prob_pct >= 35,     # book has them -175 or shorter
    has_sportsbook_odds == True
).order_by(dk_implied_prob_pct DESC).limit(5)

# Tier 4b — Fade: Overpriced depth
fade_overpriced = predictions.filter(
    final_prob_pct < 25,
    favor < -10,                   # model meaningfully below implied
    has_sportsbook_odds == True
).exclude(player_id IN fade_volume_traps).order_by(favor ASC).limit(5)
```

**Note on weeks 1–3**: The `completeness_score` filter will block many Tier 1 picks early season since carry-forward rows have `completeness_score = 0.38`. Either drop the completeness threshold for weeks 1–3 or display a "limited data" indicator on those cards. The former is simpler.

---

## 8. Backend API Changes Required

These are content-layer changes needed to support the redesign. Auth is not in scope.

### 8.1 Predictions endpoint — add tier field

`GET /api/predictions/{season}/{week}` should return a `tier` field on each prediction:

```json
{
  "player_id": "...",
  "full_name": "Drake London",
  "team": "ATL",
  "position": "WR",
  "final_prob": 0.618,
  "favor": 19.3,
  "tier": "high_conviction",
  "model_odds": 135,
  "sportsbook_odds": 160,
  ...
}
```

Tier values: `"high_conviction"`, `"value_play"`, `"on_the_radar"`, `"fade_volume_trap"`, `"fade_overpriced"`, `null` (untiered).

Computing tier server-side is better than doing it in the frontend — consistent logic, easier to test.

### 8.2 Track record endpoint — add tier breakdown

`GET /api/track-record?season=2025` needs to return per-tier hit rates:

```json
{
  "season": 2025,
  "tier_summary": {
    "top_picks": { "hits": 23, "total": 54, "hit_rate": 0.426 },
    "high_conviction": { "hits": 257, "total": 879, "hit_rate": 0.292 },
    "value_play": { "hits": 0, "total": 0, "hit_rate": null },
    "fade": { "hits": 163, "total": 1309, "hit_rate": 0.125 }
  },
  "weeks": [...],
  "season_summary": {...}
}
```

"Top picks" is defined as the top 3 `final_prob_pct` players with positive edge per week — compute this at query time, not from stored tier assignments (since tiers weren't stored in 2025 data).

### 8.3 Public predictions — is_early_season flag

For the early-season banner, the `/api/predictions/{season}/{week}` response (or `/api/status/week`) should include:

```json
{ "week": 2, "season": 2026, "is_early_season": true }
```

`is_early_season = true` when `week <= 3`.

---

## 9. Paywall Structure (Design Only — Auth Deferred)

Document the intended permission model for when auth is wired. Use `isSubscribed = false` hardcoded everywhere now.

### 9.1 Tiers

| Tier | Price | What's included |
|---|---|---|
| Free | $0 | On the Radar picks, top-level track record stats, player search (tier label + book odds only) |
| Season Pass | ~$29/season | Everything: High Conviction, Value Plays, Fade List, full track record breakdown, player season trend |
| Pro | ~$49/season | Season Pass + Thursday early access, email alerts, full historical export |

### 9.2 Implementation pattern

All gated content should be rendered and then blurred — not conditionally hidden. This means:

```tsx
// CORRECT — render, then blur
<div style={{ filter: isSubscribed ? 'none' : 'blur(6px)', pointerEvents: isSubscribed ? 'auto' : 'none' }}>
  <TierSection tier="high_conviction" predictions={predictions} />
</div>

// INCORRECT — conditional render
{isSubscribed && <TierSection tier="high_conviction" predictions={predictions} />}
```

Blurred real data is better conversion UX than a placeholder. The user sees the structure and volume of what they're missing.

**Paywall overlay** sits on top of the blurred content. It should:
- Be anchored to the bottom of the blurred section (gradient fade from transparent to `sr-bg/95`)
- Show tier name, a one-line benefit statement, and the "Get Access" CTA
- NOT have a "No thanks" / dismiss button — only close to collapse
- NOT block the page header or navigation

### 9.3 Free tier UX decisions

Free users on "This Week" see:
- The page header with week number
- On the Radar section (full, no blur)
- High Conviction and Value Play sections — blurred with count badge and CTA
- Fade List section — blurred with count badge and CTA
- No odds or model % anywhere — only tier label and player name/team

The free experience should feel like a real product, not a locked door. Seeing 7 names on the radar with no numbers is still useful. It brings them back.

---

## 10. Auth & Paywall — Implementation Notes (Future Sprint)

When auth is ready, the changes are:

1. Replace `isSubscribed = false` with `useAuth()` hook or JWT decode
2. The `PaywallGate` component accepts `isSubscribed` prop — no structural changes
3. The API does not need to gate responses — gating is purely presentational until there's a reason to gate at the data layer
4. If data-layer gating is needed later: add `?tier=free` query param to predictions endpoint and return only `on_the_radar` results; no other changes needed

Auth stack recommendation (deferred, for reference): Clerk or Supabase Auth — both have Next.js App Router support and webhook-based Stripe integration. Do not build custom JWT auth.

Payment recommendation: Stripe Checkout, season-based product (not subscription). One-time purchase per season reduces churn management complexity and matches the product's natural lifecycle.

---

## 11. Component Checklist for Agents

When implementing this spec, agents should:

- [ ] Read `frontend-refactor.md` first for technical migration context (MUI → Tailwind)
- [ ] Replace `WeeklyValue.tsx` with tiered layout — four named sections, not a sorted list
- [ ] Remove the `+EV only` checkbox filter — tier structure replaces it
- [ ] Add `tier` field support to predictions response (backend change — see §8.1)
- [ ] Implement `PlayerCard` with tier-aware styling and conditional field visibility
- [ ] Add early-season banner logic (weeks 1–3) to `WeeklyValue.tsx`
- [ ] Implement `TrackRecord.tsx` with the conviction gradient chart as the lead element
- [ ] Add `PaywallGate` component with blur treatment (hardcoded `isSubscribed = false`)
- [ ] Update all copy to match §6 microcopy reference
- [ ] Rename navigation tabs per §6.7
- [ ] Do not show overall hit rate on all predictions anywhere — only tier hit rates
- [ ] Fade list is a feature, not an afterthought — give it equal visual weight to value picks

---

*For architecture, pipeline, and ML model context see: `BGF_Project_Synopsis.md`*  
*For technical frontend migration see: `frontend-refactor.md`*
