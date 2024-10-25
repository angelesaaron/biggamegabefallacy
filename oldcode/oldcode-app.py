# GABE DAVIS MODEL CODE



def load_gabedavis_model():
    model = joblib.load('models/random_forest_model.pkl')
    return model
    
def run_gabedavis_model(model, week, rec, yds, tds, tgts):
    next_week_stats = [[week, tds, rec, yds, tgts]]
    likelihood = model.predict_proba(next_week_stats)[:, 1]
    return likelihood[0]


#########################################
##### (Default) Gabe Davis Tab ##########
#########################################
with tab_gabedavis:
    # Game Log
    st.write("Here is Gabe Davis' game log since becoming an established receiver with Buffalo 2021:")
    file_path = "data/G.DavisGameLog.csv"  # Update this with your local file path
    try:
        df = pd.read_csv(file_path)
        df = df[['seasonYr', 'week', 'receptions', 'receivingYards', 'receivingTouchdowns']]
        df['seasonYr'] = df['seasonYr'].astype(str)
        df = df.rename(columns={'seasonYr':'Season',
                                            'week':'Week',
                                            'receivingYards': 'Rec. Yards',
                                            'receivingTouchdowns':'Rec. TDs',
                                            'receptions':'Receptions'})
        st.dataframe(df)# hide_index=True)
    except Exception as e:
        st.error(f"Error loading file: {e}")

    st.write("I've trained random forest model to calculate the likelihood of a Gabe Davis scoring a TD next week.")

    st.write("Please enter the upcoming NFL Week, and  Gabe Davis' previous game stats: ")

    # MODEL
    model = load_gabedavis_model()
    weekNo = st.number_input("What is the upcoming week?", min_value = 1, max_value = 18, step = 1)
    gabe_prevYds = st.number_input("How many yards did Gabe have last week?", min_value = 0, step=1)
    gabe_prevRec = st.number_input("How many receptions did Gabe have last week?", min_value = 0, step=1)
    gabe_prevTD = st.number_input("How many touchdowns did Gabe have last week?", min_value = 0, step=1)
    gabe_prevTgts = st.number_input("How many targets did Gabe have last week?", min_value = 0, step=1)

    if st.button("Predict"):
        td_likelihood = run_gabedavis_model(model, weekNo, gabe_prevRec, gabe_prevYds, gabe_prevTD, gabe_prevTgts)
        st.write(f'The likelihood of Gabe Davis scoring a touchdown this week is: {td_likelihood*100}%')