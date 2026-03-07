  PBP (and Snap) ID Investigation — What We Found
                                                                                               
  You're right, and this is a real architectural improvement opportunity.                    

  When the model was trained, there was no known way to exactly map nflverse names to Tank01
  player IDs, so fuzzy name matching + the alias table was the only option. That assumption
  turns out to be wrong.

  The Bridge: import_players()

  nfl_data_py.import_players() (already installed, already used by seed_draft_rounds.py) is a
  player cross-reference table that contains multiple ID formats per player:

  display_name    gsis_id        pfr_id    espn_id
  A.J. Brown      00-0035676    BrowAJ00   4047646   ← Tank01 playerID
  Ja'Marr Chase   00-0036900    ChasJa00   4362628

  espn_id in nflverse = playerID in Tank01. We confirmed this during the draft round work. But
  it also unlocks exact matching for both nflverse data sources:

  PBP Data — exact match via GSIS ID

  PBP has receiver_player_id in GSIS format (00-0035676). That column is already fetched —
  _fetch_rz_pbp() filters pbp["receiver_player_id"].notna() — but then drops it and uses
  receiver_player_name ("A.Brown") for matching instead. The exact ID was always there.

  PBP receiver_player_id (00-0035676)
    → import_players()[gsis_id → espn_id]
    → Tank01 playerID (4047646)  ✅ exact

  Snap Data — exact match via PFR ID

  Snap counts have pfr_player_id in PFR format (BrowAJ00). import_players() has pfr_id in the
  same format.

  Snap pfr_player_id (BrowAJ00)
    → import_players()[pfr_id → espn_id]
    → Tank01 playerID (4047646)  ✅ exact

  Both verified on real data. A.J. Brown bridge confirmed end-to-end on both paths.

  What This Means for the Current Design

  ┌───────────────────┬────────────────────────────────────┬────────────────────────────────┐
  │                   │              Current               │         With ID Bridge         │
  ├───────────────────┼────────────────────────────────────┼────────────────────────────────┤
  │ PBP matching      │ "A.Brown" fuzzy → alias table      │ receiver_player_id → exact     │
  │                   │ patches                            │                                │
  ├───────────────────┼────────────────────────────────────┼────────────────────────────────┤
  │ Snap matching     │ "A.J. Brown" fuzzy → alias table   │ pfr_player_id → exact          │
  │                   │ patches                            │                                │
  ├───────────────────┼────────────────────────────────────┼────────────────────────────────┤
  │ Alias table       │ Required to fix known failures     │ Fallback only for missing      │
  │                   │                                    │ players                        │
  ├───────────────────┼────────────────────────────────────┼────────────────────────────────┤
  │ DataQualityEvents │ ~10 unresolved per week            │ Near zero                      │
  └───────────────────┴────────────────────────────────────┴────────────────────────────────┘

  One Caveat — Historical Players

  import_players() returns the current/recent player roster. Travis Kelce (retired 2025) wasn't
   found in it. For the 2022–2024 historical backfill already in the DB, the names were already
   fuzzy-matched and snaps/RZ data is populated — no re-work needed. Going forward (2026
  season), all active players will be in import_players().

  Bottom Line

  The alias table, the _to_short() "F.Last" derivation, the _build_snap_resolver /
  _build_pbp_resolver logic — all of that complexity exists because we didn't know about the ID
   bridge. The entire name matching layer in nflverse_adapter.py can be replaced with a
  two-line dictionary lookup. This is a clean, high-confidence fix worth doing before 2026
  season ingest starts. Want to scope it out as a task?