from decimal import Decimal
from typing import Tuple


def decimal_to_american_odds(probability: float) -> Tuple[str, float, int]:
    """
    Convert probability to American odds format.

    Args:
        probability: Float between 0 and 1

    Returns:
        Tuple of (formatted_string, raw_odds, favor)
        - formatted_string: "+250" or "-150"
        - raw_odds: 250.0 or -150.0
        - favor: 1 for underdog (+), -1 for favorite (-)
    """
    if probability is None or probability == 0:
        return "+999", 999.0, 1

    probability_pct = round(probability * 100)

    if probability_pct <= 0:
        return "+999", 999.0, 1
    elif probability_pct >= 100:
        return "-999", -999.0, -1

    if probability_pct < 50:  # Underdog (positive odds)
        odds = (100 / (probability_pct / 100)) - 100
        direction = '+'
        favor = 1
    else:  # Favorite (negative odds)
        odds = (probability_pct / (1 - (probability_pct / 100))) * -1
        direction = ''
        favor = -1

    formatted = f"{direction}{round(odds)}"
    return formatted, odds, favor


def american_to_implied_probability(odds: float) -> float:
    """
    Convert American odds to implied probability.

    Args:
        odds: American odds (e.g., +250 or -150)

    Returns:
        Float probability between 0 and 1
    """
    if odds > 0:
        return 100 / (odds + 100)
    else:
        return abs(odds) / (abs(odds) + 100)


def format_american_odds(odds: float) -> str:
    """Format odds as American string with proper sign"""
    if odds > 0:
        return f"+{int(odds)}"
    else:
        return str(int(odds))
