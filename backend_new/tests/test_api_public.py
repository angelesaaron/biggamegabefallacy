"""
Integration tests for the public API router.

DB queries are mocked via the public_client fixture.
Tests cover: predictions, players, player detail, player history.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


# ── Shared object builders ────────────────────────────────────────────────────

def make_player(
    player_id="p1",
    full_name="Justin Jefferson",
    position="WR",
    team="MIN",
    is_te=False,
    draft_round=1,
    experience=5,
    headshot_url="https://example.com/p1.jpg",
    active=True,
):
    return SimpleNamespace(
        player_id=player_id,
        full_name=full_name,
        position=position,
        team=team,
        is_te=is_te,
        draft_round=draft_round,
        experience=experience,
        headshot_url=headshot_url,
        active=active,
    )


def make_prediction(
    id=1,
    player_id="p1",
    season=2025,
    week=7,
    model_version="v2_xgb",
    final_prob=0.25,
    is_low_confidence=False,
):
    return SimpleNamespace(
        id=id,
        player_id=player_id,
        season=season,
        week=week,
        model_version=model_version,
        final_prob=final_prob,
        is_low_confidence=is_low_confidence,
    )


def make_odds(
    player_id="p1",
    game_id="20251107_MIN@CHI",
    season=2025,
    week=7,
    sportsbook="consensus",
    odds=250,
    implied_prob=0.2857,
):
    return SimpleNamespace(
        player_id=player_id,
        game_id=game_id,
        season=season,
        week=week,
        sportsbook=sportsbook,
        odds=odds,
        implied_prob=implied_prob,
    )


def _mock_execute(mock_db, *side_effects):
    """Configure mock_db.execute to return successive results."""
    mock_results = []
    for data in side_effects:
        result = MagicMock()
        if isinstance(data, list) and data and isinstance(data[0], tuple):
            # For joined queries returning (Model, Model) rows → .all()
            result.all.return_value = data
        else:
            # For scalar queries → .scalars().all()
            result.scalars.return_value.all.return_value = data
        mock_results.append(result)

    mock_db.execute = AsyncMock(side_effect=mock_results)


# ── GET /predictions/{season}/{week} ──────────────────────────────────────────

class TestGetPredictions:
    async def test_returns_empty_when_no_predictions(self, public_client, mock_db):
        pred_result = MagicMock()
        pred_result.all.return_value = []
        mock_db.execute = AsyncMock(return_value=pred_result)

        resp = await public_client.get("/predictions/2025/7")
        assert resp.status_code == 200
        body = resp.json()
        assert body["season"] == 2025
        assert body["week"] == 7
        assert body["count"] == 0
        assert body["predictions"] == []

    async def test_returns_predictions_ranked_by_prob(self, public_client, mock_db):
        player1 = make_player(player_id="p1", full_name="Justin Jefferson", team="MIN")
        player2 = make_player(player_id="p2", full_name="Davante Adams", team="LV")
        pred1 = make_prediction(id=1, player_id="p1", final_prob=0.40)
        pred2 = make_prediction(id=2, player_id="p2", final_prob=0.25)

        # First execute: joined predictions+players (already sorted by final_prob desc)
        pred_result = MagicMock()
        pred_result.all.return_value = [(pred1, player1), (pred2, player2)]

        # Second execute: odds query (empty — no odds available)
        odds_result = MagicMock()
        odds_result.scalars.return_value.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[pred_result, odds_result])

        resp = await public_client.get("/predictions/2025/7")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 2
        assert body["predictions"][0]["player_id"] == "p1"
        assert body["predictions"][0]["final_prob"] == pytest.approx(0.40, rel=1e-4)

    async def test_model_odds_computed_from_final_prob(self, public_client, mock_db):
        player = make_player(player_id="p1")
        pred = make_prediction(player_id="p1", final_prob=0.25)

        pred_result = MagicMock()
        pred_result.all.return_value = [(pred, player)]
        odds_result = MagicMock()
        odds_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(side_effect=[pred_result, odds_result])

        resp = await public_client.get("/predictions/2025/7")
        body = resp.json()
        # prob=0.25 → +300 American
        assert body["predictions"][0]["model_odds"] == 300

    async def test_favor_computed_when_odds_present(self, public_client, mock_db):
        player = make_player(player_id="p1")
        pred = make_prediction(player_id="p1", final_prob=0.30)
        market_odds = make_odds(player_id="p1", implied_prob=0.25)

        pred_result = MagicMock()
        pred_result.all.return_value = [(pred, player)]
        odds_result = MagicMock()
        odds_result.scalars.return_value.all.return_value = [market_odds]
        mock_db.execute = AsyncMock(side_effect=[pred_result, odds_result])

        resp = await public_client.get("/predictions/2025/7")
        row = resp.json()["predictions"][0]
        # favor = 0.30 - 0.25 = 0.05
        assert row["favor"] == pytest.approx(0.05, abs=1e-4)
        assert row["sportsbook_odds"] == market_odds.odds
        assert row["implied_prob"] == pytest.approx(0.25, rel=1e-4)

    async def test_favor_none_when_no_odds(self, public_client, mock_db):
        player = make_player(player_id="p1")
        pred = make_prediction(player_id="p1", final_prob=0.20)

        pred_result = MagicMock()
        pred_result.all.return_value = [(pred, player)]
        odds_result = MagicMock()
        odds_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(side_effect=[pred_result, odds_result])

        resp = await public_client.get("/predictions/2025/7")
        row = resp.json()["predictions"][0]
        assert row["favor"] is None
        assert row["sportsbook_odds"] is None

    async def test_response_includes_player_fields(self, public_client, mock_db):
        player = make_player(player_id="p1", full_name="Travis Kelce", position="TE", team="KC")
        pred = make_prediction(player_id="p1")

        pred_result = MagicMock()
        pred_result.all.return_value = [(pred, player)]
        odds_result = MagicMock()
        odds_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(side_effect=[pred_result, odds_result])

        resp = await public_client.get("/predictions/2025/7")
        row = resp.json()["predictions"][0]
        assert row["full_name"] == "Travis Kelce"
        assert row["position"] == "TE"
        assert row["team"] == "KC"
        assert row["model_version"] == "v2_xgb"

    async def test_season_below_range_rejected(self, public_client):
        resp = await public_client.get("/predictions/2019/7")
        assert resp.status_code == 422

    async def test_week_above_range_rejected(self, public_client):
        resp = await public_client.get("/predictions/2025/19")
        assert resp.status_code == 422

    async def test_week_zero_rejected(self, public_client):
        resp = await public_client.get("/predictions/2025/0")
        assert resp.status_code == 422


# ── GET /players ──────────────────────────────────────────────────────────────

class TestListPlayers:
    async def test_returns_active_players(self, public_client, mock_db):
        players = [
            make_player(player_id="p1", full_name="Justin Jefferson"),
            make_player(player_id="p2", full_name="Travis Kelce", position="TE"),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = players
        mock_db.execute = AsyncMock(return_value=mock_result)

        resp = await public_client.get("/players")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert body[0]["player_id"] == "p1"

    async def test_player_fields_in_response(self, public_client, mock_db):
        player = make_player(
            player_id="p1",
            full_name="Justin Jefferson",
            position="WR",
            team="MIN",
            draft_round=1,
            experience=5,
            headshot_url="https://example.com/p1.jpg",
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [player]
        mock_db.execute = AsyncMock(return_value=mock_result)

        resp = await public_client.get("/players")
        body = resp.json()
        row = body[0]
        assert row["player_id"] == "p1"
        assert row["full_name"] == "Justin Jefferson"
        assert row["position"] == "WR"
        assert row["team"] == "MIN"
        assert row["draft_round"] == 1
        assert row["experience"] == 5
        assert row["headshot_url"] == "https://example.com/p1.jpg"

    async def test_empty_list_when_no_players(self, public_client, mock_db):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        resp = await public_client.get("/players")
        assert resp.status_code == 200
        assert resp.json() == []


# ── GET /players/{player_id} ──────────────────────────────────────────────────

class TestGetPlayer:
    async def test_returns_player_when_found(self, public_client, mock_db):
        player = make_player(player_id="p1", full_name="Justin Jefferson")
        mock_db.get = AsyncMock(return_value=player)

        resp = await public_client.get("/players/p1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["player_id"] == "p1"
        assert body["full_name"] == "Justin Jefferson"

    async def test_returns_404_when_not_found(self, public_client, mock_db):
        mock_db.get = AsyncMock(return_value=None)

        resp = await public_client.get("/players/nonexistent")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    async def test_optional_fields_can_be_null(self, public_client, mock_db):
        player = make_player(player_id="p1", team=None, draft_round=None, headshot_url=None)
        mock_db.get = AsyncMock(return_value=player)

        resp = await public_client.get("/players/p1")
        body = resp.json()
        assert body["team"] is None
        assert body["draft_round"] is None
        assert body["headshot_url"] is None


# ── GET /players/{player_id}/history ─────────────────────────────────────────

class TestGetPlayerHistory:
    async def test_returns_predictions_newest_first(self, public_client, mock_db):
        player = make_player(player_id="p1")
        pred_w7 = make_prediction(id=2, player_id="p1", season=2025, week=7, final_prob=0.30)
        pred_w6 = make_prediction(id=1, player_id="p1", season=2025, week=6, final_prob=0.22)

        mock_db.get = AsyncMock(return_value=player)
        history_result = MagicMock()
        history_result.scalars.return_value.all.return_value = [pred_w7, pred_w6]
        mock_db.execute = AsyncMock(return_value=history_result)

        resp = await public_client.get("/players/p1/history")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert body[0]["week"] == 7
        assert body[0]["final_prob"] == pytest.approx(0.30, rel=1e-4)

    async def test_returns_404_for_unknown_player(self, public_client, mock_db):
        mock_db.get = AsyncMock(return_value=None)

        resp = await public_client.get("/players/nonexistent/history")
        assert resp.status_code == 404

    async def test_history_row_has_model_odds(self, public_client, mock_db):
        player = make_player(player_id="p1")
        pred = make_prediction(player_id="p1", season=2025, week=7, final_prob=0.25)

        mock_db.get = AsyncMock(return_value=player)
        history_result = MagicMock()
        history_result.scalars.return_value.all.return_value = [pred]
        mock_db.execute = AsyncMock(return_value=history_result)

        resp = await public_client.get("/players/p1/history")
        body = resp.json()
        # model_odds computed from final_prob=0.25 → +300
        assert body[0]["model_odds"] == 300

    async def test_history_includes_is_low_confidence(self, public_client, mock_db):
        player = make_player(player_id="p1")
        pred = make_prediction(player_id="p1", is_low_confidence=True)

        mock_db.get = AsyncMock(return_value=player)
        history_result = MagicMock()
        history_result.scalars.return_value.all.return_value = [pred]
        mock_db.execute = AsyncMock(return_value=history_result)

        resp = await public_client.get("/players/p1/history")
        assert resp.json()[0]["is_low_confidence"] is True

    async def test_season_filter_accepted(self, public_client, mock_db):
        player = make_player(player_id="p1")
        mock_db.get = AsyncMock(return_value=player)
        history_result = MagicMock()
        history_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=history_result)

        resp = await public_client.get("/players/p1/history?season=2025")
        assert resp.status_code == 200

    async def test_empty_history_returns_empty_list(self, public_client, mock_db):
        player = make_player(player_id="p1")
        mock_db.get = AsyncMock(return_value=player)
        history_result = MagicMock()
        history_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=history_result)

        resp = await public_client.get("/players/p1/history")
        assert resp.status_code == 200
        assert resp.json() == []


# ── GET /health ───────────────────────────────────────────────────────────────

class TestHealthEndpoint:
    async def test_health_returns_200_structure(self, public_client):
        # Health check uses its own DB connection, not the mocked get_db.
        # We just verify the response structure is correct when DB may fail.
        resp = await public_client.get("/health")
        # Will be 200 regardless of db status — just degraded
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body
        assert "version" in body
        assert "db" in body
        assert body["status"] in ("ok", "degraded")
        assert body["version"] == "2.0.0"
