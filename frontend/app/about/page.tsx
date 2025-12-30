export default function AboutPage() {
  return (
    <div className="min-h-screen">
      <header className="bg-gray-900 text-white py-6">
        <div className="container mx-auto px-4">
          <h1 className="text-3xl font-bold">About BGGTDM</h1>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8 max-w-4xl">
        <div className="prose dark:prose-invert max-w-none">
          <h2>What is Big Game Gabe?</h2>
          <p>
            The Big Game Gabe fallacy is something my friends and I coined while
            following Gabe Davis, especially in fantasy football and prop bets.
            It's based on the observation that Davis seems to have a huge,
            standout performance roughly once every four or five weeks. Despite
            underwhelming stretches, when he "goes off," it's often in a
            spectacular fashion with long touchdowns and big yardage totals. We
            started calling these systematic but explosive games "Big Game Gabe"
            moments.
          </p>

          <h2>How Does the Model Work?</h2>
          <p>
            The touchdown likelihood model is a Random Forest ML model, designed
            to predict whether a player will score a touchdown in the upcoming
            week. It's trained on a variety of features such as a player's
            previous game statistics (e.g., receptions, yards, touchdowns) and
            player-specific information like height, weight, and draft position,
            and team/opponent specific information.
          </p>
          <p>
            The training data set is the total game logs for all NFL WRs for the
            past 3 NFL regular seasons. The model outputs a likelihood score,
            which can be interpreted as the probability that the player will
            score a touchdown in the next game.
          </p>

          <h2>Finding Value</h2>
          <p>
            By comparing our model's implied odds to sportsbook odds, we can
            identify opportunities where the market may have mispriced a player's
            true touchdown probability. This is displayed through our weighted
            value metric, which accounts for both the magnitude of the edge and
            the base probability of the event.
          </p>

          <h2>Disclaimer</h2>
          <p className="text-sm text-gray-600">
            This tool is for entertainment and educational purposes only. Past
            performance does not guarantee future results. Please gamble
            responsibly and never wager more than you can afford to lose.
          </p>
        </div>
      </main>
    </div>
  );
}
