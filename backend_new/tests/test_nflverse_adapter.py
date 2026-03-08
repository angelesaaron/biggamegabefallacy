"""
Unit tests for nflverse_adapter pure functions.

No DB connections, no nflreadpy calls — fully mocked/faked.
"""

import pytest
from unittest.mock import MagicMock, patch
import pandas as pd

from app.utils.nflverse_adapter import (
    _build_snap_resolver,
    _build_pbp_resolver,
    _resolve_snap,
    _resolve_rz,
    _fetch_player_bridge,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

PFR_BRIDGE = {"BrowAJ00": "4047646", "HillTy00": "3054211"}
GSIS_BRIDGE = {"00-0035676": "4047646", "00-0033280": "3054211"}


# ── _build_snap_resolver ──────────────────────────────────────────────────────

def test_snap_resolver_id_primary():
    resolve = _build_snap_resolver(PFR_BRIDGE)
    assert resolve("BrowAJ00") == "4047646"


def test_snap_resolver_known_player():
    resolve = _build_snap_resolver(PFR_BRIDGE)
    assert resolve("HillTy00") == "3054211"


def test_snap_resolver_unmatched():
    resolve = _build_snap_resolver(PFR_BRIDGE)
    assert resolve("XXXXXX00") is None


def test_snap_resolver_none_pfr_id():
    resolve = _build_snap_resolver(PFR_BRIDGE)
    assert resolve(None) is None


# ── _build_pbp_resolver ───────────────────────────────────────────────────────

def test_pbp_resolver_id_primary():
    resolve = _build_pbp_resolver(GSIS_BRIDGE)
    assert resolve("00-0035676") == "4047646"


def test_pbp_resolver_known_player():
    resolve = _build_pbp_resolver(GSIS_BRIDGE)
    assert resolve("00-0033280") == "3054211"


def test_pbp_resolver_unmatched():
    resolve = _build_pbp_resolver(GSIS_BRIDGE)
    assert resolve("00-9999999") is None


def test_pbp_resolver_none_gsis_id():
    resolve = _build_pbp_resolver(GSIS_BRIDGE)
    assert resolve(None) is None


# ── _resolve_snap ─────────────────────────────────────────────────────────────

def test_resolve_snap_builds_records():
    rows = [
        {"pfr_player_id": "BrowAJ00", "player": "A.J. Brown", "team": "PHI",
         "season": 2024, "week": 7, "offense_pct": 0.88},
        {"pfr_player_id": "HillTy00", "player": "Tyreek Hill", "team": "MIA",
         "season": 2024, "week": 7, "offense_pct": 0.92},
    ]
    resolve = _build_snap_resolver(PFR_BRIDGE)
    result, unmatched = _resolve_snap(rows, resolve)

    assert len(result) == 2
    assert unmatched == []

    rec = result[("4047646", 2024, 7)]
    assert rec.player_id == "4047646"
    assert rec.team == "PHI"
    assert rec.snap_pct == pytest.approx(0.88)


def test_resolve_snap_unmatched_deduped():
    rows = [
        {"pfr_player_id": None, "player": "Unknown Guy", "team": "NE", "season": 2024, "week": 1, "offense_pct": 0.5},
        {"pfr_player_id": None, "player": "Unknown Guy", "team": "NE", "season": 2024, "week": 2, "offense_pct": 0.5},
    ]
    resolve = _build_snap_resolver({})
    result, unmatched = _resolve_snap(rows, resolve)

    assert len(result) == 0
    assert unmatched == ["Unknown Guy"]  # deduplicated


# ── _resolve_rz ───────────────────────────────────────────────────────────────

def test_resolve_rz_accumulates_dupes():
    """Duplicate (player_id, season, week) keys are summed."""
    rows = [
        {"gsis_id": "00-0035676", "name_short": "A.Brown", "team": "PHI",
         "season": 2024, "week": 7, "rz_targets": 3, "rz_tds": 1},
        {"gsis_id": "00-0035676", "name_short": "A.Brown", "team": "PHI",
         "season": 2024, "week": 7, "rz_targets": 2, "rz_tds": 0},
    ]
    resolve = _build_pbp_resolver(GSIS_BRIDGE)
    result, unmatched = _resolve_rz(rows, resolve)

    assert unmatched == []
    rec = result[("4047646", 2024, 7)]
    assert rec.rz_targets == 5
    assert rec.rz_tds == 1


def test_resolve_rz_unmatched():
    rows = [
        {"gsis_id": None, "name_short": "Z.Nobody", "team": "NE",
         "season": 2024, "week": 1, "rz_targets": 1, "rz_tds": 0},
    ]
    resolve = _build_pbp_resolver({})
    result, unmatched = _resolve_rz(rows, resolve)

    assert len(result) == 0
    assert unmatched == ["Z.Nobody"]


# ── _fetch_player_bridge ──────────────────────────────────────────────────────

def test_fetch_player_bridge_structure():
    """Mock nfl.load_players() and verify dict shapes."""
    mock_df = pd.DataFrame([
        {"gsis_id": "00-0035676", "pfr_id": "BrowAJ00", "espn_id": 4047646.0},
        {"gsis_id": "00-0033280", "pfr_id": "HillTy00", "espn_id": 3054211.0},
        {"gsis_id": None,         "pfr_id": "SomePFR0", "espn_id": 1111111.0},
        {"gsis_id": "00-0099999", "pfr_id": None,       "espn_id": 2222222.0},
        {"gsis_id": "00-0000000", "pfr_id": "NullESP0", "espn_id": None},
    ])

    mock_polars = MagicMock()
    mock_polars.to_pandas.return_value = mock_df

    with patch("app.utils.nflverse_adapter._configure_nflreadpy_cache"), \
         patch("os.makedirs"), \
         patch("nflreadpy.load_players", return_value=mock_polars):
        gsis_map, pfr_map = _fetch_player_bridge("/tmp/fake_cache")

    # espn_id=None row excluded
    assert "00-0000000" not in gsis_map
    assert "NullESP0" not in pfr_map

    # gsis_id=None row: no entry in gsis_map, but pfr entry present
    assert "SomePFR0" in pfr_map
    assert pfr_map["SomePFR0"] == "1111111"

    # pfr_id=None row: no entry in pfr_map, but gsis entry present
    assert "00-0099999" in gsis_map
    assert gsis_map["00-0099999"] == "2222222"

    # Normal rows
    assert gsis_map["00-0035676"] == "4047646"
    assert pfr_map["BrowAJ00"] == "4047646"
    assert gsis_map["00-0033280"] == "3054211"
    assert pfr_map["HillTy00"] == "3054211"
