"""
Unit tests for pure-function parsing helpers in tank01_client.py.

No I/O, no mocking — these are stateless transforms.
"""

import pytest

from app.utils.tank01_client import (
    _normalise_status,
    parse_anytime_td_odds,
    parse_game_from_schedule,
    parse_game_logs_from_box_score,
    parse_player_from_roster,
    parse_teams_from_game_id,
)


class TestParseTeamsFromGameId:
    def test_standard_format(self):
        away, home = parse_teams_from_game_id("20251107_MIN@CHI")
        assert away == "MIN"
        assert home == "CHI"

    def test_single_char_abbrev(self):
        away, home = parse_teams_from_game_id("20251107_GB@LA")
        assert away == "GB"
        assert home == "LA"


class TestNormaliseStatus:
    def test_final_variants(self):
        assert _normalise_status("Final") == "final"
        assert _normalise_status("FINAL") == "final"
        assert _normalise_status("Completed") == "final"
        assert _normalise_status("completed and final") == "final"

    def test_in_progress_variants(self):
        assert _normalise_status("In Progress") == "in_progress"
        assert _normalise_status("Live") == "in_progress"
        assert _normalise_status("4th Quarter") == "in_progress"
        assert _normalise_status("Halftime") == "in_progress"

    def test_scheduled_variants(self):
        assert _normalise_status("Scheduled") == "scheduled"
        assert _normalise_status("") == "scheduled"
        assert _normalise_status("Postponed") == "scheduled"

    def test_none_safe(self):
        assert _normalise_status(None) == "scheduled"


class TestParsePlayerFromRoster:
    def _raw(self, **overrides):
        base = {
            "playerID": "12345",
            "longName": "Justin Jefferson",
            "pos": "WR",
            "team": "MIN",
            "exp": "5",
            "isFreeAgent": "False",
            "espnHeadshot": "https://example.com/headshot.jpg",
        }
        base.update(overrides)
        return base

    def test_basic_fields(self):
        r = parse_player_from_roster(self._raw())
        assert r["player_id"] == "12345"
        assert r["full_name"] == "Justin Jefferson"
        assert r["position"] == "WR"
        assert r["team"] == "MIN"
        assert r["experience"] == 5
        assert r["active"] is True
        assert r["is_te"] is False
        assert r["headshot_url"] == "https://example.com/headshot.jpg"

    def test_te_position_sets_is_te(self):
        r = parse_player_from_roster(self._raw(pos="TE"))
        assert r["is_te"] is True
        assert r["position"] == "TE"

    def test_rookie_experience(self):
        r = parse_player_from_roster(self._raw(exp="R"))
        assert r["experience"] == 0

    def test_numeric_string_experience(self):
        r = parse_player_from_roster(self._raw(exp="3"))
        assert r["experience"] == 3

    def test_invalid_exp_is_none(self):
        r = parse_player_from_roster(self._raw(exp="N/A"))
        assert r["experience"] is None

    def test_free_agent_is_inactive(self):
        r = parse_player_from_roster(self._raw(isFreeAgent="True"))
        assert r["active"] is False

    def test_missing_player_id_returns_none(self):
        raw = self._raw()
        raw.pop("playerID")
        r = parse_player_from_roster(raw)
        assert r["player_id"] is None

    def test_falls_back_to_espn_name(self):
        raw = self._raw()
        raw.pop("longName")
        raw["espnName"] = "J.Jefferson"
        r = parse_player_from_roster(raw)
        assert r["full_name"] == "J.Jefferson"


class TestParseGameFromSchedule:
    def test_basic_fields(self):
        raw = {
            "gameID": "20251107_MIN@CHI",
            "home": "CHI",
            "away": "MIN",
            "gameStatus": "Final",
        }
        r = parse_game_from_schedule(raw, season=2025, week=7)
        assert r["game_id"] == "20251107_MIN@CHI"
        assert r["season"] == 2025
        assert r["week"] == 7
        assert r["home_team"] == "CHI"
        assert r["away_team"] == "MIN"
        assert r["status"] == "final"
        assert r["game_date"] == "20251107"
        assert r["season_type"] == "reg"

    def test_status_normalised(self):
        raw = {"gameID": "20251107_MIN@CHI", "home": "CHI", "away": "MIN", "gameStatus": "Scheduled"}
        r = parse_game_from_schedule(raw, season=2025, week=7)
        assert r["status"] == "scheduled"

    def test_missing_game_id_produces_none_date(self):
        raw = {"gameID": "", "home": "CHI", "away": "MIN", "gameStatus": "Final"}
        r = parse_game_from_schedule(raw, season=2025, week=7)
        assert r["game_date"] is None


class TestParseGameLogsFromBoxScore:
    def _box_score(self):
        return {
            "playerStats": {
                "111": {
                    "team": "MIN",
                    "Receiving": {
                        "targets": "7",
                        "receptions": "5",
                        "recYds": "80",
                        "recTD": "1",
                        "longRec": "30",
                    },
                },
                "222": {
                    "team": "CHI",
                    "Receiving": {
                        "targets": "3",
                        "receptions": "2",
                        "recYds": "25",
                        "recTD": "0",
                        "longRec": None,
                    },
                },
                "333": {
                    "team": "MIN",
                    # No Receiving key — skip (e.g. lineman with no catches)
                },
                "444": {
                    "team": "CHI",
                    "Receiving": None,  # Explicit None — skip
                },
            }
        }

    def test_parses_players_with_receiving(self):
        logs = parse_game_logs_from_box_score(
            self._box_score(), "20251107_MIN@CHI", season=2025, week=7
        )
        assert len(logs) == 2
        pids = {l["player_id"] for l in logs}
        assert pids == {"111", "222"}

    def test_stats_parsed_correctly(self):
        logs = parse_game_logs_from_box_score(
            self._box_score(), "20251107_MIN@CHI", season=2025, week=7
        )
        p111 = next(l for l in logs if l["player_id"] == "111")
        assert p111["targets"] == 7
        assert p111["receptions"] == 5
        assert p111["rec_yards"] == 80
        assert p111["rec_tds"] == 1
        assert p111["long_rec"] == 30

    def test_null_long_rec_is_none(self):
        logs = parse_game_logs_from_box_score(
            self._box_score(), "20251107_MIN@CHI", season=2025, week=7
        )
        p222 = next(l for l in logs if l["player_id"] == "222")
        assert p222["long_rec"] is None

    def test_home_away_flag(self):
        # game_id = YYYYMMDD_AWAY@HOME → MIN=away, CHI=home
        logs = parse_game_logs_from_box_score(
            self._box_score(), "20251107_MIN@CHI", season=2025, week=7
        )
        p111 = next(l for l in logs if l["player_id"] == "111")  # MIN = away
        p222 = next(l for l in logs if l["player_id"] == "222")  # CHI = home
        assert p111["is_home"] is False
        assert p222["is_home"] is True

    def test_season_week_attached(self):
        logs = parse_game_logs_from_box_score(
            self._box_score(), "20251107_MIN@CHI", season=2025, week=7
        )
        for log in logs:
            assert log["season"] == 2025
            assert log["week"] == 7

    def test_empty_player_stats(self):
        box = {"playerStats": {}}
        logs = parse_game_logs_from_box_score(box, "20251107_MIN@CHI", 2025, 7)
        assert logs == []


class TestParseAnytimeTdOdds:
    def test_basic_parsing(self):
        raw = [
            {
                "gameID": "20251107_MIN@CHI",
                "playerProps": [
                    {"playerID": "111", "propBets": {"anytd": "250"}},
                    {"playerID": "222", "propBets": {"anytd": "-130"}},
                ],
            }
        ]
        results = parse_anytime_td_odds(raw)
        assert len(results) == 2
        assert results[0] == {"player_id": "111", "game_id": "20251107_MIN@CHI", "odds": 250}
        assert results[1] == {"player_id": "222", "game_id": "20251107_MIN@CHI", "odds": -130}

    def test_missing_odds_skipped(self):
        raw = [
            {
                "gameID": "20251107_MIN@CHI",
                "playerProps": [
                    {"playerID": "111", "propBets": {"anytd": None}},
                    {"playerID": "222", "propBets": {}},
                ],
            }
        ]
        assert parse_anytime_td_odds(raw) == []

    def test_missing_player_id_skipped(self):
        raw = [
            {
                "gameID": "20251107_MIN@CHI",
                "playerProps": [
                    {"playerID": None, "propBets": {"anytd": "250"}},
                ],
            }
        ]
        assert parse_anytime_td_odds(raw) == []

    def test_non_numeric_odds_skipped(self):
        raw = [
            {
                "gameID": "20251107_MIN@CHI",
                "playerProps": [
                    {"playerID": "111", "propBets": {"anytd": "N/A"}},
                ],
            }
        ]
        assert parse_anytime_td_odds(raw) == []

    def test_multiple_games(self):
        raw = [
            {
                "gameID": "20251107_MIN@CHI",
                "playerProps": [{"playerID": "111", "propBets": {"anytd": "200"}}],
            },
            {
                "gameID": "20251107_SF@SEA",
                "playerProps": [{"playerID": "222", "propBets": {"anytd": "-110"}}],
            },
        ]
        results = parse_anytime_td_odds(raw)
        assert len(results) == 2
        assert {r["game_id"] for r in results} == {"20251107_MIN@CHI", "20251107_SF@SEA"}
