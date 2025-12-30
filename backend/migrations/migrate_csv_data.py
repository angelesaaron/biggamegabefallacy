"""
Data migration script to populate database from existing CSV files.

This script reads your existing CSV data (2024 season) and populates
the PostgreSQL database tables.

Usage:
    python migrations/migrate_csv_data.py
"""

import asyncio
import pandas as pd
import os
from pathlib import Path
from sqlalchemy import select
from decimal import Decimal

from app.database import AsyncSessionLocal, engine, Base
from app.models import Player, Prediction, SportsbookOdds, GameResult, ValuePick
from app.utils.odds_conversion import decimal_to_american_odds, american_to_implied_probability


# Path to data directory (adjust if needed)
DATA_DIR = Path(__file__).parent.parent.parent / "data"


async def create_tables():
    """Create all database tables"""
    print("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ Tables created")


async def migrate_players():
    """Migrate player data from roster CSVs"""
    print("\n=== Migrating Players ===")

    async with AsyncSessionLocal() as session:
        # Find all roster CSV files
        roster_files = list((DATA_DIR / "rosters").glob("*.csv"))

        if not roster_files:
            print("⚠ No roster files found")
            return

        # Use the most recent roster file
        latest_roster = max(roster_files, key=os.path.getmtime)
        print(f"Loading roster from: {latest_roster}")

        df = pd.read_csv(latest_roster)

        players_added = 0
        for _, row in df.iterrows():
            # Check if player already exists
            result = await session.execute(
                select(Player).where(Player.player_id == str(row['playerId']))
            )
            existing_player = result.scalar_one_or_none()

            if existing_player:
                # Update existing player
                existing_player.full_name = row['fullName']
                existing_player.first_name = row.get('firstName')
                existing_player.last_name = row.get('lastName')
                existing_player.team_id = str(row['team_id'])
                existing_player.position = row.get('position')
                existing_player.height = int(row['height']) if pd.notna(row.get('height')) else None
                existing_player.weight = int(row['weight']) if pd.notna(row.get('weight')) else None
                existing_player.age = int(row['age']) if pd.notna(row.get('age')) else None
                existing_player.experience_years = int(row['exp']) if pd.notna(row.get('exp')) else None
                existing_player.active_status = bool(row.get('activestatus', 1) == 1)
                existing_player.headshot_url = row.get('headshot')
            else:
                # Create new player
                player = Player(
                    player_id=str(row['playerId']),
                    full_name=row['fullName'],
                    first_name=row.get('firstName'),
                    last_name=row.get('lastName'),
                    team_id=str(row['team_id']),
                    position=row.get('position'),
                    height=int(row['height']) if pd.notna(row.get('height')) else None,
                    weight=int(row['weight']) if pd.notna(row.get('weight')) else None,
                    age=int(row['age']) if pd.notna(row.get('age')) else None,
                    experience_years=int(row['exp']) if pd.notna(row.get('exp')) else None,
                    active_status=bool(row.get('activestatus', 1) == 1),
                    headshot_url=row.get('headshot'),
                )
                session.add(player)
                players_added += 1

        await session.commit()
        print(f"✓ Migrated {players_added} players")


async def migrate_model_odds():
    """Migrate model predictions from modelOdds CSV files"""
    print("\n=== Migrating Model Predictions ===")

    async with AsyncSessionLocal() as session:
        model_odds_files = list((DATA_DIR / "modelOdds").glob("*.csv"))

        if not model_odds_files:
            print("⚠ No model odds files found")
            return

        predictions_added = 0
        for file in model_odds_files:
            # Parse year and week from filename (e.g., 2024_NFL_Week14_BestOdds.csv)
            try:
                parts = file.stem.split('_')
                year = int(parts[0])
                week = int(parts[2].replace('Week', ''))
            except (IndexError, ValueError):
                print(f"⚠ Skipping {file.name} - couldn't parse year/week")
                continue

            print(f"Loading predictions from Week {week}, {year}...")
            df = pd.read_csv(file)

            for _, row in df.iterrows():
                # Check if prediction already exists
                result = await session.execute(
                    select(Prediction).where(
                        Prediction.player_id == str(row['Player']),
                        Prediction.season_year == year,
                        Prediction.week == week
                    )
                )
                existing_pred = result.scalar_one_or_none()

                if not existing_pred:
                    prediction = Prediction(
                        player_id=str(row['Player']),
                        season_year=year,
                        week=week,
                        td_likelihood=Decimal(str(row['TD_Likelihood'])),
                        model_odds=Decimal(str(row['Model_Odds'])),
                        favor=int(row['Favor'])
                    )
                    session.add(prediction)
                    predictions_added += 1

        await session.commit()
        print(f"✓ Migrated {predictions_added} predictions")


async def migrate_sportsbook_odds():
    """Migrate sportsbook odds from sportsbookOdds CSV files"""
    print("\n=== Migrating Sportsbook Odds ===")

    async with AsyncSessionLocal() as session:
        odds_files = list((DATA_DIR / "sportsbookOdds").glob("*.csv"))

        if not odds_files:
            print("⚠ No sportsbook odds files found")
            return

        odds_added = 0
        for file in odds_files:
            # Parse year and week from filename (e.g., odds_2024_week14.csv)
            try:
                parts = file.stem.split('_')
                year = int(parts[1])
                week = int(parts[2].replace('week', ''))
            except (IndexError, ValueError):
                print(f"⚠ Skipping {file.name} - couldn't parse year/week")
                continue

            print(f"Loading sportsbook odds from Week {week}, {year}...")
            df = pd.read_csv(file)

            # Sportsbook columns (excluding Player column)
            sportsbook_cols = [col for col in df.columns if col != 'Player']

            for _, row in df.iterrows():
                player_name = row['Player']

                for sportsbook in sportsbook_cols:
                    odds_value = row[sportsbook]

                    # Skip if odds not available
                    if pd.isna(odds_value) or odds_value == 'N/A':
                        continue

                    # Check if odds already exist
                    result = await session.execute(
                        select(SportsbookOdds).where(
                            SportsbookOdds.player_id == str(player_name),
                            SportsbookOdds.season_year == year,
                            SportsbookOdds.week == week,
                            SportsbookOdds.sportsbook == sportsbook
                        )
                    )
                    existing_odds = result.scalar_one_or_none()

                    if not existing_odds:
                        odds_entry = SportsbookOdds(
                            player_id=str(player_name),
                            season_year=year,
                            week=week,
                            sportsbook=sportsbook,
                            odds=Decimal(str(odds_value))
                        )
                        session.add(odds_entry)
                        odds_added += 1

        await session.commit()
        print(f"✓ Migrated {odds_added} sportsbook odds entries")


async def migrate_value_picks():
    """Migrate value picks from historicalOdds CSV files"""
    print("\n=== Migrating Value Picks ===")

    async with AsyncSessionLocal() as session:
        historical_odds_dir = DATA_DIR / "historicalOdds"

        if not historical_odds_dir.exists():
            print("⚠ No historicalOdds directory found")
            return

        picks_added = 0
        for sportsbook_dir in historical_odds_dir.iterdir():
            if not sportsbook_dir.is_dir():
                continue

            sportsbook = sportsbook_dir.name
            print(f"Processing {sportsbook}...")

            for file in sportsbook_dir.glob("*.csv"):
                # Parse year and week from filename
                try:
                    parts = file.stem.split('_')
                    year = int(parts[0])
                    week = int(parts[1].replace('week', ''))
                except (IndexError, ValueError):
                    continue

                df = pd.read_csv(file)

                # Skip if required columns missing
                required_cols = ['Player', 'Model_Odds', sportsbook, 'WeightedValue']
                if not all(col in df.columns for col in required_cols):
                    continue

                for _, row in df.iterrows():
                    player_name = row['Player']
                    model_odds = row['Model_Odds']
                    sportsbook_odds = row[sportsbook]

                    # Skip invalid rows
                    if pd.isna(model_odds) or pd.isna(sportsbook_odds):
                        continue

                    # Check if value pick already exists
                    result = await session.execute(
                        select(ValuePick).where(
                            ValuePick.player_id == str(player_name),
                            ValuePick.season_year == year,
                            ValuePick.week == week,
                            ValuePick.sportsbook == sportsbook
                        )
                    )
                    existing_pick = result.scalar_one_or_none()

                    if not existing_pick:
                        value_pick = ValuePick(
                            player_id=str(player_name),
                            season_year=year,
                            week=week,
                            sportsbook=sportsbook,
                            model_odds=Decimal(str(model_odds)),
                            sportsbook_odds=Decimal(str(sportsbook_odds)),
                            model_probability=Decimal(str(american_to_implied_probability(float(model_odds)))),
                            sportsbook_probability=Decimal(str(american_to_implied_probability(float(sportsbook_odds)))),
                            weighted_value=Decimal(str(row['WeightedValue'])) if pd.notna(row.get('WeightedValue')) else None
                        )
                        session.add(value_pick)
                        picks_added += 1

        await session.commit()
        print(f"✓ Migrated {picks_added} value picks")


async def migrate_game_results():
    """Migrate actual game results from roster_game_logs.csv"""
    print("\n=== Migrating Game Results ===")

    game_logs_file = DATA_DIR / "roster_game_logs.csv"

    if not game_logs_file.exists():
        print("⚠ roster_game_logs.csv not found")
        return

    async with AsyncSessionLocal() as session:
        df = pd.read_csv(game_logs_file)

        results_added = 0
        for _, row in df.iterrows():
            # Parse year and week
            year = int(row['seasonYr']) if pd.notna(row.get('seasonYr')) else None
            week = int(row['week']) if pd.notna(row.get('week')) else None

            if not year or not week:
                continue

            # Only migrate 2024 data
            if year != 2024:
                continue

            player_name = row['fullName']

            # Check if result already exists
            result = await session.execute(
                select(GameResult).where(
                    GameResult.player_id == str(player_name),
                    GameResult.season_year == year,
                    GameResult.week == week
                )
            )
            existing_result = result.scalar_one_or_none()

            if not existing_result:
                game_result = GameResult(
                    player_id=str(player_name),
                    season_year=year,
                    week=week,
                    receiving_touchdowns=int(row.get('receivingTouchdowns', 0)),
                    receptions=int(row.get('receptions', 0)) if pd.notna(row.get('receptions')) else None,
                    receiving_yards=int(row.get('receivingYards', 0)) if pd.notna(row.get('receivingYards')) else None,
                    targets=int(row.get('receivingTargets', 0)) if pd.notna(row.get('receivingTargets')) else None,
                )
                session.add(game_result)
                results_added += 1

        await session.commit()
        print(f"✓ Migrated {results_added} game results")


async def main():
    """Run all migrations"""
    print("=" * 60)
    print("BGGTDM Data Migration Script")
    print("=" * 60)

    await create_tables()
    await migrate_players()
    await migrate_model_odds()
    await migrate_sportsbook_odds()
    await migrate_value_picks()
    await migrate_game_results()

    print("\n" + "=" * 60)
    print("✓ Migration Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
