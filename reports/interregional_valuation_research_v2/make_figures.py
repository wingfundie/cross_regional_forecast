"""Static Figure 1: quarterly spread decomposition for the four region pairs (from evidence/spread_decomposition.csv)."""
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PAIRS = [('VIC to NSW', 'NSW minus VIC'), ('NSW to QLD', 'QLD minus NSW'), ('VIC to SA', 'SA minus VIC'), ('TAS to VIC', 'VIC minus TAS')]


def main():
    s = pd.read_csv(HERE / 'evidence/spread_decomposition.csv')
    s = s[s.complete]
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(4, 1, figsize=(11, 11.5), sharex=True, dpi=150)
    for ax, (d, title) in zip(axes, PAIRS):
        g = s[s.direction == d].sort_values('quarter')
        x = np.arange(len(g))
        ax.bar(x - .18, g.energy, .36, color='#255e7e', label='Capped energy')
        ax.bar(x + .18, g.scarcity, .36, color='#b8732d', label='Scarcity excess')
        ax.plot(x, g.spread, '-o', color='#222', ms=3.5, lw=1.4, label='Total spread')
        ax.axhline(0, color='#888', lw=.8)
        ax.set_title(title, loc='left', fontweight='bold', fontsize=11)
        ax.set_ylabel('AUD/MWh'); ax.grid(axis='y', color='#eee')
        ax.set_xticks(x); ax.set_xticklabels([q.replace('Q', ' Q') for q in g.quarter], rotation=45, ha='right')
    axes[0].legend(ncol=3, frameon=False, loc='upper right')
    fig.tight_layout()
    out = HERE / 'figures/quarterly_spreads.png'
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, metadata={'Software': None})
    print(out)


if __name__ == '__main__':
    main()
