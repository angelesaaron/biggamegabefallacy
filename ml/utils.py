import numpy as np
import matplotlib.pyplot as plt


def american_to_implied_prob(odds):
    """Convert American odds to vig-adjusted implied probability (~5% vig removal)."""
    if odds > 0:
        raw = 100 / (odds + 100)
    else:
        raw = abs(odds) / (abs(odds) + 100)
    return raw / 1.05


def prob_to_american(p):
    """Convert probability to American odds (rounded to nearest 5)."""
    p = np.clip(p, 0.001, 0.999)
    if p >= 0.5:
        odds = -round((p / (1 - p)) * 100 / 5) * 5
    else:
        odds = round(((1 - p) / p) * 100 / 5) * 5
    return int(odds)


def reliability_diagram(y_true, y_prob, n_bins=10, title='', ax=None):
    """Plot a reliability diagram (calibration curve)."""
    y_true = np.array(y_true)
    y_prob = np.array(y_prob)

    bins = np.linspace(0, 1, n_bins + 1)
    bin_means, bin_fracs, bin_counts = [], [], []
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (y_prob >= lo) & (y_prob < hi)
        if mask.sum() > 0:
            bin_means.append(y_prob[mask].mean())
            bin_fracs.append(y_true[mask].mean())
            bin_counts.append(mask.sum())

    bin_means = np.array(bin_means)
    bin_fracs = np.array(bin_fracs)

    if ax is None:
        fig, ax = plt.subplots(figsize=(6, 5))

    ax.plot([0, 1], [0, 1], 'k--', label='Perfect calibration', alpha=0.5)
    sc = ax.scatter(bin_means, bin_fracs, s=[c / 2 for c in bin_counts],
                    alpha=0.8, zorder=5)
    ax.plot(bin_means, bin_fracs, 'o-', alpha=0.6)
    ax.set_xlabel('Mean predicted probability')
    ax.set_ylabel('Fraction of positives')
    ax.set_title(title or 'Reliability Diagram')
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    max_dev = np.max(np.abs(bin_means - bin_fracs)) if len(bin_means) > 0 else float('nan')
    ax.text(0.05, 0.92, f'Max deviation: {max_dev:.3f}',
            transform=ax.transAxes, fontsize=9)

    return bin_means, bin_fracs, bin_counts
