import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import click
from sqlalchemy import text

from db.engine import SessionLocal, get_engine, init_db
from db.models import CrawlRun, Listing, Neighborhood, NeighborhoodSnapshot


@click.group()
def cli():
    """Utrecht house price crawler and flip opportunity analyzer."""


# ---------------------------------------------------------------------------
# db commands
# ---------------------------------------------------------------------------

@cli.group()
def db():
    """Database management commands."""


@db.command("init")
def db_init():
    """Create all database tables (idempotent)."""
    from config.neighborhoods import NEIGHBORHOODS

    init_db()
    click.echo("Database tables created.")

    session = SessionLocal()
    try:
        for nbhd in NEIGHBORHOODS:
            existing = session.query(Neighborhood).filter_by(name=nbhd.name).first()
            if not existing:
                session.add(
                    Neighborhood(
                        name=nbhd.name,
                        slug=nbhd.slugs[0],
                        postal_codes=json.dumps([]),
                        lat_center=nbhd.lat_center,
                        lon_center=nbhd.lon_center,
                        distance_to_station_km=nbhd.distance_to_station_km,
                    )
                )
        session.commit()
        click.echo(f"Seeded {len(NEIGHBORHOODS)} neighborhoods.")
    finally:
        session.close()


@db.command("status")
def db_status():
    """Show database row counts and last crawl run."""
    engine = get_engine()
    with engine.connect() as conn:
        tables = ["neighborhoods", "listings", "price_history", "neighborhood_snapshots", "crawl_runs"]
        click.echo("\nRow counts:")
        for table in tables:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            click.echo(f"  {table:<30} {count:>8}")

    session = SessionLocal()
    try:
        last = session.query(CrawlRun).order_by(CrawlRun.started_at.desc()).first()
        if last:
            click.echo(f"\nLast crawl: {last.spider_name} at {last.started_at} — status: {last.status}")
            click.echo(f"  Found: {last.listings_found}  New: {last.listings_new}  Updated: {last.listings_updated}  Errors: {last.errors}")
        else:
            click.echo("\nNo crawl runs yet.")
    finally:
        session.close()


# ---------------------------------------------------------------------------
# crawl commands
# ---------------------------------------------------------------------------

@cli.group()
def crawl():
    """Run Scrapy spiders to collect listings."""


def _run_spider(spider_name: str, max_pages: int, neighborhoods: str) -> None:
    cmd = [
        sys.executable, "-m", "scrapy", "crawl", spider_name,
        "-a", f"max_pages={max_pages}",
        "-a", f"neighborhoods={neighborhoods}",
        "--logfile", f"{spider_name}.log",
    ]
    click.echo(f"Running spider: {spider_name} (max_pages={max_pages})")
    result = subprocess.run(cmd, cwd=str(Path(__file__).parents[1]))
    if result.returncode != 0:
        click.echo(f"Spider {spider_name} exited with code {result.returncode}", err=True)
        sys.exit(result.returncode)
    click.echo(f"Spider {spider_name} completed.")


@crawl.command("forsale")
@click.option("--max-pages", default=20, show_default=True, help="Max search result pages per neighborhood slug.")
@click.option("--neighborhoods", default="", help="Comma-separated neighborhood names to restrict crawl.")
def crawl_forsale(max_pages: int, neighborhoods: str):
    """Scrape active for-sale listings from Funda."""
    _run_spider("funda_forsale", max_pages, neighborhoods)


@crawl.command("sold")
@click.option("--max-pages", default=10, show_default=True, help="Max pages of sold listings per slug.")
@click.option("--neighborhoods", default="", help="Comma-separated neighborhood names to restrict crawl.")
def crawl_sold(max_pages: int, neighborhoods: str):
    """Scrape recently sold listings from Funda."""
    _run_spider("funda_sold", max_pages, neighborhoods)


@crawl.command("all")
@click.option("--max-pages", default=20, show_default=True)
@click.option("--neighborhoods", default="")
def crawl_all(max_pages: int, neighborhoods: str):
    """Run both for-sale and sold spiders sequentially."""
    _run_spider("funda_forsale", max_pages, neighborhoods)
    _run_spider("funda_sold", min(max_pages, 10), neighborhoods)


# ---------------------------------------------------------------------------
# analyze commands
# ---------------------------------------------------------------------------

@cli.group()
def analyze():
    """Compute metrics and opportunity scores."""


@analyze.command("snapshots")
@click.option("--month", default=None, help="Month to compute in YYYY-MM format (default: current month).")
def analyze_snapshots(month: str | None):
    """Compute monthly neighborhood snapshots from listings."""
    from analysis.metrics import compute_all_snapshots

    target_month = None
    if month:
        target_month = date(int(month[:4]), int(month[5:7]), 1)

    count = compute_all_snapshots(target_month)
    click.echo(f"Computed {count} neighborhood snapshots.")


@analyze.command("scores")
def analyze_scores():
    """Compute and display flip opportunity scores per neighborhood."""
    from analysis.scoring import compute_scores

    df = compute_scores()
    if df.empty:
        click.echo("Not enough data to compute scores. Run more crawls and compute snapshots first.")
        return

    click.echo(f"\n{'Rank':<5} {'Neighborhood':<28} {'Score':>6} {'Underval':>9} {'Momentum':>9} {'Liquidity':>9} {'Spread':>7} {'€/m²':>8} {'km':>5}")
    click.echo("-" * 100)
    for _, row in df.iterrows():
        click.echo(
            f"{row['rank']:<5} {row['neighborhood']:<28} {row['flip_score']:>6.1f} "
            f"{row['undervaluation']:>9.1f} {row['momentum']:>9.1f} {row['liquidity']:>9.1f} "
            f"{row['spread']:>7.1f} {row['latest_median_price_per_m2']:>8,.0f} "
            f"{row['distance_to_station_km']:>5.1f}"
        )


# ---------------------------------------------------------------------------
# report commands
# ---------------------------------------------------------------------------

@cli.group()
def report():
    """Generate charts and reports."""


@report.command("neighborhoods")
@click.option("--output", default=None, help="Output file path (e.g. chart.png). Shows interactively if omitted.")
def report_neighborhoods(output: str | None):
    """Bar chart: median price per m² by neighborhood."""
    from analysis.charts import chart_neighborhoods
    from analysis.loader import load_snapshots

    df = load_snapshots()
    if df.empty:
        click.echo("No snapshot data. Run `crawl all` and `analyze snapshots` first.")
        return
    chart_neighborhoods(df, output)


@report.command("trends")
@click.option("--output", default=None, help="Output file path.")
def report_trends(output: str | None):
    """Line chart: price per m² trend over time per neighborhood."""
    from analysis.charts import chart_trends
    from analysis.loader import load_snapshots

    df = load_snapshots()
    if df.empty:
        click.echo("No snapshot data.")
        return
    chart_trends(df, output)


@report.command("opportunities")
@click.option("--output", default=None, help="Output file path.")
def report_opportunities(output: str | None):
    """Scatter plot: undervaluation vs momentum bubble chart."""
    from analysis.charts import chart_opportunities
    from analysis.scoring import compute_scores

    df = compute_scores()
    if df.empty:
        click.echo("No score data. Need 3+ months of snapshots.")
        return
    chart_opportunities(df, output)


@report.command("proximity")
@click.option("--output", default=None, help="Output file path.")
def report_proximity(output: str | None):
    """Scatter: price per m² vs walking distance to Utrecht Centraal."""
    from analysis.charts import chart_proximity
    from analysis.loader import load_snapshots
    from analysis.scoring import compute_scores

    df_snap = load_snapshots()
    if df_snap.empty:
        click.echo("No snapshot data.")
        return
    df_scores = compute_scores()
    chart_proximity(df_snap, df_scores if not df_scores.empty else None, output)
