#!/usr/bin/env python
# coding: utf-8
from utils import *
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
import plotly.express as px

st.set_page_config(page_title="Big Game Fallacy?", initial_sidebar_state="expanded")

##########################################
##     Title, Tabs, and Sidebar         ##
##########################################

# Title 
st.title("Big Game Gabe Touchdown Model?")
st.write("Pick an NFL pass catcher and see if they're due for a Gabe Davis style Big Game")

# Tabs
tab_player, tab_best_odds, tab_performance, tab_faq = st.tabs(["Receiving TD Model", "Weekly Best Odds", 'Past Performance', 'FAQ'])

# Sidebar
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

##########################################
##       1. Player Tab                  ##
##########################################

with tab_player:

    # Prompt 1 - Player Selection ------------------------------------------------------------------------------------

    # Text
    st.subheader("Choose a receiver:")

    # Load Teams
    dfTeams = load_teams()

    # Validate Team Data
    if dfTeams.empty or 'FullName' not in dfTeams.columns:
        st.error("Team data is unavailable. Please check back later.")
        st.stop()

    # Validate Default Index = Jacksonville Jaguars
    try:
        default_team_index = dfTeams[dfTeams['FullName'] == 'Jacksonville Jaguars'].index[0]
    except IndexError:
        default_team_index = 0
    default_team_index= int(default_team_index) # Fallback to the first option if default is not found

    # Team Select Drop Down
    selected_team = st.selectbox("Select an NFL team:", dfTeams['FullName'], index=default_team_index)

    # Validate Selected Team
    selected_team_row = dfTeams[dfTeams['FullName'] == selected_team]
    if selected_team_row.empty:
        st.warning("Invalid team selected. Please try again.")
        st.stop()

    # Validate team_id
    team_id = selected_team_row['id'].values[0]
    if not team_id or not isinstance(team_id, (int, str, np.int64)):
        st.error("Invalid team ID. Unable to load roster for the selected team.")
        st.stop()

    # Prompt 2 - Player Selection -------------------------------------------------------------------------------------
    
    # Load Roster
    dfRoster = get_team_roster(team_id)
    if dfRoster.empty or 'fullName' not in dfRoster.columns:
        st.error("Roster data is unavailable for the selected team.")
        st.stop()
    
    # Player Select Drop Down
    selected_player = st.selectbox("Select a receiver:", dfRoster['fullName'], index=6)

    # Validate Selected Player
    selected_player_row = validate_active_player(dfRoster, selected_player)
    # Validate Player ID
    player_id = selected_player_row['playerId']
    if not player_id or not isinstance(player_id, (int, str, np.int64)):
        st.error("Invalid player ID. Unable to load player for the selected team.")
        st.stop()
    
    # Validate Player Image
    player_image = selected_player_row['headshot']
    if not player_image or not isinstance(player_image, str):
        st.error("Unable to load headshot for the selected player.")

    # Display Image
    st.image(player_image, width=300)
    st.divider()

    # Data Retrieval 1 - Player Data -----------------------------------------------------------------------------------
    try:
        gameLogData = load_data(selected_player_row)
    except ValueError as e:
        st.error(str(e))
        st.stop()

    # Model Parameters 1 -----------------------------------------------------------------------------------------------
    try:
        stats = extract_previous_game_stats(gameLogData)
        required_keys = [
            'nextWeek', 'lag_yds', 'cumulative_yards_per_game', 
            'cumulative_receptions_per_game', 'cumulative_targets_per_game', 
            'avg_receiving_yards_last_3', 'avg_receptions_last_3', 
            'avg_targets_last_3', 'yards_per_reception', 
            'td_rate_per_target', 'is_first_week'
        ]
        missing_keys = [key for key in required_keys if key not in stats]
        if missing_keys:
            raise ValueError(f"Missing required stats keys: {missing_keys}")

    except ValueError as e:
        st.error(f"Error extracting game stats: {str(e)}")
        st.stop()


    # Display Week + Year
    # Get Week + Year
    year, week = get_current_nfl_week()
    st.markdown(f'''
    Click `Predict` to see:  {selected_player_row['fullName']} - NFL Week {week} anytime touchdown scorer odds.
    ''')
    # Execute Model 1 ----------------------------------------------------------------------------------------------------
    if st.button("Predict "):

        try:
            # Run Model
            td_likelihood = run_td_model(stats)

            # Validate Model Output
            if not isinstance(td_likelihood, (float, int)):
                raise ValueError("Prediction returned an invalid result.")

            # Display Likelihood
            # st.markdown(f'''
            #     The likelihood of {selected_player_row['fullName']} scoring a receiving touchdown is: 
            #     ##### {round(td_likelihood*100, 2)} %
            #     ''')
            # Using HTML to center content

            st.markdown(f"""
                <div style="text-align: left;">
                    <p>The likelihood of {selected_player_row['fullName']} scoring a receiving touchdown is: </p>
                </div>
                <div style="text-align: center;">
                    <h5>{round(td_likelihood*100, 2)} %</h5>
                </div>
            """, unsafe_allow_html=True)

            # Fetch Odds
            odds_str, odds, favor = decimal_to_american_odds(td_likelihood)

            # Display Odds
            # st.markdown(f'''
            #     The expected American Odds of {selected_player_row['fullName']} scoring a receiving touchdown is: 
            #     ##### {odds_str}
            #     ''')
            st.markdown(f"""
                <div style="text-align: left;">
                    <p>The expected American Odds of {selected_player_row['fullName']} scoring a receiving touchdown is: </p>
                </div>
                <div style="text-align: center;">
                    <h5>{odds_str}</h5>
                </div>
            """, unsafe_allow_html=True)
            
            # Get Individual Player Odds ---------------------------------------------------------------------------------
            combineddf = create_player_odds_df(odds, selected_player_row['fullName'])
            
            # Create Heatmap
            create_heatmap(combineddf)
            
        except ValueError as e:
            st.error(f"Error during prediction: {str(e)}")
            st.stop()


##########################################
##       2. Weekly Best Odds            ##
##########################################
with tab_best_odds:

    # Model Best Odds -------------------------------------------------------------------
    # Get Year + Week
    year, week = get_current_nfl_week()

    # Title
    st.markdown(f'''
    ### NFL Week {week} - Model's Value Anytime TD Odds
    ''')
    # Model's Best Odds
    st.markdown(f'''
    ##### Model's Best Odds in Week {week}
    ''')

    # Get the model odds
    modelOdds = best_odds_model()

    # Data Validation for modelOdds
    if modelOdds is not None and not modelOdds.empty:
        st.dataframe(modelOdds, use_container_width = True)
    else:
        st.warning("No model odds available for this week.")

    st.divider()
    
    # Best Value on Sports Book
    provider_list = ['DraftKings', 'FanDuel', 'BetOnline.ag', 'BetRivers', 'BetMGM', 'Bovada']

    # Validate provider selection
    provider = st.selectbox("Choose a provider:", provider_list, index=0)
    # Model's Best Odds
    st.markdown(f'''
    ##### {provider} Best Value Odds in Week {week}
    ''')

    # Data Validation for provider odds
    if provider is not None and provider in provider_list:
        providerOdds = best_odds_provider(provider)

        if providerOdds is not None and not providerOdds.empty:
            st.dataframe(providerOdds, use_container_width = True)
        else:
            st.warning(f"No odds available for {provider}.")
        


##################################
##     3. Past Performance      ##
##################################
with tab_performance:
    # Unit Size
    unit_size = st.number_input("Choose unit size:", min_value= 0, step=1, placeholder = 10)
    # Best Value on Sports Book
    st.markdown(f'''
                ### Last Week Model Picks
                To change provider, navigate to `Weekly Best Odds Tab`
                ''')
    
    percent, winnings, performance = get_past_performance(provider="Sportsbook", unit=unit_size, is_model=True)


     # Check for None and handle appropriately
    if percent is not None:
        st.metric("Winning %", f"{percent * 100}%")
    else:
        st.metric("Winning %", "Data not available")  # Show a default message if percent is None

    if winnings is not None:
        st.metric("Net Balance", f"{round(winnings, 2)}")
    else:
        st.metric("Net Balance", "Data not available")  # Show a default message if winnings is None

    # Display performance data
    st.dataframe(performance, use_container_width=True)

    st.divider()

    st.markdown(f'''
                ### Last Week Best Value Picks - {provider}
                To change provider, navigate to `Weekly Best Odds Tab`
                ''')
    
    percent_provider, winnings_provider, performance_provider = get_past_performance(provider, unit=unit_size, is_model=False)


     # Check for None and handle appropriately
    if percent_provider is not None:
        st.metric("Winning %", f"{percent_provider* 100}%")
    else:
        st.metric("Winning %", "Data not available")  # Show a default message if percent is None

    if winnings_provider is not None:
        st.metric("Net Balance", f"{round(winnings_provider, 2)}")
    else:
        st.metric("Net Balance", "Data not available")  # Show a default message if winnings is None

    # Display performance data
    st.dataframe(performance_provider, use_container_width=True)
    


#########################################
##### FAQ Tab ########################
#########################################
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

    st.divider()
    # Add Button to Reload Odds
    reload_odds = st.button('Reload Odds')

    if reload_odds:
        # Call the function to reload odds (this will replace the downstream CSVs)
        reload_sportsbook_odds()
        load_or_fetch_odds(reload_odds=True)
        st.success('Odds have been reloaded and the downstream CSVs have been updated.')



    