```md
# BGGTDM (Big Game Gabe TD Model)

BGGTDM is a modern NFL touchdown prediction web application that compares a proprietary machine learning model’s touchdown probabilities against sportsbook odds. The goal is to surface **value discrepancies**, provide **player-level insight**, and present everything in a **clean, Sleeper-inspired UI** that’s easy to explore for fans and bettors alike.

This project began as a Streamlit app and has been fully refactored into a production-style web application with a dedicated backend, frontend, and data pipeline.

---

## Core Concept

For any given NFL week, BGGTDM:
- Predicts the probability that a player (WR / TE) will score a touchdown
- Converts that probability into implied American odds
- Compares those odds against sportsbook TD scorer odds
- Highlights where the model sees **value (edge)** relative to the market

---

## Application Views

BGGTDM has **two primary views**:

---

## 1. Player View (Default)

The Player View is the heart of the application. It allows users to explore **one player at a time** in depth.

### What You Can See

#### Player Overview
- Player name, headshot, team, position, jersey number
- High-level KPIs such as:
  - Touchdowns scored
  - Games played
  - Targets
  - TD rate / efficiency metrics

#### Current Week Prediction (Primary Focus)
- Model-predicted touchdown probability
- Model-implied American odds
- Sportsbook TD scorer odds for the same week
- Clear visual comparison highlighting:
  - Where the model is more bullish than the sportsbook
  - Where the market is pricing the player efficiently

#### Historical Performance vs Model
- Week-by-week view of:
  - Model touchdown probability
  - Actual game outcomes
- Interactive or expandable game log table:
  - Highlights weeks where the player scored a touchdown
  - Shows how model expectations compared to real outcomes
- Visualizations that make it easy to understand:
  - Consistency
  - Volatility
  - How often the model was “right” for this player

The Player View is designed to feel similar to a **Sleeper fantasy player page**, blending analytics with a sportsbook-style presentation while staying clean and readable.

---

## 2. Weekly Value View

The Weekly Value View is designed for discovery.

Instead of focusing on a single player, this page answers the question:

> *“Which players offer the most value this week based on model vs sportsbook odds?”*

### What You Can See

- A ranked list of players for a given calendar week
- Sorted by **edge differential**:
  - Difference between model-implied odds and sportsbook odds
- Each row or card includes:
  - Player name and headshot
  - Model touchdown probability
  - Model-implied odds
  - Sportsbook odds
  - Clear edge indicator
- Optional historical context:
  - Whether the player scored in the previous week
  - High-level model performance from last week

Users can click any player in the Weekly View to navigate directly to that player’s detailed Player View.

---

## Design Philosophy

- **Clean, modern, and minimal**
- Heavy inspiration from the **Sleeper fantasy football app**
- Dark mode–first design
- No cluttered dashboards or dense tables by default
- Details are available via expansion (accordions, drill-downs)
- Focused on clarity, not gambling flashiness

---

## Data & Model

- Player data, game logs, schedules, and betting odds are sourced from the **Tank01 NFL API**
- The machine learning model:
  - Uses historical player performance features
  - Outputs a touchdown probability for each player-week
  - Is designed to be revisited and retrained as more data accumulates
- Odds comparisons are performed using player prop data embedded directly in Tank01 responses

### Weekly Data Updates

The application automatically updates data every Tuesday at 7 AM EST (after Monday Night Football) via GitHub Actions:

**Update Process:**
- Fetches schedule for current and next week
- Updates game logs for the previous week's completed games
- Refreshes sportsbook odds for upcoming games
- Generates new touchdown predictions

**Idempotent Design (Safe to Run Multiple Times):**
- **Schedule**: Updates existing games, adds new ones (no duplicates)
- **Game Logs**: Skips existing logs, only adds new ones (no duplicates)
- **Odds**: Deletes and refreshes all odds for the target week (ensures latest odds)
- **API Calls**: Makes ~556 calls per run regardless of existing data

Running the update script multiple times for the same week is safe but uses API quota. The automated workflow ensures data stays fresh without manual intervention.

---

## Intended Audience

- NFL fans who enjoy analytics
- Fantasy football players
- Sports betting hobbyists
- Friends and small private users (this is a passion project, not a commercial platform)

---

## Project Status

- Backend ML inference and feature engineering complete
- Frontend UI under active development
- Initial focus is on correctness, clarity, and usability
- Future enhancements (model retraining, deeper historical analysis, richer visuals) will be layered in incrementally

---

## Disclaimer

BGGTDM is a personal analytics and visualization project. It is not financial advice, gambling advice, or a betting service. All data is provided for informational and educational purposes only.
```
