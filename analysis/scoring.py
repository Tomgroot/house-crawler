import logging

import numpy as np
import pandas as pd
from scipy import stats

from analysis.loader import load_listings, load_snapshots

logger = logging.getLogger(__name__)

MIN_SNAPSHOTS = 3
MIN_LISTINGS = 5


def _percentile_rank(series: pd.Series) -> pd.Series:
    """Normalize a Series to [0, 100] via percentile rank."""
    return series.rank(pct=True) * 100


def _undervaluation_score(df_snap: pd.DataFrame, city_median: float) -> pd.Series:
    """Score based on how far below city median the neighborhood's median price/m² is."""
    latest = (
        df_snap.sort_values("snapshot_month")
        .groupby("neighborhood")["median_price_per_m2"]
        .last()
    )
    score = (1 - latest / city_median).clip(lower=0) * 100
    return score.clip(upper=100)


def _momentum_score(df_snap: pd.DataFrame) -> pd.Series:
    """Score based on linear regression slope of median_price_per_m2 over last 6 months."""
    slopes = {}
    for nbhd, grp in df_snap.groupby("neighborhood"):
        recent = grp.nlargest(6, "snapshot_month").sort_values("snapshot_month")
        valid = recent.dropna(subset=["median_price_per_m2"])
        if len(valid) < 2:
            slopes[nbhd] = np.nan
            continue
        x = np.arange(len(valid), dtype=float)
        result = stats.linregress(x, valid["median_price_per_m2"].values)
        slopes[nbhd] = result.slope
    slope_series = pd.Series(slopes)
    return _percentile_rank(slope_series.fillna(slope_series.median()))


def _liquidity_score(df_snap: pd.DataFrame) -> pd.Series:
    """Score: neighborhoods that sell faster than city average get higher scores."""
    latest = (
        df_snap.sort_values("snapshot_month")
        .groupby("neighborhood")["avg_days_on_market"]
        .last()
    )
    city_avg_dom = latest.mean()
    if city_avg_dom == 0:
        return pd.Series(50.0, index=latest.index)
    score = (city_avg_dom / latest).clip(upper=2) * 50  # cap at 100
    return score.clip(lower=0, upper=100)


def _price_spread_score(df_listings: pd.DataFrame) -> pd.Series:
    """Score based on IQR of price_per_m2 within neighborhood — high spread = more deals."""
    iqrs = {}
    for nbhd, grp in df_listings.groupby("neighborhood"):
        vals = grp["price_per_m2"].dropna()
        if len(vals) < MIN_LISTINGS:
            iqrs[nbhd] = np.nan
        else:
            iqrs[nbhd] = float(np.percentile(vals, 75) - np.percentile(vals, 25))
    s = pd.Series(iqrs)
    return _percentile_rank(s.fillna(s.median()))


def compute_scores() -> pd.DataFrame:
    """
    Compute the flip potential score for every neighborhood with sufficient data.

    Returns a ranked DataFrame with columns:
        neighborhood, undervaluation, momentum, liquidity, spread, flip_score, rank,
        latest_median_price_per_m2, city_median, avg_dom, snapshot_count, distance_to_station_km
    """
    df_snap = load_snapshots()
    df_listings = load_listings()

    if df_snap.empty:
        logger.warning("No snapshot data found — run `analyze snapshots` first.")
        return pd.DataFrame()

    # Filter to neighborhoods with enough data
    snap_counts = df_snap.groupby("neighborhood")["snapshot_month"].count()
    eligible = snap_counts[snap_counts >= MIN_SNAPSHOTS].index
    df_snap = df_snap[df_snap["neighborhood"].isin(eligible)]

    if df_snap.empty:
        logger.warning("No neighborhoods have %d+ monthly snapshots yet.", MIN_SNAPSHOTS)
        return pd.DataFrame()

    city_median = df_snap.groupby("snapshot_month")["median_price_per_m2"].median().iloc[-1]
    if pd.isna(city_median) or city_median == 0:
        logger.error("Cannot compute city median price — insufficient data.")
        return pd.DataFrame()

    u = _undervaluation_score(df_snap, city_median)
    m = _momentum_score(df_snap)
    l = _liquidity_score(df_snap)
    s = _price_spread_score(df_listings[df_listings["neighborhood"].isin(eligible)])

    all_nbhds = u.index.union(m.index).union(l.index).union(s.index)
    u = u.reindex(all_nbhds).fillna(0)
    m = m.reindex(all_nbhds).fillna(50)
    l = l.reindex(all_nbhds).fillna(50)
    s = s.reindex(all_nbhds).fillna(50)

    flip_score = (0.35 * u + 0.30 * m + 0.20 * l + 0.15 * s).round(1)

    latest = (
        df_snap.sort_values("snapshot_month")
        .groupby("neighborhood")
        .last()
        .reindex(all_nbhds)
    )

    dist = df_snap.groupby("neighborhood")["distance_to_station_km"].first().reindex(all_nbhds)

    result = pd.DataFrame(
        {
            "neighborhood": all_nbhds,
            "undervaluation": u.round(1),
            "momentum": m.round(1),
            "liquidity": l.round(1),
            "spread": s.round(1),
            "flip_score": flip_score,
            "latest_median_price_per_m2": latest["median_price_per_m2"].round(0),
            "city_median": city_median,
            "avg_dom": latest["avg_days_on_market"].round(1),
            "snapshot_count": snap_counts.reindex(all_nbhds),
            "distance_to_station_km": dist,
        }
    )

    result = result.sort_values("flip_score", ascending=False).reset_index(drop=True)
    result.insert(0, "rank", range(1, len(result) + 1))
    return result
