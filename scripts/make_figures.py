"""Redraw docs/safety_utility.png from results/evaluation*.json."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    dev = json.loads((ROOT / "results" / "evaluation.json").read_text())["results"]
    held = json.loads((ROOT / "results" / "evaluation_heldout.json").read_text())["results"]
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    for rows, marker in ((dev, "o"), (held, "s")):
        for row in rows:
            x, y = 100 * row["false_refusal_rate"], 100 * row["attack_success_rate"]
            ax.scatter(x, y, marker=marker, s=60, color="#3182bd" if marker == "o" else "#e6550d", zorder=3)
            if marker == "o":
                ax.annotate(row["defense"], (x, y), textcoords="offset points", xytext=(6, 4), fontsize=8)
    for d, h in zip(dev, held, strict=True):
        ax.annotate(
            "",
            xy=(100 * h["false_refusal_rate"], 100 * h["attack_success_rate"]),
            xytext=(100 * d["false_refusal_rate"], 100 * d["attack_success_rate"]),
            arrowprops={"arrowstyle": "->", "color": "grey", "lw": 0.8},
        )
    ax.scatter([], [], marker="o", color="#3182bd", label="development phrasing")
    ax.scatter([], [], marker="s", color="#e6550d", label="held-out phrasing")
    ax.set(
        xlabel="false refusal rate on benign requests (%)",
        ylabel="attack success rate (%)",
        title="Safety vs utility (lower-left is better)",
        xlim=(-3, 62),
        ylim=(-3, 85),
    )
    ax.legend(frameon=False, loc="upper right")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(ROOT / "docs" / "safety_utility.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
