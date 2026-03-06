"""American odds ↔ implied probability conversion."""


def implied_prob_from_american(odds: int) -> float:
    """
    Convert American odds to implied probability (vig-inclusive).

    +250 → 1 / (1 + 250/100) = 0.2857
    -150 → 150 / (150 + 100) = 0.6000
    """
    if odds > 0:
        return 100 / (odds + 100)
    else:
        return abs(odds) / (abs(odds) + 100)


def american_from_prob(prob: float) -> int:
    """
    Convert probability to American odds (no vig applied).
    Returns the nearest integer.

    0.2857 → +250
    0.6000 → -150
    """
    if prob <= 0 or prob >= 1:
        raise ValueError(f"Probability must be between 0 and 1, got {prob}")
    if prob < 0.5:
        return round(100 / prob - 100)
    else:
        return round(-prob * 100 / (1 - prob))
