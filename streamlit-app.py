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
##  Title, Tabs, and Sidebar            ##
##########################################
st.title("Big Game Fallacy?")
st.write("Is Big Game Gabe coming out next week? See what the model says")

#tab_player, tab_gabedavis, tab_faq = st.tabs(["Receiver Selection", 'Gabe Davis', 'FAQ'])
tab_player, tab_top_players, tab_faq = st.tabs(["Receiver Selection", "Best Odds", 'FAQ'])

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
        selected_player = st.selectbox("Select an receiver:", dfRoster['fullName'], index=0)
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
            st.subheader(f"{selected_player_row['fullName'].values[0]} - Historical Data:")

            # Look back hard coded to 3 years (same as model trained) 

            adjusted_exp = adjust_experience(exp_value, 3)
            lookbackTime = datetime.now().year - 3

            # Generate player experience DF for game log loop
            playerExperienceDF = create_player_experience_df(player_id, adjusted_exp)

            if not playerExperienceDF.empty:
                # SCRAPE GAME LOG DATA
                try:
                    gameLog = scrape_game_log(playerExperienceDF)
                except ValueError as e:
                    st.write("Game Log Data not found!")
                    gameLog = pd.DataFrame()

                #gameLog = scrape_game_log(playerExperienceDF)
                if not gameLog.empty:

                    # GENERATE FEATURES
                    gameLog['fullName'] = selected_player_row['fullName'].iloc[0]
                    #gameLog.to_csv('testgamelog.csv', index=False)
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

                    with st.expander("View Game Log", expanded=False):
                        st.dataframe(gameLogDisplay)#, hide_index=True)
                    
                    #### DATA VISUALIZATION ------

                    # Create a select box for users to choose the Y variable
                    with st.expander("View Chart Data", expanded=False): 
                        y_variable = st.selectbox(
                            'Select Variable',
                            options=['TD', 'Yards', 'Receptions', 'Targets'],
                            index=0  # Default index
                        )

                        # Determine aggregation method based on selected variable
                        displayVar = ''
                        if y_variable == 'TD':
                            # Sum for touchdowns
                            week_data = gameLogDisplay.groupby('Week').agg({'TD': 'sum'}).reset_index()
                            displayVar = 'Total'
                        else:
                            # Average for other variables
                            week_data = gameLogDisplay.groupby('Week').agg({y_variable: 'mean'}).reset_index()
                            displayVar = 'Average'

                        # Create the Altair bar chart
                        chart = alt.Chart(week_data).mark_bar().encode(
                            x=alt.X('Week:O', title='Week'),
                            y=alt.Y(f'{y_variable}:Q', title=f'Total {y_variable.capitalize()}' if y_variable == 'TD' else f'Average {y_variable.capitalize()}'),
                            tooltip=['Week:O', f'{y_variable}:Q']  # Show tooltip on hover
                        ).properties(
                            title=f'{displayVar} {y_variable.capitalize()} by Week since {lookbackTime}',
                            width=600,
                            height=400
                        )

                        # Display the chart in Streamlit
                        st.altair_chart(chart, use_container_width=True)

                    st.divider()
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

# TOP PLAYERS TAB ---------------------------------------------------------------------------------------------------------------       
with tab_top_players:
    st.markdown(" ### Team Best Odds this Week")
    
    # 1. Year/Week Inputs -------------------

    # 1.1 Year + Week from function
    year, week = get_current_nfl_week()
    # 1.2 Year Input
    current_year = st.number_input('Year: ' ,min_value=2021, value=year, max_value=year, step=1)
    # 1.3 Week Input
    upcoming_week = st.number_input('Week: ', min_value=1, max_value=18, value=week, step=1)

    # 2. Data Sourcing/Ingestion ------------

    # 2.1 Load Team List
    dfTeams = load_teams()

    # 2.2 Select Box for Teams
    selected_team_odds = st.multiselect("Select an NFL team(s):", dfTeams['FullName'])
    #st.write("This may take a few seconds to load.")

    if not selected_team_odds:
        st.warning("Please select at least one NFL team.")
    else:
        selected_team_odds_rows = dfTeams[dfTeams['FullName'].isin(selected_team_odds)]
        all_rosters = []
        st.write("This may take a few seconds to load.")

        # 2.3 Get Team IDs
        if not selected_team_odds_rows.empty:
            team_ids = selected_team_odds_rows['id']
            
            # 2.4 Load Rosters
            for team_id in team_ids:
                dfRoster = load_roster(team_id)
                if not dfRoster.empty:
                    all_rosters.append(dfRoster)

                # 2.5 Consolidate Rosters
                if all_rosters:
                    combined_roster_df = pd.concat(all_rosters, ignore_index=True)

                    # 3 Model -------------------------

                    # 3.1 Instantiate Model
                    wrmodel = load_wr_model()

                    # 3.2 Call Model
                    topodds = get_all_player_logs_and_odds(combined_roster_df, wrmodel, current_year, upcoming_week)
                    # 3.3 Print Data
                    topoddsDisplay = topodds[['Player', 'td_likelihood','odds']].sort_values(by='td_likelihood',ascending=False)
                    topoddsDisplay['td_likelihood'] = topoddsDisplay['td_likelihood'] * 100
                    topoddsDisplay = topoddsDisplay.rename(columns={'td_likelihood': 'TD Likelihood %', 'odds':'Model Odds'})
                    st.dataframe(topoddsDisplay)

                    # 4. Bubble Chart -------------------

                    # 4.1 Hover Elements
                    topodds['hover_text'] = (
                        topodds['Player'] + '<br>' +
                        'TD Likelihood: ' + (round(topodds['td_likelihood']* 100)).astype(str) +  '%' +'<br>' +
                        'TD Rate per Target: ' + (round(topodds['td_rate_per_target']*100).astype(str)) + '%' + '<br>' +
                        'Season TD Total: ' + topodds['season_td_total'].astype(str) + '<br>' +
                        'Odds: ' + topodds['odds'].astype(str)
                    )
                    fig = px.scatter(
                        topodds,
                        x='season_td_total',
                        y='td_rate_per_target',
                        size='td_likelihood',
                        hover_name= 'hover_text',
                        title='Player Touchdown Likelihood Bubble Chart'
                    )

                    # Add images to the scatter plot as layout shapes
                    for i, row in topodds.iterrows():
                        # Set a base size for the images and scale it based on td_likelihood
                        #base_size = 2.5  # Base size of the image
                        max_size = 3  # Cap the maximum image size
                        base_multiplier = 4
                        image_size = min(row['td_likelihood'] * base_multiplier, max_size)  # Scale and cap image size

                        fig.add_layout_image(
                            dict(
                                source=row['headshot'],
                                x=row['season_td_total'],
                                y=row['td_rate_per_target'],
                                xref="x",
                                yref="y",
                                sizex=image_size,  # Set the width of the image
                                sizey=image_size,  # Set the height of the image
                                opacity=1,  # Adjust opacity as needed
                                layer="above",
                                xanchor="center",  # Center the image on the x position
                                yanchor="middle"   # Center the image on the y position
                            )
                        )

                    # Update layout
                    fig.update_layout(
                        xaxis_title='Season TD Total',
                        yaxis_title='TD Rate per Target',
                        showlegend=False,
                        height=600,
                        width=800, # Set a consistent height for the chart
                        dragmode='pan'
                    )

                    # Display the Plotly figure in Streamlit
                    st.plotly_chart(fig, use_container_width=True)

                else:
                    st.write("No rosters available for the selected teams.")



# FAQ TAB -----------------------------------------------------------------------------------------------------------------------
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




