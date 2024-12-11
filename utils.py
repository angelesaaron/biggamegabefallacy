import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import requests
from datetime import datetime, timedelta
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.ensemble._forest import ForestClassifier
import altair as alt
import joblib
import pickle
import os
import pytz

# API KEY
rapidapi_key = st.secrets["api"]["rapidapi_key"]
odds_api_key = st.secrets["api"]['odds_api_key']


# LOAD TEAMS -----------------------------------------------------------------------------
def load_teams():
    dfTeams = pd.read_csv('data/teamList.csv')
    dfTeams = dfTeams[['id', 'abbrev', 'location', 'name']]
    dfTeams['FullName'] = dfTeams['location'] + ' ' + dfTeams['name']
    return dfTeams

# LOAD ROSTER ----------------------------------------------------------------------------
def load_roster():
    # Get Year + Week
    year, week = get_current_nfl_week()
    
    # File Path
    file_path = f'data/rosters/{year}_week{week}_roster.csv'

    # Check if File Path exists
    if os.path.exists(file_path):
        roster = pd.read_csv(file_path)
        return roster
    
    # Load Teams
    teams = load_teams()

    # Initialize an empty list to collect data
    all_rosters = []
    
    # Roster URL for API
    rosterurl = "https://nfl-api1.p.rapidapi.com/nflteamplayers"

    # API Headers
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "nfl-api1.p.rapidapi.com"
    }

    # Iterate over each team's ID
    for team in teams['id']:
        querystring = {"teamid": team}

        try:
            # API GET Request
            response = requests.get(rosterurl, headers=headers, params=querystring)
            response.raise_for_status()  # Raise an exception for HTTP errors
            roster_json = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch roster data for team ID {team}: {e}")
            continue
        except ValueError as e:
            print(f"Invalid JSON response for team ID {team}: {e}")
            continue

        # Extract athletes and team data
        athletes = roster_json.get("team", {}).get("athletes", [])
        team_id = roster_json.get("team", {}).get("id", None)

        if not athletes:
            print(f"No athlete data found for team ID {team}.")
            continue
        if team_id is None:
            print(f"Invalid or missing team ID in the response for team ID {team}.")
            continue

        # Process athlete data for this team
        athlete_data = []
        for athlete in athletes:
            athlete_data.append(
                {
                    "team_id": team_id,
                    "playerId": athlete.get("id"),
                    "firstName": athlete.get("firstName"),
                    "lastName": athlete.get("lastName"),
                    "fullName": athlete.get("fullName"),
                    "displayName": athlete.get("displayName"),
                    "weight": athlete.get("weight"),
                    "height": athlete.get("height"),
                    "age": athlete.get("age"),
                    "position": athlete.get("position", {}).get("abbreviation"),
                    "activestatus": athlete.get("status", {}).get("id"),
                    "headshot": athlete.get("headshot", {}).get("href"),
                    "exp": athlete.get("experience", {}).get("years"),
                }
            )

        # Convert to DataFrame for this team and append to the list
        team_roster = pd.DataFrame(athlete_data)
        all_rosters.append(team_roster)

    # Concatenate all team rosters into a single DataFrame
    full_roster = pd.concat(all_rosters, ignore_index=True)

    # Ensure 'activestatus' is converted to int64
    if 'activestatus' in full_roster.columns:
        try:
            full_roster['activestatus'] = pd.to_numeric(full_roster['activestatus'], errors='coerce').fillna(0).astype('int64')
        except Exception as e:
            raise RuntimeError(f"Error converting 'activestatus' to int64: {e}")

    # Filter for relevant positions (WR and TE)
    if full_roster.empty:
        raise RuntimeError("No valid roster data available after processing.")
    
    full_roster_WR_TE = full_roster[full_roster['position'].isin(['WR', 'TE'])]
    if full_roster_WR_TE.empty:
        raise RuntimeError("No WR or TE players found in the rosters.")
    
    # Save the combined roster to a CSV file
    full_roster_WR_TE.to_csv(file_path, index=False)

    return full_roster_WR_TE

# GET ROSTER -----------------------------------------------------------------------------
def get_team_roster(teamid):
    if not teamid:
        raise ValueError("Invalid team ID provided.")

    # Load the full roster
    full_roster = load_roster()

    # Ensure the `team_id` column exists
    if 'team_id' not in full_roster.columns:
        raise ValueError("The roster data does not contain a 'team_id' column.")

    # Filter the roster for the specified team
    team_roster = full_roster[full_roster['team_id'] == teamid]

    # Validate the filtered roster
    if team_roster.empty:
        raise ValueError(f"No players found for team ID '{teamid}'.")

    return team_roster

# VALIDATE PLAYER STATUS -----------------------------------------------------------------
def validate_active_player(dfRoster, selected_player):
    selected_player_row = dfRoster[dfRoster['fullName'] == selected_player]

    if selected_player_row.empty:
        st.stop()
    if not selected_player_row['activestatus'].values[0] == 1:
        st.warning(f"{selected_player} is not active. Please select a different player.")
        st.stop()

    return selected_player_row.iloc[0]  # Return the row for the active player

# LOAD DATA
def load_data_for_roster(roster_df):
    if not isinstance(roster_df, pd.DataFrame):
        raise ValueError("Invalid roster_df. Expected a pandas DataFrame.")

    year, week = get_current_nfl_week()

    # Define the final results file path
    file_path = f"data/playerData/{year}_week{week}/roster_game_logs.csv"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # Check if the combined CSV already exists
    if os.path.exists(file_path):
        st.write(f"Loading existing data for NFL {year} - Week {week}...")
        return pd.read_csv(file_path)

    all_game_logs = []

    log_url = "https://nfl-api1.p.rapidapi.com/player-game-log"
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "nfl-api1.p.rapidapi.com"
    }

    for _, player_row in roster_df.iterrows():
        # Validate player_row
        if 'playerId' not in player_row or pd.isna(player_row['playerId']):
            continue

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

        rows, labels = [], []

        for _, row in player_experience_df.iterrows():
            querystring = {"playerId": row["playerId"], "season": str(row["Year"])}
            try:
                response = requests.get(log_url, headers=headers, params=querystring)
                response.raise_for_status()
                json_data = response.json()

                if "player_game_log" not in json_data or not json_data:
                    continue

                player_game_log = json_data["player_game_log"]
                if not player_game_log:
                    continue

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

        if rows:
            # Process game log data for the player
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
                group["cumulative_receiving_yards"] = group["receivingYards"].cumsum().shift(1)
                group["cumulative_receptions"] = group["receptions"].cumsum().shift(1)
                group["cumulative_receiving_touchdowns"] = group["receivingTouchdowns"].cumsum().shift(1)
                group["cumulative_targets"] = group["receivingTargets"].cumsum().shift(1)
                group["cumulative_yards_per_game"] = group["cumulative_receiving_yards"] / (group["weeks_played"] - 1)
                group["cumulative_receptions_per_game"] = group["cumulative_receptions"] / (group["weeks_played"] - 1)
                group["cumulative_tds_per_game"] = group["cumulative_receiving_touchdowns"] / (group["weeks_played"] - 1)
                group["cumulative_targets_per_game"] = group["cumulative_targets"] / (group["weeks_played"] - 1)
                group["avg_receiving_yards_last_3"] = group["receivingYards"].rolling(window=3, min_periods=1).mean().shift(1)
                group["avg_receptions_last_3"] = group["receptions"].rolling(window=3, min_periods=1).mean().shift(1)
                group["avg_tds_last_3"] = group["receivingTouchdowns"].rolling(window=3, min_periods=1).mean().shift(1)
                group["avg_targets_last_3"] = group["receivingTargets"].rolling(window=3, min_periods=1).mean().shift(1)
                group["yards_per_reception"] = (group["receivingYards"] / group["receptions"]).shift(1).replace([float("inf"), -float("inf")], 0)
                group["td_rate_per_target"] = (group["cumulative_receiving_touchdowns"] / group["cumulative_targets"]).shift(1).replace([float("inf"), -float("inf")], 0)
                return group

            game_log = game_log.groupby(["seasonYr", "fullName"]).apply(calculate_lagged_features)
            game_log.fillna(0, inplace=True)
            game_log["is_first_week"] = (game_log["weeks_played"] == 1).astype(int)
            game_log['td'] = (game_log['receivingTouchdowns'] > 0).astype(int)

            all_game_logs.append(game_log)

    # Combine all player game logs and save the final results
    final_game_logs = pd.concat(all_game_logs, ignore_index=True) if all_game_logs else pd.DataFrame()
    final_game_logs.to_csv(file_path, index=False)
    st.write(f"New data cached for week {week}, year {year}")

    return final_game_logs

# EXTRACT PREVIOUS GAME ------------------------------------------------------------------
def extract_previous_game_stats(gameData):
    # Validate input
    if not isinstance(gameData, pd.DataFrame) or gameData.empty:
        raise ValueError("Invalid or empty gameData. Cannot extract previous game statistics.")
    
    required_columns = [
        "receivingYards", "receptions", "td", "receivingTouchdowns", "receivingTargets",
        "cumulative_yards_per_game", "cumulative_receptions_per_game", "cumulative_targets_per_game",
        "avg_receiving_yards_last_3", "avg_receptions_last_3", "avg_targets_last_3",
        "yards_per_reception", "td_rate_per_target", "is_first_week"
    ]
    missing_columns = [col for col in required_columns if col not in gameData.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns in gameData: {', '.join(missing_columns)}.")
    
    # Ensure there's at least one row of data
    if gameData.shape[0] < 1:
        raise ValueError("Insufficient data in gameData to extract previous game statistics.")

    # Extract previous game stats (last row of DataFrame)
    df_previous_game = gameData.iloc[-1]
    
    # Validate individual fields
    def validate_field(field, expected_type, default_value=None):
        """Helper function to validate individual fields."""
        value = df_previous_game.get(field, default_value)
        if not isinstance(value, expected_type) and not pd.isna(value):
            raise ValueError(f"Invalid type for {field}. Expected {expected_type}, got {type(value)}.")
        return value if pd.notna(value) else default_value

    stats = {
        # Previous game stats
        "lag_yds": validate_field("receivingYards", (int, float, np.int64), 0),
        "lag_REC": validate_field("receptions", (int, float, np.int64), 0),
        "lag_td": validate_field("td", (int, float, np.int64), 0),
        "lag_REC_TD": validate_field("receivingTouchdowns", (int, float, np.int64), 0),
        "lag_TGT": validate_field("receivingTargets",  (int, float, np.int64), 0),
        
        # Cumulative and rolling averages
        "cumulative_yards_per_game": validate_field("cumulative_yards_per_game",  (int, float, np.int64), 0),
        "cumulative_receptions_per_game": validate_field("cumulative_receptions_per_game",  (int, float, np.int64), 0),
        "cumulative_targets_per_game": validate_field("cumulative_targets_per_game",  (int, float, np.int64), 0),
        "avg_receiving_yards_last_3": validate_field("avg_receiving_yards_last_3",  (int, float, np.int64), 0),
        "avg_receptions_last_3": validate_field("avg_receptions_last_3",  (int, float, np.int64), 0),
        "avg_targets_last_3": validate_field("avg_targets_last_3",  (int, float, np.int64), 0),
        "yards_per_reception": validate_field("yards_per_reception",  (int, float, np.int64), 0),
        "td_rate_per_target": validate_field("td_rate_per_target",  (int, float, np.int64), 0),
        "is_first_week": validate_field("is_first_week", (int, np.int64),  1),
    }

    # Determine next week and year (default to Week 1 if unavailable)
    try:
        thisYear, nextWeek = get_current_nfl_week()
    except Exception as e:
        print(f"Error determining next week: {e}. Defaulting to Week 1.")
        thisYear, nextWeek = datetime.now().year, 1

    stats["thisYear"] = thisYear
    stats["nextWeek"] = int(nextWeek)

    return stats

# RUN MODEL ------------------------------------------------------------------------------
def run_td_model(stats_dict):
    # Load the model
    model = joblib.load('models/wr-model.pkl')

    # Define the required fields
    required_keys = [
        'nextWeek', 'lag_yds', 'cumulative_yards_per_game', 
        'cumulative_receptions_per_game', 'cumulative_targets_per_game', 
        'avg_receiving_yards_last_3', 'avg_receptions_last_3', 
        'avg_targets_last_3', 'yards_per_reception', 
        'td_rate_per_target', 'is_first_week'
    ]
    
    # Validate that all required keys are in the dictionary
    missing_keys = [key for key in required_keys if key not in stats_dict]
    if missing_keys:
        raise ValueError(f"Missing required keys in stats dictionary: {missing_keys}")

    # Prepare the features as an array for prediction
    parameters = np.array([[
        float(stats_dict['nextWeek']),
        float(stats_dict['lag_yds']),
        float(stats_dict['cumulative_yards_per_game']),
        float(stats_dict['cumulative_receptions_per_game']),
        float(stats_dict['cumulative_targets_per_game']),
        float(stats_dict['avg_receiving_yards_last_3']),
        float(stats_dict['avg_receptions_last_3']),
        float(stats_dict['avg_targets_last_3']),
        float(stats_dict['yards_per_reception']),
        float(stats_dict['td_rate_per_target']),
        int(stats_dict['is_first_week'])
    ]])

    # Perform prediction
    likelihood = model.predict_proba(parameters)[:, 1]
    return likelihood[0]

# GET NFL Season Start -------------------------------------------------------------------
def get_current_nfl_week():
    # 1. Instantiate Today
    eastern = pytz.timezone('US/Eastern')
    # Get the current date and time in US/Eastern
    today = datetime.now(eastern)
    #today = datetime.today()
    # 2. Define NFL season start dates, with each season starting on the first Thursday after Labor Day
    nfl_start_dates = {
        2024: eastern.localize(datetime(2024, 9, 5)),
        2025: eastern.localize(datetime(2025, 9, 5)),
    }
    
    # 3. Pull NFL Start date for Current Year
    current_year = today.year
    nfl_start = nfl_start_dates.get(current_year, None)
    
    # 4. If today < NFL season start, return Week 1
    if nfl_start and today < nfl_start:
        return current_year, 1

    # 5. Calculate first tuesday - as want to define weeks tuesday - monday, tuesday to monday ....
    first_tuesday = nfl_start + timedelta(days=(8 - nfl_start.weekday()) % 7)
    
    # 6. Calculate the number of days since the first Tuesday
    days_since_first_tuesday = (today - first_tuesday).days
    
    # 7. Calculate the current NFL week if within the season (Weeks 1–18)
    if 0 <= days_since_first_tuesday < 18 * 7:
        week = days_since_first_tuesday // 7 + 2
        return current_year, week
    
    # 8. Catch all -- if today is after Week 18, return Week 1 of the next season
    return current_year + 1, 1

# CONVERT TO AMERICAN ODDS ---------------------------------------------------------------
def decimal_to_american_odds(probability):

    if probability is None:
        probability = 0
    probability = round(probability * 100)
    if probability < 0 or probability > 100:
        raise ValueError("Probability must be between 0 and 100.")
    
    if probability == 0:
        return float('inf')  # Infinite odds for 0% probability (no chance of winning)
    elif probability == 100:
        return -1  # This means a guaranteed win, represented as negative infinity odds

    if probability < 50:  # Positive odds
        odds = (100 / (probability / 100)) - 100
        direction = '+'
        favor = 1
    else:  # Negative odds
        odds = (probability / (1 - (probability / 100))) * -1
        direction = ''
        favor = -1
    
    return f"{direction}{round(odds)}", odds, favor
    
# GET SPORTSBOOK ODDS --------------------------------------------------------------------
def get_sportsbook_odds():
    
    # Define constants
    sport = 'americanfootball_nfl'
    region = 'us'
    url = f'https://api.the-odds-api.com/v4/sports/{sport}/odds'
    params = {
        'apiKey': odds_api_key,
        'regions': region,
        'markets': 'h2h',  # Specifies the market type
    }
    
    try:
        # Fetch event data
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raise an error for non-200 status codes
        events = response.json()

        # Extract event IDs
        event_ids = [event['id'] for event in events]

        if not event_ids:
            print("No events found.")
            return None

        all_odds_data = {}

        # Fetch odds for each event
        for event_id in event_ids:
            odds_url = f'https://api.the-odds-api.com/v4/sports/{sport}/events/{event_id}/odds'
            response = requests.get(odds_url, params={'apiKey': odds_api_key, 'regions': region, 'markets': 'player_anytime_td', 'oddsFormat': 'american'})
            response.raise_for_status()

            json_data = response.json()

            # Extract odds for players
            for bookmaker in json_data.get('bookmakers', []):
                book_title = bookmaker['title']
                for market in bookmaker.get('markets', []):
                    if market.get('key') == 'player_anytime_td':
                        for outcome in market.get('outcomes', []):
                            player_name = outcome['description']
                            odds = outcome['price']

                            if player_name not in all_odds_data:
                                all_odds_data[player_name] = {}

                            all_odds_data[player_name][book_title] = odds

        # Convert the collected data into a DataFrame
        odds_df = pd.DataFrame.from_dict(all_odds_data, orient='index').fillna('N/A')

        # Ensure numeric columns are properly formatted
        odds_df = odds_df.apply(pd.to_numeric, errors='coerce').round().fillna('N/A')

        # Convert numeric values back to integers
        for col in odds_df.columns:
            odds_df[col] = odds_df[col].apply(lambda x: int(x) if isinstance(x, float) and not pd.isna(x) else x)
        
        # Reset Index
        odds_df = odds_df.reset_index()
        # Rename the new column from 'index' to 'Player'
        odds_df.rename(columns={'index': 'Player'}, inplace=True)

        # Player Name Handling
        odds_df.loc[odds_df['Player'] == 'AJ Brown', 'Player'] = 'A.J. Brown'

        # Save the DataFrame to a CSV file
        year, week = get_current_nfl_week()
        return odds_df

    except requests.exceptions.RequestException as e:
        print(f"Error during API request: {e}")
        return None

# FETCH SPORTSBOOK ODDS ------------------------------------------------------------------
def load_or_fetch_odds(reload_odds=False):
    # Define the path to your CSV file
    year, week = get_current_nfl_week()
    csv_file = f'data/sportsbookOdds/odds_{year}_week{week}.csv'

    # If reload_odds is True, always fetch data, even if CSV exists
    if reload_odds:
        st.write("Reloading odds from source...")
        odds_df = get_sportsbook_odds()  # Call your function to fetch data
        if odds_df is not None:
            # Save the DataFrame to a CSV file
            odds_df.to_csv(csv_file, index=False)
            print("Data fetched and saved.")
        else:
            print("Error fetching data.")
            return None
    else:
        # Check if the CSV file exists
        if not os.path.exists(csv_file):
            # CSV doesn't exist, fetch and process the data
            #st.write("CSV file not found. Fetching data...")
            odds_df = get_sportsbook_odds()  # Call your function to fetch data
            if odds_df is not None:
                # Save the DataFrame to a CSV file
                odds_df.to_csv(csv_file, index=False)
                print("Data fetched and saved.")
            else:
                print("Error fetching data.")
                return None
        else:
            # CSV exists, load the data
            #st.write("CSV file found. Loading data...")
            odds_df = pd.read_csv(csv_file)

    return odds_df

# GET PLAYER -----------------------------------------------------------------------------
def create_player_odds_df(odds, player_name):
    # Initialize an empty DataFrame
    df_combined = pd.DataFrame()
    # Construct the file path for the sportsbook data
    sportsbookData = load_or_fetch_odds()
    # Create a DataFrame for the player and model odds
    data = {
        'Player': [player_name],
        'Model': [odds]
    }
    df_player_odds = pd.DataFrame(data)
    # Join sportsbook data on player and add all columns from sportsbook data
    df_combined = pd.merge(df_player_odds, sportsbookData, on='Player', how='left')

    # Return the combined DataFrame
    return df_combined

# CREATE HEATMAP -------------------------------------------------------------------------
def create_heatmap(playerOddsDF):
    # Melt the DataFrame for the HeatMap
    df_melted = playerOddsDF.melt(id_vars=['Player', 'Model'], var_name='Provider', value_name='Odds')

    # Calculate the difference between provider odds and model odds
    df_melted['Difference'] = df_melted['Odds'] - df_melted['Model']

    # Pivot the DataFrame for the heatmap
    heatmap_data = df_melted.pivot(index="Player", columns="Provider", values="Odds")
    difference_data = df_melted.pivot(index="Player", columns="Provider", values="Difference")
    
    # Annotate with positive values marked as '+'
    annot_data = heatmap_data.applymap(lambda x: f"+{round(x)}" if pd.notna(x) and x > 0 else (str(round(x)) if pd.notna(x) else ""))

    # Set the colormap to a diverging palette (green for negative, red for positive)
    cmap = sns.diverging_palette(10, 150, s=100, l=50, as_cmap=True)
    
    # Create the heatmap plot
    plt.figure(figsize=(9, 5))
    ax = sns.heatmap(
        difference_data,
        annot=annot_data,
        fmt="",
        cmap=cmap, 
        center=0, 
        cbar=False,
        linewidths=.5
    )

    # Update titles and labels
    plt.title('Odds Comparison Heatmap')
    ax.set_xlabel("")
    ax.set_ylabel("")

    # Show the plot in Streamlit
    st.pyplot(plt)
    plt.clf()  # Clear the current figure after displaying
     
# RUN MODEL FOR ALL PLAYERS --------------------------------------------------------------
def get_total_model_odds():
    
    # Get Year + Week
    year, week = get_current_nfl_week()
    # Get File if already exists
    file_path = f'data/modelOdds/{year}_NFL_Week{week}_BestOdds.csv'

    # Check if File Path exists
    if os.path.exists(file_path):
        odds_df = pd.read_csv(file_path)
        return odds_df
    # Get Roster
    fullRoster = load_roster()
    actives = fullRoster[fullRoster['activestatus'] == 1]
    # Load Game Log Data 
    gameLogData = load_data_for_roster(fullRoster)
    # Filter gameLogData to include only active players
    active_gameLogData = gameLogData[gameLogData['fullName'].isin(actives['fullName'])]

    results = []
    for player_name in active_gameLogData['fullName'].unique():
        try:
            # Filter player-specific game log data
            player_data = active_gameLogData[active_gameLogData['fullName'] == player_name]

            # Step 2: Ensure player data is available
            if player_data.empty:
                continue  # Skip if no game log data available

            # Step 3: Extract previous game statistics
            stats = extract_previous_game_stats(player_data)

            # Step 4: Run the touchdown model
            td_likelihood = run_td_model(stats)
            odds_str, odds, favor = decimal_to_american_odds(td_likelihood)

            # Step 5: Store the result
            results.append({
                "Player": player_name,
                "TD_Likelihood": td_likelihood,
                "Model_Odds": odds,
                "Favor": favor
            })

        except Exception as e:
            print(f"Error processing player {player_name}: {e}")
            continue  # Skip any player that causes an error
    # Convert results to a DataFrame
    odds_df = pd.DataFrame(results)
    odds_df.to_csv(file_path, index=False)

    return odds_df

# GET WEEKLY BEST ODDS --------------------------------------------------------------------
def get_all_odds():
    # Get Week + Year
    year, week = get_current_nfl_week()

    file_path = f"data/combinedOdds/{year}_week{week}_combined_odds.csv"
    # Check if File Path exists
    if os.path.exists(file_path):
        totalOdds = pd.read_csv(file_path)

        return totalOdds
    

    # Get Model Output
    modelOdds = get_total_model_odds()
    
    # Validate modelOdds
    if modelOdds is None or modelOdds.empty:
        print("Error: Model odds data is empty or could not be fetched.")
        return
    if 'Player' not in modelOdds.columns:
        print("Error: 'Player' column not found in modelOdds.")
        return
    

    # Get SportsBook Odds
    sportsbookOdds = load_or_fetch_odds()
    # Validate sportsbookOdds
    if sportsbookOdds is None or sportsbookOdds.empty:
        print("Error: Sportsbook odds data is empty or could not be fetched.")
        return
    if 'Player' not in sportsbookOdds.columns:
        print("Error: 'Player' column not found in sportsbookOdds.")
        return


    # JOIN
    totalOdds = pd.merge(modelOdds, sportsbookOdds, how='left', on='Player')
    totalOdds = totalOdds[['Player', 'TD_Likelihood', 'Model_Odds', 'Favor', 'DraftKings', 'FanDuel', 'BetOnline.ag', 'BetRivers', 'BetMGM', 'Bovada']]
    
    # Clean Data Set
    totalOdds = totalOdds.loc[totalOdds['TD_Likelihood'].notna() & (totalOdds['TD_Likelihood'] != '')]


    totalOdds.to_csv(file_path)

    return totalOdds

# MODEL BEST ODDS ------------------------------------------------------------------------
def best_odds_model():
    odds = get_all_odds()

    # get year + week
    year, week = get_current_nfl_week()

    file_path = f"data/historicalOdds/model/{year}_week{week}_valuepicks.csv"
    if os.path.exists(file_path):
        odds = pd.read_csv(file_path)
        odds['Odds'] = round(odds['Model_Odds'])
        odds['Odds'] = odds.apply(lambda row: f"+{round(row['Odds'])}" if row['Favor'] == 1 else round(row['Odds']), axis=1)
        odds = odds[['Player', 'Odds']].head(30)
        odds = odds.reset_index(drop=True)
        odds.index = odds.index+1
        return odds

    # Check if the necessary columns exist in the DataFrame
    required_columns = ['Player', 'TD_Likelihood', 'Model_Odds', 'Favor']
    for col in required_columns:
        if col not in odds.columns:
            raise ValueError(f"Missing required column: {col}")
    
    # Check if TD_Likelihood and Model_Odds are numeric
    if not pd.api.types.is_numeric_dtype(odds['TD_Likelihood']) or not pd.api.types.is_numeric_dtype(odds['Model_Odds']):
        raise ValueError("Columns 'TD_Likelihood' and 'Model_Odds' must be numeric.")

    # Drop rows with missing values in key columns
    odds = odds.dropna(subset=['TD_Likelihood', 'Model_Odds'])

    # Sort data by TD_Likelihood in descending order
    odds = odds.sort_values(by='TD_Likelihood', ascending=False)

    # to CSV
    odds.to_csv(file_path)

    # Round Odds
    odds['Odds'] = round(odds['Model_Odds'])

    # Add Prefix (Only if Favor is 1, otherwise keep as is)
    odds['Odds'] = odds.apply(lambda row: f"+{round(row['Odds'])}" if row['Favor'] == 1 else round(row['Odds']), axis=1)

    # Segment data fields
    odds = odds[['Player', 'Odds']].head(30)
    odds = odds.reset_index(drop=True)
    odds.index = odds.index+1

    return odds 

# PROVIDER BEST ODDS ---------------------------------------------------------------------
def best_odds_provider(provider):
    # Check if 'provider' column exists in the DataFrame
    combinedOdds = get_all_odds()

    # get year + week 
    year, week = get_current_nfl_week()

     # Check if File Path Already Exists
    file_path = f"data/historicalOdds/{provider}/{year}_week{week}_valuepicks.csv"

    if os.path.exists(file_path):
        odds = pd.read_csv(file_path)
        # DATA PROCESSING 

        # Formatting
        odds['Odds'] = odds.apply(lambda row: f"+{round(row['Model_Odds'])}" if row['Favor'] == 1 else round(row['Model_Odds']), axis=1)
        odds[provider] = odds[provider].apply(lambda x: f"+{int(x)}" if x > 0 else str(int(x)))

        # Subsetting
        odds = odds[['Player', 'Odds', provider]].head(30)
        odds = odds.reset_index(drop=True)
        odds.index = odds.index+1
        return odds

    # Validate provider column
    if provider not in combinedOdds.columns:
        raise ValueError(f"Provider column '{provider}' is missing in the data.")
    
    # Check if the necessary columns exist
    required_columns = ['Player', 'Model_Odds', 'Favor']
    for col in required_columns:
        if col not in combinedOdds.columns:
            raise ValueError(f"Missing required column: {col}")
    
    # Ensure 'Model_Odds' and provider column contain numeric values
    if not pd.api.types.is_numeric_dtype(combinedOdds['Model_Odds']) or not pd.api.types.is_numeric_dtype(combinedOdds[provider]):
        raise ValueError(f"Columns 'Model_Odds' and '{provider}' must be numeric.")
    
    # Subset the provider and necessary columns, drop rows with missing values
    odds = combinedOdds[['Player', 'Model_Odds', 'Favor', provider]].dropna()

    # Calculate the Difference between Model_Odds and provider odds
    odds['Difference'] = odds['Model_Odds'] - odds[provider]

    # Calculate the implied probability
    odds['Model_Probability'] = odds['Model_Odds'].apply(implied_probability)
    odds[f'{provider}_Probability'] = odds[provider].apply(implied_probability)
    odds['Weight'] = 1 - odds['Model_Probability']
    odds["WeightedValue"] = (odds[f'{provider}_Probability'] - odds["Model_Probability"]) * odds["Weight"]

    # Filter Out Anything Less Than 800
    odds = odds[odds['Model_Odds'] <= 800]
    # Filter Out Bad Value Plays
    odds = odds[odds['WeightedValue'] <= 0.0000]
    # Sort by the difference in ascending order
    odds = odds.sort_values(by='WeightedValue', ascending=True)

    # # Put to CSV
    odds.to_csv(file_path)

    # Round Model_Odds and add prefix if Favor == 1
    odds['Odds'] = odds.apply(lambda row: f"+{round(row['Model_Odds'])}" if row['Favor'] == 1 else round(row['Model_Odds']), axis=1)


    # Format provider odds with a "+" prefix if positive, else leave as is
    odds[provider] = odds[provider].apply(lambda x: f"+{int(x)}" if x > 0 else str(int(x)))

    # Select top 20 rows
    odds = odds[['Player', 'Odds', provider]].head(30)
    odds = odds.reset_index(drop=True)
    odds.index = odds.index+1

    return odds

# VALUE BALANCING - IMPLIED PROBABILITY --------------------------------------------------
def implied_probability(odds):
    if odds > 0:
        return 100/(odds+100)
    else:
        return - odds / (-odds + 100)

# GET PAST MODEL + PICK PERFORMANCE
def get_past_performance(provider, unit, is_model=True):
    # Get year and week
    year, week = get_current_nfl_week()
    last_week = max(week - 1, 1)

    # Define the file path for last week's data
    if is_model:
        file_path_lastweek = f"data/historicalOdds/model/{year}_week{last_week}_valuepicks.csv"
    else:
        file_path_lastweek = f"data/historicalOdds/{provider}/{year}_week{last_week}_valuepicks.csv"

    # Check if the file exists
    if not os.path.exists(file_path_lastweek):
        st.write(f"The historical stats for {provider} do not exist. Unable to retrieve past performance.")
        return None, None, pd.DataFrame()

    # Read the historical odds data
    lastWeekOdds = pd.read_csv(file_path_lastweek)
    lastWeekOdds['Touchdowns'] = None

    # Load the roster
    roster = load_roster()
    if roster.empty:
        raise ValueError("Roster is empty. Please check the data source.")
    # Load game log data for the roster
    gameLogData = load_data_for_roster(roster)
    if gameLogData.empty:
        raise ValueError("Game log data is empty. Please ensure the data source is valid and populated.")



      # Loop over each player and get touchdown data
    for idx, row in lastWeekOdds.iterrows():
        player_name = row['Player']

        # Filter the game log data for the specific player
        player_df = gameLogData[gameLogData['fullName'] == player_name]
        if player_df.empty:
            print(f"No game log data found for player: {player_name}. Skipping...")
            continue

        # Filter for the specific week and year
        filtered_row = player_df[(player_df['week'] == last_week) & (player_df['seasonYr'] == year)]
        if filtered_row.empty:
            print(f"No game log entry found for {player_name} for week {last_week}, season {year}. Skipping...")
            continue
        if not filtered_row.empty:
            lastWeekOdds.at[idx, 'Touchdowns'] = filtered_row.iloc[0]['receivingTouchdowns']

    # Set odds based on the source (Model or Provider)
    if is_model:
        lastWeekOdds = lastWeekOdds.sort_values('TD_Likelihood', ascending=False)
        lastWeekOdds['Sportsbook'] = lastWeekOdds.apply(lambda row: row['DraftKings'] if pd.notnull(row['DraftKings']) else (row['FanDuel'] if pd.notnull(row['FanDuel']) else None), axis=1)
        lastWeekOdds = lastWeekOdds[lastWeekOdds['Sportsbook'].notna()]
    else:
        lastWeekOdds = lastWeekOdds.sort_values('WeightedValue', ascending=True)
        lastWeekOdds['Sportsbook'] = lastWeekOdds[provider]
        
    
    lastWeekOdds = lastWeekOdds[lastWeekOdds['Sportsbook'].notna()]
    lastWeekOdds = lastWeekOdds.fillna(0)

    # Apply Winnings calculation
    lastWeekOdds['Win'] = lastWeekOdds.apply(lambda row: calculate_win(row, unit, provider), axis=1)

    # Format odds
    lastWeekOdds['Odds'] = lastWeekOdds.apply(lambda row: f"+{round(row['Model_Odds'])}" if row['Favor'] == 1 else round(row['Model_Odds']), axis=1)
    lastWeekOdds['Sportsbook'] = lastWeekOdds['Sportsbook'].apply(lambda x: f"+{int(x)}" if x > 0 else str(int(x)))

    # Select top 30 rows
    lastWeekOdds = lastWeekOdds[['Player', 'Odds', 'Sportsbook', 'Touchdowns', 'Win']].head(30)
    lastWeekOdds = lastWeekOdds.reset_index(drop=True)
    lastWeekOdds.index = lastWeekOdds.index + 1

    # Style the DataFrame for Streamlit
    styledOdds = lastWeekOdds.style.apply(highlight_rows, axis=1)

    # Calculate KPIs
    percent = (lastWeekOdds['Touchdowns'] > 0).sum() / len(lastWeekOdds)
    winnings = (lastWeekOdds['Win']).sum()

    return percent, winnings, styledOdds

# CALCULATE BET RESULT -------------------------------------------------------------------------
def calculate_win(row, unit, provider):
    if row['Touchdowns'] > 0:
        odds = row[provider]
        if odds > 0:
            return unit * (odds / 100)  # Positive odds calculation
        else:
            return unit / (abs(odds) / 100)  # Negative odds calculation
    else:
        return -(unit)

# HIGHLIGHT WINNING ROWS -------------------------------------------------------------------------
def highlight_rows(row):
    # Highlight rows where Touchdowns > 3
    if row["Touchdowns"] > 0:
        return ["background-color: green"] * len(row)
    else:
        return [""] * len(row)

# RELOAD SPORTSBOOK ODDS
def reload_sportsbook_odds():
    # Get Year + Week
    year, week = get_current_nfl_week()
    # Delete CSVs

    # 1. sportsbook odds
    sportsbook_path = f"data/sportsbookOdds/odds_{year}_week{week}.csv"
    if os.path.exists(sportsbook_path):
        os.remove(sportsbook_path)
        st.write(f"File {sportsbook_path} has been deleted.")
    
    # 2. combined odds
    combined_path = f"data/combinedOdds/odds_{year}_week{week}_combined_odds.csv"
    if os.path.exists(combined_path):
        os.remove(combined_path)
        st.write(f"File {combined_path} has been deleted.")
    
    # 3. retrigger load odds

    load_or_fetch_odds(reload_odds=True)
