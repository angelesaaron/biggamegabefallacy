#!/usr/bin/env python
# coding: utf-8


import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import requests
from datetime import datetime
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.ensemble._forest import ForestClassifier
import joblib
import pickle

rapidapi_key = st.secrets["api"]["rapidapi_key"]

st.set_page_config(page_title="Big Game Fallacy?", initial_sidebar_state="expanded")

#####################################################
########### Load and Prep Data ######################
####################################################

# LOAD TEAMS -------------------------------------------------------------------------
def load_teams():
    dfTeams = pd.read_csv('data/teamList.csv')
    dfTeams['FullName'] = dfTeams['location'] + ' ' + dfTeams['name']
    return dfTeams

# LOAD ROSTER -------------------------------------------------------------------------
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
        "headshot"
    ]

    roster = pd.DataFrame(rows, columns=column_headers)

    rosterWR = roster[roster['position'] == 'WR']
    rosterWR['fullName'] = rosterWR['firstName'] + ' ' + rosterWR['lastName']
    rosterWR.loc[rosterWR['exp'] == 0, 'exp'] = 1

    return rosterWR

# LOAD GAME LOG -------------------------------------------------------------------------
def scrape_game_log(playerExperience):
    
    logurl = "https://nfl-api1.p.rapidapi.com/player-game-log"
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "nfl-api1.p.rapidapi.com"
    }

    # Initialize list to hold rows of data
    rows = []

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

# GENERATE FEATURES -------------------------------------------
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

def get_experience_value(player_row):
    exp_value = player_row['exp'].values
    if exp_value.size > 0:
        exp_value = exp_value
    else:
        exp_value[0] = 0
    return exp_value[0]

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
    
    # Make sure the shape is correct
    print("Parameters:", parameters)
    print("Shape:", parameters.shape)

    # Perform prediction
    likelihood = model.predict_proba(parameters)[:, 1]
    return likelihood[0]

# AMERICAN ODDS
def decimal_to_american_odds(percentage):
    if percentage <= 0 or percentage >= 1:
        raise ValueError("Percentage must be in the range (0, 1)")

    if percentage < 0.5:
        # Convert to positive American odds for less likely outcomes
        american_odds = 100 * (1 - percentage) / percentage
        direction = '+'
    else:
        # Convert to negative American odds for more likely outcomes
        american_odds = -100 / (percentage / (1 - percentage))
        direction = '-'
    return f"{direction}{round(american_odds)}"



################################################################################################################################################
    
##########################################
##  Title, Tabs, and Sidebar            ##
##########################################
st.title("Big Game Fallacy?")
st.write("Is Big Game Gabe coming out next week? See what the model says")

#tab_player, tab_gabedavis, tab_faq = st.tabs(["Receiver Selection", 'Gabe Davis', 'FAQ'])
tab_player, tab_faq = st.tabs(["Receiver Selection", 'FAQ'])

col1, col2, col3 = st.sidebar.columns([1,8,1])
with col1:
    st.write("")
with col2:
    st.image('images/gabeDavisPicture.png',  use_column_width=True)
with col3:
    st.write("")

st.sidebar.markdown(" ## Big Game Gabe Theory")
st.sidebar.markdown('''The Big Game Gabe fallacy is something my friends and I coined while following Gabe Davis, especially in fantasy football and prop bets. It’s based on the observation that Davis seems to have a huge, standout performance roughly once every four or five weeks. Despite underwhelming stretches, when he "goes off," it’s often in a spectacular fashion with long touchdowns and big yardage totals. We started calling these systematic but explosive games “Big Game Gabe” moments. It’s become a running joke when betting on his performance, as we wait for his patented once-a-month breakout
''')

#########################################
##### Player Tab ########################
#########################################


with tab_player:
    
    # Player Selection Header ------------------------------------
    st.subheader("Choose a receiver:")
    # Prompt for selecting team
    dfTeams = load_teams()
    default_team = 'Jacksonville Jaguars'

    # TEAM SELECT BOX --------------------------------
    selected_team = st.selectbox("Select an NFL team:", dfTeams['FullName'], index = 14)
    selected_team_row = dfTeams[dfTeams['FullName'] == selected_team]
    # Display the ID value based on the selected row
    if not selected_team_row.empty:
        team_id = selected_team_row['id'].values[0]  # Retrieve the TeamID from the selected row
        #st.write(f"Team ID: {team_id}")
        dfRoster = load_roster(team_id)

        # PLAYER SELECT BOX ------------------------------
        selected_player = st.selectbox("Select an receiver:", dfRoster['fullName'], index=2)
        selected_player_row = dfRoster[dfRoster['fullName'] == selected_player]
        if not selected_player_row.empty:
            player_id = selected_player_row['playerId'].values[0]
            #st.dataframe(selected_player_row)
            #st.write(f"Player ID: {player_id}")
            st.image(selected_player_row['headshot'].values[0], width=300)
            st.divider()
            exp_value = get_experience_value(selected_player_row)
            #st.write(selected_player_row['exp'].values[0])

            # PLAYER EXPERIENCE BOX ------------------------------
            st.subheader(f"{selected_player_row['fullName'].values[0]} - Game Log:")

            # Look back hard coded to 3 years (same as model trained) 

            adjusted_exp = adjust_experience(exp_value, 3)

            # Generate player experience DF for game log loop
            playerExperienceDF = create_player_experience_df(player_id, adjusted_exp)

            if not playerExperienceDF.empty:
                # SCRAPE GAME LOG DATA

                gameLog = scrape_game_log(playerExperienceDF)
                if not gameLog.empty:

                    # GENERATE FEATURES
                    gameLog['fullName'] = selected_player_row['fullName'].iloc[0]
                    gameLog.to_csv('testgamelog.csv', index=False)
                    gameData = add_new_features_lag(gameLog)

                    # DISPLAY GAME LOG
                    gameLogDisplay = gameLog[['seasonYr', 'week', 'receptions', 'receivingTargets' ,'receivingYards', 'receivingTouchdowns']]
                    gameLogDisplay = gameLogDisplay.rename(columns={'seasonYr':'Season',
                                                                        'week':'Week',
                                                                        'receivingYards': 'Yards',
                                                                        'receivingTouchdowns':'TD',
                                                                        'receptions':'Receptions',
                                                                        'receivingTargets':'Targets'
                                                                        })
                    st.write('Game Log')
                    st.dataframe(gameLogDisplay)#, hide_index=True)
                    st.divider()
                    #st.dataframe(gameLog)

                    ########################################################################
                    ############################# MODEL ####################################

                    st.subheader("Touchdown Likelihood:")
                    st.write(f"Calculate the likelihood for {selected_player_row['fullName'].values[0]} to score a touchdown next week.")
                    #### Load Model
                    wrmodel = load_wr_model()

                    ## Game Log Data ------------------------------------------------------

                    # 1. BINARY FLAG
                    gameData['td'] = (gameData['receivingTouchdowns'] > 0).astype(int)

                    # 2. PREVIOUS GAME STATS
                    df_previous_game = gameData.iloc[-1]
                    lag_Yds = df_previous_game['receivingYards']
                    lag_REC = df_previous_game['receptions']
                    lag_td = df_previous_game['td']
                    lag_REC_TD = df_previous_game['receivingTouchdowns']
                    lag_TGT = df_previous_game['receivingTargets']

                    # 3. OTHER PARAMETERS
                    cumulative_yards_per_game = df_previous_game['cumulative_yards_per_game']
                    cumulative_receptions_per_game = df_previous_game['cumulative_receptions_per_game']
                    cumulative_targets_per_game = df_previous_game['cumulative_targets_per_game']
                    avg_receiving_yards_last_3 = df_previous_game['avg_receiving_yards_last_3']
                    avg_receptions_last_3 = df_previous_game['avg_receptions_last_3']
                    avg_targets_last_3 = df_previous_game['avg_targets_last_3']
                    yards_per_reception = df_previous_game['yards_per_reception']
                    td_rate_per_target = df_previous_game['td_rate_per_target']
                    is_first_week = df_previous_game['is_first_week']

                    # 4. GET NEXT WEEK otherwise default to WEEK 1
                    nextWeek = (df_previous_game['week']) + 1
                    if nextWeek > 18:
                        nextWeek = 1
                    else:
                        nextWeek = nextWeek
                    
                    #nextWeek = nextWeek.astype(int)

                    #### UI ELEMENTS

                    # Week
                    paramWeek = st.number_input('Upcoming NFL Week: ', min_value=1, max_value=18, value=nextWeek)

                    # INPUTS
                    st.markdown("Please input the **previous** week game statistics: ")
                    st.caption("This will default to last game statistics for the selected player.")
                    paramRec = st.number_input('Receptions: ', min_value=0, value=lag_REC, step=1)
                    paramYds = st.number_input("Receiving Yards: ", min_value=0, value=lag_Yds, step=1)
                    paramTD = st.number_input("Touchdowns: ", min_value=0, value=lag_REC_TD, step=1)
                    paramTgts = st.number_input("Targets: ", min_value=0, value=lag_TGT, step=1)

                    # Processing 

                    # PREDICTION
                    if st.button("Predict "):
                        td_likelihood = run_wr_model(wrmodel, paramWeek, paramYds, cumulative_yards_per_game, cumulative_receptions_per_game, cumulative_targets_per_game, avg_receiving_yards_last_3, avg_receptions_last_3, avg_targets_last_3, yards_per_reception, td_rate_per_target, is_first_week)

                        st.markdown(f'''
                            The likelihood of {selected_player_row['fullName'].values[0]} scoring a touchdown is **{round(td_likelihood*100, 2)} %**
                            ''')

                        odds = decimal_to_american_odds(td_likelihood)

                        st.markdown(f'''
                            The expected American Odds of {selected_player_row['fullName'].values[0]} scoring a touchdown is **{odds}**
                            ''')

                        
                else:
                    ("No game log. Model cannot predict without historical game data.")
                    
            else:
                st.write("No year limit selected.")
        else:
            st.write("No player selected.")
            
    else:
        st.write("No team selected.")

with tab_faq:
    st.markdown(" ### Frequently Asked Questions 🔎 ")
    st.write("Both the touchdown likelihood model and the Gabe Davis model are still being continually refined and improved to enhance their accuracy and predictive capabilities.")

    expand_faq3 = st.expander('''Who is Gabe Davis?''')
    with expand_faq3:
        st.write('''
        **Gabe Davis** is an NFL wide receiver who plays for the Jacksonville Jaguars in the NFL.
        He was drafted by the Buffalo Bills in the 4th round of the 2020 NFL Draft out of the University of Central Florida (UCF).
        Davis quickly became known for his big-play ability, particularly as a deep threat due to his size (6'2", 210 lbs) and speed.
        He made headlines with a standout performance in the 2021-2022 playoffs, where he caught four touchdown passes in a single game against the Kansas City Chiefs, setting an NFL playoff record.
        ''', unsafe_allow_html=True)

    expand_faq4 = st.expander('''What is Big Game Gabe Fallacy?''')
    with expand_faq4:
        st.write('''
        The **Big Game Gabe fallacy** is something my friends and I coined while following Gabe Davis, especially in fantasy football and prop bets.
        It’s based on the observation that Davis seems to have a huge, standout performance roughly once every four or five weeks.
        Despite underwhelming stretches, when he "goes off," it’s often in a spectacular fashion with long touchdowns and big yardage totals.
        We started calling these systematic but explosive games “Big Game Gabe” moments.
        It’s become a running joke when betting on his performance, as we wait for his patented once-a-month breakout.
        ''')

    expand_faq1 = st.expander('''What is the TD likelihood model?''')
    with expand_faq1:
        
        st.write('''
        The touchdown likelihood model in the Player Selection tab is a Random Forest ML model, designed to predict whether a player will score a touchdown in the upcoming week.
        It’s trained on a variety of features such as a player's previous game statistics (e.g., receptions, yards, touchdowns) and player-specific information like height, weight and draft position, and team/opponent specific information. 
        The training data set is the total game logs for all NFL WRs for the past 3 NFL regular seasons.
        The model outputs a likelihood score, which can be interpreted as the probability that the player will score a touchdown in the next game.
        ''', unsafe_allow_html=True)

    expand_faq2 = st.expander('''What is a Random Forest Model?''')
    with expand_faq2:
            st.write('''
            A Random Forest model works by constructing multiple decision trees during training and then aggregating their predictions to make a final decision.
            Each tree considers different subsets of the data, making the model more robust to overfitting and better at generalizing to unseen data.
            ''', unsafe_allow_html=True)

    
    ##########



# Display the roster
# st.write("### Data Preview")
# st.dataframe(data)

# Plot using matplotlib or seaborn
# st.write("### Data Plot")
# fig, ax = plt.subplots()
# sns.scatterplot(data=data, x='week', y='fPts', ax=ax)
# st.pyplot(fig)

# Add widgets like sliders, buttons, etc.
#st.write("### Select a Range")
#range_val = st.slider("Select a range", 0, 100, (25, 75))
#st.write(f"Selected range: {range_val}")



# In[ ]:




