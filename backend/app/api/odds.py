from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import Dict, List
import asyncio

from app.database import get_db
from app.models.odds import SportsbookOdds
from app.models.schedule import Schedule
from app.utils.nfl_calendar import get_current_nfl_week
from app.utils.tank01_client import Tank01Client
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


async def sync_odds_for_week_task(season: int, week: int):
    """
    Background task to sync odds for a specific week.
    """
    from app.database import AsyncSessionLocal
    from app.models.player import Player

    logger.info(f"Starting background odds sync for {season} Week {week}")

    client = Tank01Client()

    try:
        async with AsyncSessionLocal() as db:
            # Get all games for this week
            result = await db.execute(
                select(Schedule)
                .where(Schedule.season_year == season, Schedule.week == week)
            )
            games = result.scalars().all()

            if not games:
                logger.warning(f"No games found for {season} Week {week}")
                return

            # Get all valid player IDs to check foreign key constraints
            player_result = await db.execute(select(Player.player_id))
            valid_player_ids = {row[0] for row in player_result.all()}
            logger.info(f"Found {len(valid_player_ids)} valid players in database")

            # Delete existing odds for this week (refresh)
            await db.execute(
                delete(SportsbookOdds)
                .where(SportsbookOdds.season_year == season, SportsbookOdds.week == week)
            )
            await db.commit()

            total_saved = 0
            skipped_players = set()

            for game in games:
                game_id = game.game_id  # Store game_id before potential rollback

                try:
                    # Fetch odds using gameID
                    response = await client.get_betting_odds(game_id=game_id)

                    if not response or 'body' not in response:
                        continue

                    # Handle both dict and list response formats
                    body = response.get('body')
                    if not body:
                        continue

                    if isinstance(body, dict):
                        game_data = body if body.get('gameID') == game_id else None
                    elif isinstance(body, list):
                        game_data = next((g for g in body if g.get('gameID') == game_id), None)
                    else:
                        continue

                    if not game_data:
                        continue

                    player_props = game_data.get('playerProps', [])

                    for prop in player_props:
                        player_id = prop.get('playerID')
                        anytd = prop.get('propBets', {}).get('anytd')

                        if not player_id or not anytd:
                            continue

                        # Skip players not in our database to avoid foreign key violations
                        if player_id not in valid_player_ids:
                            skipped_players.add(player_id)
                            continue

                        # Parse odds
                        try:
                            if anytd == "even":
                                odds_value = 100
                            elif isinstance(anytd, str) and (anytd.startswith('+') or anytd.startswith('-')):
                                odds_value = int(anytd)
                            else:
                                odds_value = int(anytd)
                        except (ValueError, TypeError):
                            continue

                        # Save for both DraftKings and FanDuel
                        for sportsbook in ['draftkings', 'fanduel']:
                            odds_record = SportsbookOdds(
                                player_id=player_id,
                                game_id=game_id,
                                season_year=season,
                                week=week,
                                sportsbook=sportsbook,
                                anytime_td_odds=odds_value
                            )
                            db.add(odds_record)

                        total_saved += 2

                    await db.commit()

                except Exception as e:
                    logger.error(f"Error syncing odds for game {game_id}: {str(e)}")
                    await db.rollback()
                    continue

            if skipped_players:
                logger.warning(f"Skipped {len(skipped_players)} players not in database")

            logger.info(f"Background odds sync complete: {total_saved} records saved")

    except Exception as e:
        logger.error(f"Background odds sync failed: {str(e)}")
    finally:
        await client.close()


@router.post("/refresh")
async def refresh_odds(
    background_tasks: BackgroundTasks,
    week: int | None = Query(None, description="Week to refresh (defaults to current week)"),
    year: int | None = Query(None, description="Year to refresh (defaults to current year)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually refresh sportsbook odds for a specific week.
    Runs in background and returns immediately.
    """
    if week is None or year is None:
        year, week = get_current_nfl_week()

    # Start background task
    background_tasks.add_task(sync_odds_for_week_task, year, week)

    return {
        "status": "started",
        "message": f"Refreshing odds for {year} Week {week} in background",
        "year": year,
        "week": week
    }


@router.get("/current")
async def get_current_odds(
    sportsbook: str = Query("draftkings", description="Sportsbook name (draftkings or fanduel)"),
    db: AsyncSession = Depends(get_db)
):
    """Get current week sportsbook odds"""
    year, week = get_current_nfl_week()

    result = await db.execute(
        select(SportsbookOdds)
        .where(
            SportsbookOdds.season_year == year,
            SportsbookOdds.week == week,
            SportsbookOdds.sportsbook == sportsbook
        )
    )
    odds_records = result.scalars().all()

    return {
        "year": year,
        "week": week,
        "sportsbook": sportsbook,
        "odds": [
            {
                "player_id": record.player_id,
                "game_id": record.game_id,
                "anytime_td_odds": record.anytime_td_odds,
                "fetched_at": record.fetched_at.isoformat()
            }
            for record in odds_records
        ]
    }


@router.get("/comparison/{player_id}")
async def get_odds_comparison(
    player_id: str,
    week: int | None = Query(None, description="Week (defaults to current)"),
    year: int | None = Query(None, description="Year (defaults to current)"),
    db: AsyncSession = Depends(get_db)
):
    """Get model vs sportsbook odds comparison for a player"""
    if week is None or year is None:
        year, week = get_current_nfl_week()

    # Get sportsbook odds for this player
    result = await db.execute(
        select(SportsbookOdds)
        .where(
            SportsbookOdds.player_id == player_id,
            SportsbookOdds.season_year == year,
            SportsbookOdds.week == week
        )
    )
    odds_records = result.scalars().all()

    sportsbook_odds = {
        record.sportsbook: record.anytime_td_odds
        for record in odds_records
    }

    return {
        "player_id": player_id,
        "year": year,
        "week": week,
        "sportsbook_odds": sportsbook_odds
    }
