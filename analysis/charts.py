"""Chart generators for house price analysis."""

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns

logger = logging.getLogger(__name__)

sns.set_theme(style="whitegrid", palette="muted")
COLOR_ACCENT = "#E8623A"


def _save_or_show(fig: plt.Figure, output: str | None, return_fig: bool = False) -> "plt.Figure | None":
    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output, dpi=150, bbox_inches="tight")
        print(f"Chart saved to {output}")
        plt.close(fig)
        return None
    elif return_fig:
        return fig
    else:
        plt.show()
        plt.close(fig)
        return None


def chart_neighborhoods(df_snap: pd.DataFrame, output: str | None = None, return_fig: bool = False) -> "plt.Figure | None":
    """Bar chart: latest median price per m² by neighborhood, sorted descending."""
    latest = (
        df_snap.sort_values("snapshot_month")
        .groupby("neighborhood")[["median_price_per_m2", "distance_to_station_km"]]
        .last()
        .sort_values("median_price_per_m2", ascending=True)
        .dropna(subset=["median_price_per_m2"])
    )

    if latest.empty:
        logger.warning("No snapshot data to chart.")
        return

    fig, ax = plt.subplots(figsize=(10, max(5, len(latest) * 0.55)))
    bars = ax.barh(latest.index, latest["median_price_per_m2"], color=COLOR_ACCENT, alpha=0.85)

    city_median = latest["median_price_per_m2"].median()
    ax.axvline(city_median, color="steelblue", linestyle="--", linewidth=1.5, label=f"City median: €{city_median:,.0f}")

    ax.bar_label(bars, fmt="€{:,.0f}", padding=4, fontsize=9)
    ax.set_xlabel("Median price per m² (€)")
    ax.set_title("Utrecht — Median House Price per m² by Neighborhood")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"€{x:,.0f}"))
    ax.legend()
    fig.tight_layout()
    return _save_or_show(fig, output, return_fig)


def chart_trends(df_snap: pd.DataFrame, output: str | None = None, return_fig: bool = False) -> "plt.Figure | None":
    """Line chart: median price per m² over time per neighborhood."""
    df = df_snap.dropna(subset=["median_price_per_m2", "snapshot_month"]).copy()
    df["snapshot_month"] = pd.to_datetime(df["snapshot_month"])

    if df.empty:
        logger.warning("No trend data to chart.")
        return

    neighborhoods = df.groupby("neighborhood")["snapshot_month"].count()
    top = neighborhoods[neighborhoods >= 2].index

    fig, ax = plt.subplots(figsize=(12, 6))
    for nbhd in sorted(top):
        grp = df[df["neighborhood"] == nbhd].sort_values("snapshot_month")
        ax.plot(grp["snapshot_month"], grp["median_price_per_m2"], marker="o", markersize=4, label=nbhd)

    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"€{x:,.0f}"))
    ax.set_xlabel("Month")
    ax.set_ylabel("Median price per m² (€)")
    ax.set_title("Utrecht — Price per m² Trend by Neighborhood")
    ax.legend(loc="upper left", fontsize=8, ncol=2)
    fig.autofmt_xdate()
    fig.tight_layout()
    return _save_or_show(fig, output, return_fig)


def chart_opportunities(df_scores: pd.DataFrame, output: str | None = None, return_fig: bool = False) -> "plt.Figure | None":
    """
    Scatter plot: undervaluation vs momentum.
    Bubble size = liquidity. Color = flip score.
    Annotations label each neighborhood.
    """
    if df_scores.empty:
        logger.warning("No score data to chart — run `analyze scores` first.")
        return

    df = df_scores.dropna(subset=["undervaluation", "momentum", "liquidity", "flip_score"])

    fig, ax = plt.subplots(figsize=(11, 8))
    scatter = ax.scatter(
        df["undervaluation"],
        df["momentum"],
        s=df["liquidity"] * 8 + 50,
        c=df["flip_score"],
        cmap="RdYlGn",
        alpha=0.85,
        edgecolors="white",
        linewidths=0.5,
    )
    plt.colorbar(scatter, ax=ax, label="Flip Score (0–100)")

    for _, row in df.iterrows():
        ax.annotate(
            row["neighborhood"],
            (row["undervaluation"], row["momentum"]),
            fontsize=8,
            ha="center",
            va="bottom",
            xytext=(0, 6),
            textcoords="offset points",
        )

    ax.set_xlabel("Undervaluation score (higher = cheaper vs city median)")
    ax.set_ylabel("Momentum score (higher = prices rising faster)")
    ax.set_title("Utrecht — Flip Opportunity Map\n(bubble size = liquidity)")
    ax.axhline(50, color="gray", linestyle=":", linewidth=0.8)
    ax.axvline(50, color="gray", linestyle=":", linewidth=0.8)
    fig.tight_layout()
    return _save_or_show(fig, output, return_fig)


def chart_price_vs_size(df_listings: pd.DataFrame, output: str | None = None, return_fig: bool = False) -> "plt.Figure | None":
    """Scatter plot: individual house price vs living space (m²)."""
    df = df_listings.dropna(subset=["price", "size_m2"]).copy()
    df = df[(df["price"] > 0) & (df["size_m2"] > 0)]

    if df.empty:
        logger.warning("No listings with both price and size_m2 data.")
        return

    fig, ax = plt.subplots(figsize=(11, 7))
    ax.scatter(
        df["size_m2"],
        df["price"],
        alpha=0.45,
        s=18,
        color=COLOR_ACCENT,
        edgecolors="none",
    )

    if len(df) >= 3:
        z = np.polyfit(df["size_m2"], df["price"], 1)
        p = np.poly1d(z)
        x_line = np.linspace(df["size_m2"].min(), df["size_m2"].max(), 200)
        ax.plot(x_line, p(x_line), color="steelblue", linestyle="--", linewidth=1.5, label="Trend")
        ax.legend()

    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"€{v:,.0f}"))
    ax.set_xlabel("Living space (m²)")
    ax.set_ylabel("House price (€)")
    ax.set_title(f"Price vs Living Space — {len(df):,} listings")
    fig.tight_layout()
    return _save_or_show(fig, output, return_fig)


def chart_proximity(df_snap: pd.DataFrame, df_scores: pd.DataFrame | None = None, output: str | None = None, return_fig: bool = False) -> "plt.Figure | None":
    """
    Scatter: price per m² vs walking distance to Utrecht Centraal.
    Bubble size = active listings (volume). Color = flip score if available.
    """
    latest = (
        df_snap.sort_values("snapshot_month")
        .groupby("neighborhood")[["median_price_per_m2", "distance_to_station_km", "active_listings"]]
        .last()
        .dropna(subset=["median_price_per_m2", "distance_to_station_km"])
    )

    if latest.empty:
        logger.warning("No proximity data to chart.")
        return

    if df_scores is not None and not df_scores.empty:
        score_map = df_scores.set_index("neighborhood")["flip_score"]
        latest["flip_score"] = latest.index.map(score_map)
    else:
        latest["flip_score"] = 50.0

    latest["active_listings"] = latest["active_listings"].fillna(10)

    fig, ax = plt.subplots(figsize=(11, 7))
    scatter = ax.scatter(
        latest["distance_to_station_km"],
        latest["median_price_per_m2"],
        s=latest["active_listings"] * 15 + 40,
        c=latest["flip_score"],
        cmap="RdYlGn",
        alpha=0.85,
        edgecolors="white",
        linewidths=0.5,
    )
    plt.colorbar(scatter, ax=ax, label="Flip Score")

    for nbhd, row in latest.iterrows():
        ax.annotate(
            nbhd,
            (row["distance_to_station_km"], row["median_price_per_m2"]),
            fontsize=8,
            ha="center",
            va="bottom",
            xytext=(0, 7),
            textcoords="offset points",
        )

    # Trendline
    x = latest["distance_to_station_km"].values
    y = latest["median_price_per_m2"].values
    if len(x) >= 3:
        z = np.polyfit(x, y, 1)
        p = np.poly1d(z)
        x_line = np.linspace(x.min(), x.max(), 100)
        ax.plot(x_line, p(x_line), "steelblue", linestyle="--", linewidth=1.5, label="Trend")
        ax.legend()

    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"€{v:,.0f}"))
    ax.set_xlabel("Walking distance to Utrecht Centraal (km)")
    ax.set_ylabel("Median price per m² (€)")
    ax.set_title(
        "Utrecht — Price per m² vs Distance to Station\n"
        "(bubble size = active listings; color = flip score)\n"
        "Neighborhoods BELOW the trend line are undervalued for their location"
    )
    fig.tight_layout()
    return _save_or_show(fig, output, return_fig)
