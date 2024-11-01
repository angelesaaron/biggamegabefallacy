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

# API KEY
rapidapi_key = st.secrets["api"]["rapidapi_key"]

# LOAD TEAMS ----------------------------------------------------------------------------
def load_teams():
    dfTeams = pd.read_csv('data/teamList.csv')
    dfTeams['FullName'] = dfTeams['location'] + ' ' + dfTeams['name']
    return dfTeams

# LOAD ROSTER ---------------------------------------------------------------------------
def load_roster(teamid):
    
    # Roster URL for API
    rosterurl = "https://nfl-api1.p.rapidapi.com/nflteamplayers"

    querystring = {"teamid":teamid}
    
    # API HEADERS
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "nfl-api1.p.rapidapi.com"
    }
    # GET Request
    rosterResponse = requests.get(rosterurl, headers=headers, params=querystring)
    json_data = rosterResponse.json()

    # Extract team information
    team_info = json_data["team"]
    team_id = team_info["id"]
    team_location = team_info["location"]
    team_name = team_info["name"]
    
    rows = []

    # Extract player information
    for athlete in json_data['team']["athletes"]:
        athlete_id = athlete["id"]
        athlete_first_name = athlete["firstName"]
        athlete_last_name = athlete["lastName"]
        athlete_height = athlete["height"]
        athlete_weight = athlete["weight"]
        athlete_age = athlete.get('age', {})
        
        draft_info = athlete.get("draft", {})
        draft_rd = draft_info.get('round', None) 
        
        position_abbreviation = athlete["position"]["abbreviation"]
        exp = athlete["experience"]["years"]
        activestatus = athlete.get("status", {}).get('id', None)
        
        headshot = athlete.get("headshot", {}).get('href', None)

        row = [
            team_id,
            team_location,
            team_name,
            athlete_id,
            athlete_first_name,
            athlete_last_name,
            athlete_height,
            athlete_weight,
            athlete_age,
            draft_rd,
            position_abbreviation,
            exp,
            activestatus,
            headshot
        ]
        rows.append(row)

    column_headers = [
        "teamId",
        "location",
        "name",
        "playerId",
        "firstName",
        "lastName",
        "height",
        "weight",
        "athleteAge",
        "draftRd",
        "position",
        "exp",
        "activestatus",
        "headshot"
    ]

    roster = pd.DataFrame(rows, columns=column_headers)
    rosterWR = roster[roster['position'] == 'WR']
    rosterWR = rosterWR[rosterWR['activestatus'] == '1']
    rosterWR = rosterWR.drop('activestatus', axis=1)
    rosterWR['fullName'] = rosterWR['firstName'] + ' ' + rosterWR['lastName']
    rosterWR.loc[rosterWR['exp'] == 0, 'exp'] = 1

    return rosterWR

# LOAD GAME LOG -------------------------------------------------------------------------
@st.cache_data
def scrape_game_log(playerExperience):
    
    logurl = "https://nfl-api1.p.rapidapi.com/player-game-log"
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "nfl-api1.p.rapidapi.com"
    }

    # Initialize list to hold rows of data
    rows = []
    labels = []

    # Iterate through playerExperience DataFrame
    for index, row in playerExperience.iterrows():
        querystring = {"playerId": row['playerId'], "season": str(row['Year'])}
        logresponse = requests.get(logurl, headers=headers, params=querystring)

        # Check for successful response
        if logresponse.status_code != 200:
            print(f"Error fetching data for playerId {row['playerId']} in season {row['Year']}")
            continue

        json_data = logresponse.json()

        # Check if 'player_game_log' exists in the response
        if "player_game_log" not in json_data:
            print(f"'player_game_log' key missing for playerId {row['playerId']} in season {row['Year']}")
            continue
        
        player_game_log = json_data.get("player_game_log", {})
        labels = player_game_log.get("names", [])

        # Iterate through the seasonTypes and their events
        for season in player_game_log.get("seasonTypes", []):
            season_name = season.get("displayName", "Unknown")
            for category in season.get("categories", []):
                for event in category.get("events", []):
                    event_stats = event.get("stats", [])
                    event_id = event.get("eventId", "Unknown")

                    # Extract game data
                    game_data = player_game_log.get("events", {}).get(event_id, {})
                    week = game_data.get("week", "Unknown")
                    game_date = game_data.get("gameDate", "Unknown")
                    home_score = game_data.get("homeTeamScore", "Unknown")
                    away_score = game_data.get("awayTeamScore", "Unknown")
                    game_result = game_data.get("gameResult", "Unknown")

                    # Prepare a row with stats and additional metadata
                    row_data = event_stats + [
                        week,
                        game_date,
                        home_score,
                        away_score,
                        game_result,
                        event_id,
                        season_name
                    ]

                    # Append other columns from the input row (excluding playerId and Year)
                    row_data += row.drop(['playerId', 'Year']).tolist()  # Include other columns

                    rows.append(row_data)

    # Define column headers, including all columns from the input DataFrame
    column_headers = labels + [
        "week", "date", "homeScore", 
        "awayScore", "result", "eventId", "seasonName"
    ] + [col for col in playerExperience.columns if col not in ['playerId', 'Year']]  # Keep all other columns

    print(f"Column headers: {column_headers}")
    # Create the DataFrame
    if rows:  # Check if rows are populated
        gameLog = pd.DataFrame(rows, columns=column_headers)
        gameLog['seasonYr'] = gameLog['seasonName'].str.slice(0, 4)
        gameLog['seasonType'] = gameLog['seasonName'].str.slice(4)
        gameLog['seasonYr'] = gameLog['seasonYr'].str.strip()
        gameLog['seasonType'] = gameLog['seasonType'].str.strip()
        gameLog['receivingTouchdowns'] = pd.to_numeric(gameLog['receivingTouchdowns'], errors='coerce').fillna(0).astype(int)
        gameLog['receptions'] = pd.to_numeric(gameLog['receptions'], errors='coerce').fillna(0).astype(int)
        gameLog['receivingYards'] = pd.to_numeric(gameLog['receivingYards'], errors='coerce').fillna(0).astype(int)
        gameLog['receivingTargets'] = pd.to_numeric(gameLog['receivingTargets'], errors ='coerce').fillna(0). astype(int)
        gameLog['fumbles'] = pd.to_numeric(gameLog['fumbles'], errors ='coerce').fillna(0). astype(int)
        gameLog = gameLog[gameLog['seasonType'] == 'Regular Season']
        gameLogFin = gameLog.sort_values(by=['seasonYr', 'seasonType', 'week'], ascending=[True, True, True])
        
        return gameLogFin
    else:
        print("No data available")
        return pd.DataFrame()  # Return empty DataFrame if no data was collected

# GENERATE FEATURES ---------------------------------------------------------------------
def add_new_features_lag(data):
    # Sort data to ensure calculations are in the correct order
    data = data.sort_values(by=['fullName', 'seasonYr', 'week']).reset_index(drop=True)
    # Calculate weeks played for each season and player
    data['weeks_played'] = data.groupby(['seasonYr', 'fullName']).cumcount() + 1

    # Lag all cumulative and rolling calculations by shifting by 1 week
    # 1. Total Receiving Yards per Game (Lagged)
    data['cumulative_receiving_yards'] = data.groupby(['seasonYr', 'fullName'])['receivingYards'].cumsum().shift(1)
    data['cumulative_yards_per_game'] = data['cumulative_receiving_yards'] / (data['weeks_played'] - 1)
    # 2. Total Receptions per Game (Lagged)
    data['cumulative_receptions'] = data.groupby(['seasonYr', 'fullName'])['receptions'].cumsum().shift(1)
    data['cumulative_receptions_per_game'] = data['cumulative_receptions'] / (data['weeks_played'] - 1)
    # 3. Total Touchdowns per Game (Lagged)
    data['cumulative_receiving_touchdowns'] = data.groupby(['seasonYr', 'fullName'])['receivingTouchdowns'].cumsum().shift(1)
    data['cumulative_tds_per_game'] = data['cumulative_receiving_touchdowns'] / (data['weeks_played'] - 1)
    # 4. Cumulative Target Share per Game (Lagged)
    data['cumulative_targets'] = data.groupby(['seasonYr', 'fullName'])['receivingTargets'].cumsum().shift(1)
    data['cumulative_targets_per_game'] = data['cumulative_targets'] / (data['weeks_played'] - 1)
    # 5. 3-Game Average Receiving Yards (Lagged)
    data['avg_receiving_yards_last_3'] = data.groupby(['seasonYr', 'fullName'])['receivingYards']\
        .rolling(window=3, min_periods=1).mean().shift(1).reset_index(level=[0, 1], drop=True)
    # 6. 3-Game Average Receptions (Lagged)
    data['avg_receptions_last_3'] = data.groupby(['seasonYr', 'fullName'])['receptions']\
        .rolling(window=3, min_periods=1).mean().shift(1).reset_index(level=[0, 1], drop=True)
    # 7. 3-Game Average Touchdowns (Lagged)
    data['avg_tds_last_3'] = data.groupby(['seasonYr', 'fullName'])['receivingTouchdowns']\
        .rolling(window=3, min_periods=1).mean().shift(1).reset_index(level=[0, 1], drop=True)
    # 8. 3-Game Average Targets (Lagged)
    data['avg_targets_last_3'] = data.groupby(['seasonYr', 'fullName'])['receivingTargets']\
        .rolling(window=3, min_periods=1).mean().shift(1).reset_index(level=[0, 1], drop=True)
    # 9. Yards per Reception (Lagged for each game)
    data['yards_per_reception'] = (data['receivingYards'] / data['receptions']).shift(1)
    data['yards_per_reception'].replace([float('inf'), -float('inf')], 0, inplace=True)  # Handle division by zero
    # 10. Touchdown Rate per Target (Lagged cumulative touchdowns per cumulative targets)
    data['td_rate_per_target'] = (data['cumulative_receiving_touchdowns'] / data['cumulative_targets']).shift(1)
    data['td_rate_per_target'].replace([float('inf'), -float('inf')], 0, inplace=True)  # Handle division by zero
    # Fill in NaNs for rows where calculations are not available (e.g., first game of season)
    data.fillna(0, inplace=True)
    data['is_first_week'] = (data['weeks_played'] == 1).astype(int)
    return data

# GET EXPERIENCE VALUE ------------------------------------------------------------------
def get_experience_value(player_row):
    # Access 'exp' as an array if possible; otherwise, set to 0 if it's missing or empty
    exp_value = player_row['exp'].values if hasattr(player_row['exp'], 'values') else player_row['exp']
    
    # Check if exp_value is empty or invalid, then assign 0 if so
    if isinstance(exp_value, (list, np.ndarray)) and exp_value.size > 0:
        exp_value = exp_value[0]
    elif exp_value is None or not isinstance(exp_value, int):
        exp_value = 0

    return exp_value

def adjust_experience(exp, lookback):
    if exp > lookback:
        return lookback
    else:
        return exp
    
def create_player_experience_df(playerID, adjusted_exp):
    current_year = datetime.now().year
    years = [current_year - i for i in range(adjusted_exp)]
    df = pd.DataFrame({
        'playerId': [playerID] * adjusted_exp,  # Same player ID for each row
        'Year': years  # List of years
    })
    
    return df

def load_wr_model():
    model = joblib.load('models/wr-model.pkl')
    return model

def run_wr_model(model, week, lag_yds, cumulative_yards_per_game, cumulative_receptions_per_game, cumulative_targets_per_game, avg_receiving_yards_last_3, avg_receptions_last_3, avg_targets_last_3, yards_per_reception, td_rate_per_target, is_first_week):
    # Ensure parameters are correctly formatted
    parameters = np.array([[float(week), float(lag_yds), float(cumulative_yards_per_game), 
                            float(cumulative_receptions_per_game), float(cumulative_targets_per_game), 
                            float(avg_receiving_yards_last_3), float(avg_receptions_last_3), 
                            float(avg_targets_last_3), float(yards_per_reception), 
                            float(td_rate_per_target), int(is_first_week)]])
    # Perform prediction
    likelihood = model.predict_proba(parameters)[:, 1]
    return likelihood[0]

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
    else:  # Negative odds
        odds = (probability / (1 - (probability / 100))) * -1
        direction = ''
    
    return f"{direction}{round(odds)}"

@st.cache_data
def get_all_player_logs_and_odds(dfRoster, _wrmodel, upcoming_year, upcoming_week):

    player_data = []

    # 1. Iterate through entire list of players from teams selected in the selectbox to get game data
    for _, player_row in dfRoster.iterrows():
        player_id = player_row['playerId']
        player_name = player_row['fullName']
        headshot = player_row['headshot']
        # 1.1 Get player experience DF
        exp_value = get_experience_value(player_row)
        adjusted_exp = adjust_experience(exp_value, 3)

        # 1.2 Create the DataFrame of player experience for the API
        playerExperienceDF = create_player_experience_df(player_id, adjusted_exp)

        # 1.3 Fetch game logs and process if data exists
        if not playerExperienceDF.empty:
            try:
                gameLog = scrape_game_log(playerExperienceDF)
            except ValueError as e:
                gameLog = pd.DataFrame()
            if not gameLog.empty:
                gameLog['fullName'] = player_name
                gameData = add_new_features_lag(gameLog)
                gameData['seasonYr'] = gameData['seasonYr'].astype(int)

                # 1.4 Source Prior Week from incoming parameter and check if prior week is empty, otherwise look back
                # one more week
                prior_week = upcoming_week - 1 
                prior_week_data = gameData[(gameData['seasonYr'] == upcoming_year) & (gameData['week'] == prior_week)]

                while prior_week_data.empty and prior_week > 0:
                    prior_week -=1
                    prior_week_data = gameData[(gameData['seasonYr'] == upcoming_year) & (gameData['week'] == prior_week)]

                if prior_week_data.empty:
                    continue

                if len(prior_week_data) != 1:
                    continue

                prior_week_data = prior_week_data.replace([np.inf, -np.inf], 0).fillna(0)

                # 2. Create Features for Model from Prior Week Game Data
                lag_yds = prior_week_data['receivingYards'].values[0]
                cumulative_yards_per_game = prior_week_data['cumulative_yards_per_game'].values[0]
                cumulative_receptions_per_game = prior_week_data['cumulative_receptions_per_game'].values[0]
                cumulative_targets_per_game = prior_week_data['cumulative_targets_per_game'].values[0]
                avg_receiving_yards_last_3 = prior_week_data['avg_receiving_yards_last_3'].values[0]
                avg_receptions_last_3 = prior_week_data['avg_receptions_last_3'].values[0]
                avg_targets_last_3 = prior_week_data['avg_targets_last_3'].values[0]
                yards_per_reception = prior_week_data['yards_per_reception'].values[0]
                td_rate_per_target = prior_week_data['td_rate_per_target'].values[0]
                is_first_week = prior_week_data['is_first_week'].values[0]
                # 2.1 Display Features
                cumulative_receiving_touchdowns = prior_week_data['cumulative_receiving_touchdowns'].values[0]

                # 2.2 Calculate touchdown likelihood
                td_likelihood = run_wr_model(_wrmodel, upcoming_week, lag_yds, cumulative_yards_per_game, cumulative_receptions_per_game, cumulative_targets_per_game, avg_receiving_yards_last_3, avg_receptions_last_3, avg_targets_last_3, yards_per_reception, td_rate_per_target, is_first_week)

                if td_likelihood is None:
                    td_likelihood = 0
                # 2.3 Store the player name and calculated odds
                player_data.append({
                    'Player': player_name,
                    'headshot': headshot,
                    'td_rate_per_target': td_rate_per_target,
                    'season_td_total': cumulative_receiving_touchdowns,
                    'td_likelihood': td_likelihood,
                    'odds': decimal_to_american_odds(td_likelihood)
                })

    player_df = pd.DataFrame(player_data)#.sort_values(by='td_likelihood').head(15)
    
    return player_df

# GET NFL Season Start ---------------------------------
def get_current_nfl_week():
    # 1. Instantiate Today
    today = datetime.today()
    # 2. Define NFL season start dates, with each season starting on the first Thursday after Labor Day
    nfl_start_dates = {
        2024: datetime(2024, 9, 5),
        2025: datetime(2025, 9, 5),
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
