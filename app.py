"""Streamlit dashboard for house-crawler — run with: streamlit run app.py"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent

st.set_page_config(
    page_title="House Crawler",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

st.sidebar.title("🏠 House Crawler")
st.sidebar.caption("Utrecht house price tracker")

page = st.sidebar.radio(
    "Navigate",
    ["Dashboard", "Neighborhoods", "Trends", "Opportunities", "Proximity", "Listings"],
    label_visibility="collapsed",
)

st.sidebar.divider()
st.sidebar.caption("Data")

if st.sidebar.button("🔄 Refresh data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()


# ---------------------------------------------------------------------------
# Cached data loaders
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def get_snapshots() -> pd.DataFrame:
    from analysis.loader import load_snapshots
    return load_snapshots()


@st.cache_data(ttl=300)
def get_scores() -> pd.DataFrame:
    from analysis.scoring import compute_scores
    return compute_scores()


@st.cache_data(ttl=300)
def get_listings(status: str, neighborhood: str | None) -> pd.DataFrame:
    from analysis.loader import load_listings
    return load_listings(
        status=None if status == "All" else status.lower().replace(" ", "_"),
        neighborhood=None if neighborhood == "All" else neighborhood,
    )


@st.cache_data(ttl=60)
def get_db_stats() -> dict:
    from db.engine import get_engine
    from sqlalchemy import text

    engine = get_engine()
    tables = ["neighborhoods", "listings", "price_history", "neighborhood_snapshots", "crawl_runs"]
    stats = {}
    with engine.connect() as conn:
        for t in tables:
            stats[t] = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
    return stats


@st.cache_data(ttl=60)
def get_crawl_history() -> pd.DataFrame:
    from db.engine import SessionLocal
    from db.models import CrawlRun

    session = SessionLocal()
    try:
        runs = session.query(CrawlRun).order_by(CrawlRun.started_at.desc()).all()
        if not runs:
            return pd.DataFrame()
        rows = []
        for r in runs:
            duration = None
            if r.finished_at and r.started_at:
                secs = int((r.finished_at - r.started_at).total_seconds())
                duration = f"{secs // 60}m {secs % 60}s"
            rows.append({
                "Started": r.started_at,
                "Spider": r.spider_name or "—",
                "Status": r.status,
                "New": r.listings_new,
                "Updated": r.listings_updated,
                "Found": r.listings_found,
                "Max pages": r.max_pages,
                "Duration": duration or "—",
                "Errors": r.errors,
            })
        return pd.DataFrame(rows)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

if page == "Dashboard":
    st.title("Dashboard")

    try:
        stats = get_db_stats()
        history = get_crawl_history()
    except Exception as e:
        st.error(f"Database error: {e}\n\nRun `house-crawler db init` first.")
        st.stop()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Neighborhoods", stats.get("neighborhoods", 0))
    col2.metric("Listings", f"{stats.get('listings', 0):,}")
    col3.metric("Snapshots", f"{stats.get('neighborhood_snapshots', 0):,}")
    col4.metric("Crawl runs", stats.get("crawl_runs", 0))

    st.divider()
    st.subheader("Crawl history")
    st.caption("Crawls run automatically every Sunday at 02:00 UTC.")

    if history.empty:
        st.info("No crawls run yet. The first crawl will run automatically on Sunday at 02:00 UTC.")
    else:
        status_icons = {"completed": "✅", "running": "⏳", "failed": "❌"}
        history["Status"] = history["Status"].map(lambda s: f"{status_icons.get(s, '❓')} {s}")
        st.dataframe(
            history,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Started": st.column_config.DatetimeColumn("Started (UTC)", format="YYYY-MM-DD HH:mm"),
                "New": st.column_config.NumberColumn("New listings"),
                "Updated": st.column_config.NumberColumn("Updated"),
                "Found": st.column_config.NumberColumn("Total found"),
                "Max pages": st.column_config.NumberColumn("Pages crawled"),
            },
        )


# ---------------------------------------------------------------------------
# Neighborhoods chart
# ---------------------------------------------------------------------------

elif page == "Neighborhoods":
    st.title("Neighborhoods — Median price per m²")

    df = get_snapshots()
    if df.empty:
        st.warning("No snapshot data yet. Snapshots are computed automatically after each weekly crawl.")
        st.stop()

    from analysis.charts import chart_neighborhoods
    fig = chart_neighborhoods(df, return_fig=True)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)


# ---------------------------------------------------------------------------
# Trends chart
# ---------------------------------------------------------------------------

elif page == "Trends":
    st.title("Price trends over time")

    df = get_snapshots()
    if df.empty:
        st.warning("No snapshot data yet. Snapshots are computed automatically after each weekly crawl.")
        st.stop()

    neighborhoods = sorted(df["neighborhood"].dropna().unique().tolist())
    selected = st.multiselect(
        "Filter neighborhoods (leave empty for all)",
        options=neighborhoods,
        default=[],
    )
    if selected:
        df = df[df["neighborhood"].isin(selected)]

    from analysis.charts import chart_trends
    fig = chart_trends(df, return_fig=True)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)


# ---------------------------------------------------------------------------
# Opportunities chart
# ---------------------------------------------------------------------------

elif page == "Opportunities":
    st.title("Flip opportunity map")
    st.caption("Undervaluation vs price momentum. Bubble size = liquidity. Color = flip score.")

    df = get_scores()
    if df.empty:
        st.warning("Not enough data. Need 3+ monthly snapshots per neighborhood.")
        st.stop()

    from analysis.charts import chart_opportunities
    fig = chart_opportunities(df, return_fig=True)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

    st.divider()
    st.subheader("Score table")
    display_cols = ["rank", "neighborhood", "flip_score", "undervaluation", "momentum", "liquidity", "spread", "latest_median_price_per_m2", "distance_to_station_km"]
    available = [c for c in display_cols if c in df.columns]
    st.dataframe(
        df[available].style.background_gradient(subset=["flip_score"], cmap="RdYlGn"),
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------------------------
# Proximity chart
# ---------------------------------------------------------------------------

elif page == "Proximity":
    st.title("Price vs distance to Utrecht Centraal")
    st.caption("Neighborhoods below the trend line are undervalued for their location.")

    df_snap = get_snapshots()
    if df_snap.empty:
        st.warning("No snapshot data yet.")
        st.stop()

    df_scores = get_scores()

    from analysis.charts import chart_proximity
    fig = chart_proximity(df_snap, df_scores if not df_scores.empty else None, return_fig=True)
    if fig:
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)


# ---------------------------------------------------------------------------
# Listings browser
# ---------------------------------------------------------------------------

elif page == "Listings":
    st.title("Listings browser")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        status_filter = st.selectbox("Status", ["For Sale", "Sold", "All"])
    with col2:
        try:
            from analysis.loader import load_neighborhoods
            nbhds_df = load_neighborhoods()
            nbhd_options = ["All"] + sorted(nbhds_df["name"].dropna().tolist())
        except Exception:
            nbhd_options = ["All"]
        neighborhood_filter = st.selectbox("Neighborhood", nbhd_options)
    with col3:
        sort_by = st.selectbox("Sort by", ["last_seen_at", "price", "price_per_m2", "listing_date"])

    try:
        df = get_listings(status_filter, neighborhood_filter)
    except Exception as e:
        st.error(f"Failed to load listings: {e}")
        st.stop()

    if df.empty:
        st.info("No listings match the selected filters.")
        st.stop()

    # Price range filter
    price_col = df["price"].dropna()
    if not price_col.empty:
        price_min, price_max = int(price_col.min()), int(price_col.max())
        if price_min < price_max:
            low, high = st.slider(
                "Price range (€)",
                min_value=price_min,
                max_value=price_max,
                value=(price_min, price_max),
                step=5_000,
                format="€%d",
            )
            df = df[(df["price"].isna()) | ((df["price"] >= low) & (df["price"] <= high))]

    # Sort
    if sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=False)

    st.caption(f"{len(df):,} listing(s)")

    display_cols = [
        "address", "neighborhood", "status", "price", "price_per_m2",
        "size_m2", "num_rooms", "build_year", "energy_label",
        "listing_date", "sold_date", "distance_to_station_km", "url",
    ]
    available = [c for c in display_cols if c in df.columns]

    column_config = {
        "price": st.column_config.NumberColumn("Price (€)", format="€%d"),
        "price_per_m2": st.column_config.NumberColumn("€/m²", format="€%.0f"),
        "size_m2": st.column_config.NumberColumn("m²", format="%.0f m²"),
        "distance_to_station_km": st.column_config.NumberColumn("Station (km)", format="%.1f km"),
        "url": st.column_config.LinkColumn("Link", display_text="View →"),
    }

    st.dataframe(
        df[available],
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
        height=600,
    )
