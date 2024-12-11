# LOAD PLAYER GAME LOG DATA --------------------------------------------------------------
def load_data(player_row):
    # Validate `player_row`
    if not isinstance(player_row, pd.Series):
        raise ValueError("Invalid player_row. Expected a pandas Series.")
    
    if 'playerId' not in player_row or pd.isna(player_row['playerId']):
        raise ValueError("Invalid player_row: Missing or invalid 'playerId'.")
    
    if 'exp' not in player_row or not isinstance(player_row['exp'], (int, float, np.int64, np.float64)) or pd.isna(player_row['exp']):
        exp = 1
    else:
        exp = int(player_row['exp']) + 1
    
    # Calculate adjusted experience and years
    lookback = 3
    adjusted_exp = min(exp, lookback)
    current_year = datetime.now().year
    years = [current_year - i for i in range(adjusted_exp)]

    # Create player experience DataFrame
    player_experience_df = pd.DataFrame({
        'playerId': [player_row['playerId']] * adjusted_exp,
        'fullName': [player_row['fullName']] * adjusted_exp,
        'Year': years
    })

    year, week = get_current_nfl_week()
    # Define file path to check for existing CSV
    file_path = f"data/playerData/{year}_week{week}/{player_row['firstName']}_{player_row['lastName']}_{year}_week{week}_data.csv"

    # Ensure the directory exists before saving the CSV
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # Check if the CSV exists, if so, load it and return
    if os.path.exists(file_path):
        st.write(f"Loading existing data for playerId {player_row['fullName']}...")
        game_log = pd.read_csv(file_path)
        return game_log

    # Fetch game log data
    log_url = "https://nfl-api1.p.rapidapi.com/player-game-log"
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "nfl-api1.p.rapidapi.com"
    }
    rows, labels = [], []
    

    for _, row in player_experience_df.iterrows():
        querystring = {"playerId": row["playerId"], "season": str(row["Year"])}
        try:
            response = requests.get(log_url, headers=headers, params=querystring)
            response.raise_for_status()
            json_data = response.json()

            if "player_game_log" not in json_data or not json_data:
                print(f"No game log found for playerId {row['playerId']} in season {row['Year']}.")
                continue

            player_game_log = json_data["player_game_log"]
            if not player_game_log:  # Further check for empty 'player_game_log'
                print(f"player_game_log is empty for playerId {row['playerId']} in season {row['Year']}. Skipping...")
                continue  # Skip if player_game_log is empty

            labels = player_game_log.get("names", [])

            for season in player_game_log.get("seasonTypes", []):
                season_name = season.get("displayName", "Unknown")
                for category in season.get("categories", []):
                    for event in category.get("events", []):
                        event_stats = event.get("stats", [])
                        event_id = event.get("eventId", "Unknown")
                        game_data = player_game_log.get("events", {}).get(event_id, {})

                        row_data = event_stats + [
                            game_data.get("week", "Unknown"),
                            game_data.get("gameDate", "Unknown"),
                            game_data.get("homeTeamScore", "Unknown"),
                            game_data.get("awayTeamScore", "Unknown"),
                            game_data.get("gameResult", "Unknown"),
                            event_id,
                            season_name
                        ]
                        row_data += row.drop(["playerId", "Year"]).tolist()
                        rows.append(row_data)

        except requests.exceptions.RequestException as e:
            print(f"Error fetching data for playerId {row['playerId']} in season {row['Year']}: {e}")
            continue
    if not rows:
        print("No data collected.")
        return pd.DataFrame()

    # Process game log data
    column_headers = labels + [
        "week", "date", "homeScore", "awayScore", "result",
        "eventId", "seasonName"
    ] + [col for col in player_experience_df.columns if col not in ["playerId", "Year"]]

    game_log = pd.DataFrame(rows, columns=column_headers)
    game_log["seasonYr"] = game_log["seasonName"].str.slice(0, 4).str.strip()
    game_log["seasonType"] = game_log["seasonName"].str.slice(4).str.strip()
    game_log = game_log[game_log["seasonType"] == "Regular Season"]

    numeric_columns = ["receivingTouchdowns", "receptions", "receivingYards", "receivingTargets", "fumbles"]
    for col in numeric_columns:
        game_log[col] = pd.to_numeric(game_log[col], errors="coerce").fillna(0).astype(int)

    game_log.sort_values(by=["seasonYr", "seasonType", "week"], inplace=True)

    # Add lagged features
    game_log = game_log.sort_values(by=["fullName", "seasonYr", "week"]).reset_index(drop=True)
    game_log["weeks_played"] = game_log.groupby(["seasonYr", "fullName"]).cumcount() + 1

    def calculate_lagged_features(group):
        # Cumulative Features
        group["cumulative_receiving_yards"] = group["receivingYards"].cumsum().shift(1)
        group["cumulative_receptions"] = group["receptions"].cumsum().shift(1)
        group["cumulative_receiving_touchdowns"] = group["receivingTouchdowns"].cumsum().shift(1)
        group["cumulative_targets"] = group["receivingTargets"].cumsum().shift(1)

        # Lagged Per-Game Features
        group["cumulative_yards_per_game"] = group["cumulative_receiving_yards"] / (group["weeks_played"] - 1)
        group["cumulative_receptions_per_game"] = group["cumulative_receptions"] / (group["weeks_played"] - 1)
        group["cumulative_tds_per_game"] = group["cumulative_receiving_touchdowns"] / (group["weeks_played"] - 1)
        group["cumulative_targets_per_game"] = group["cumulative_targets"] / (group["weeks_played"] - 1)

        # Rolling Features (3-game averages)
        group["avg_receiving_yards_last_3"] = group["receivingYards"].rolling(window=3, min_periods=1).mean().shift(1)
        group["avg_receptions_last_3"] = group["receptions"].rolling(window=3, min_periods=1).mean().shift(1)
        group["avg_tds_last_3"] = group["receivingTouchdowns"].rolling(window=3, min_periods=1).mean().shift(1)
        group["avg_targets_last_3"] = group["receivingTargets"].rolling(window=3, min_periods=1).mean().shift(1)

        # Yards per Reception and Touchdown Rate per Target
        group["yards_per_reception"] = (group["receivingYards"] / group["receptions"]).shift(1).replace([float("inf"), -float("inf")], 0)
        group["td_rate_per_target"] = (group["cumulative_receiving_touchdowns"] / group["cumulative_targets"]).shift(1).replace([float("inf"), -float("inf")], 0)

        return group

    # Handle division by zero and first-week cases
    game_log = game_log.groupby(["seasonYr", "fullName"]).apply(calculate_lagged_features)
    game_log.fillna(0, inplace=True)
    game_log["is_first_week"] = (game_log["weeks_played"] == 1).astype(int)

    game_log['td'] = (game_log['receivingTouchdowns'] > 0).astype(int)

    # Save the data to CSV
    game_log.to_csv(file_path, index=False)
    st.write(f"New data cached for {player_row['fullName']}")

    return game_log
