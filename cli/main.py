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


def _run_spider(mode: str, max_pages: int) -> None:
    cmd = [
        sys.executable, "-m", "scrapy", "crawl", "funda",
        "-a", f"mode={mode}",
        "-a", f"max_pages={max_pages}",
        "--logfile", f"funda_{mode}.log",
    ]
    click.echo(f"Running spider: funda mode={mode} (max_pages={max_pages})")
    result = subprocess.run(cmd, cwd=str(Path(__file__).parents[1]))
    if result.returncode != 0:
        click.echo(f"Spider funda ({mode}) exited with code {result.returncode}", err=True)
        sys.exit(result.returncode)
    click.echo(f"Spider funda ({mode}) completed.")


@crawl.command("forsale")
@click.option("--max-pages", default=20, show_default=True, help="Max search result pages.")
def crawl_forsale(max_pages: int):
    """Scrape active for-sale listings from Funda."""
    _run_spider("for_sale", max_pages)


@crawl.command("sold")
@click.option("--max-pages", default=10, show_default=True, help="Max pages of sold listings.")
def crawl_sold(max_pages: int):
    """Scrape recently sold listings from Funda."""
    _run_spider("sold", max_pages)


@crawl.command("all")
@click.option("--max-pages", default=20, show_default=True)
def crawl_all(max_pages: int):
    """Run both for-sale and sold spiders sequentially."""
    _run_spider("for_sale", max_pages)
    _run_spider("sold", min(max_pages, 10))


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
# listings commands
# ---------------------------------------------------------------------------

@cli.group()
def listings():
    """Browse crawled listings."""


@listings.command("list")
@click.option("--status", default="for_sale", type=click.Choice(["for_sale", "sold", "all"]), show_default=True, help="Filter by listing status.")
@click.option("--neighborhood", default=None, help="Filter by neighborhood name (partial match).")
@click.option("--limit", default=50, show_default=True, help="Max rows to show.")
@click.option("--sort", default="last_seen_at", type=click.Choice(["last_seen_at", "price", "price_per_m2", "listing_date"]), show_default=True, help="Sort column.")
def listings_list(status: str, neighborhood: str | None, limit: int, sort: str):
    """List crawled listings."""
    from sqlalchemy import desc

    session = SessionLocal()
    try:
        q = session.query(Listing)
        if status != "all":
            q = q.filter(Listing.status == status)
        if neighborhood:
            nbhd = session.query(Neighborhood).filter(Neighborhood.name.ilike(f"%{neighborhood}%")).first()
            if nbhd is None:
                click.echo(f"No neighborhood matching '{neighborhood}' found.", err=True)
                return
            q = q.filter(Listing.neighborhood_id == nbhd.id)

        sort_col = {
            "last_seen_at": Listing.last_seen_at,
            "price": Listing.price,
            "price_per_m2": Listing.price_per_m2,
            "listing_date": Listing.listing_date,
        }[sort]
        q = q.order_by(desc(sort_col))
        rows = q.limit(limit).all()

        if not rows:
            click.echo("No listings found.")
            return

        nbhd_map = {n.id: n.name for n in session.query(Neighborhood).all()}

        header = f"{'Address':<35} {'Neighborhood':<22} {'Status':<8} {'Price':>10} {'€/m²':>7} {'m²':>5} {'Rooms':>5} {'Date':<12} {'URL'}"
        click.echo(header)
        click.echo("-" * len(header))
        for r in rows:
            nbhd_name = nbhd_map.get(r.neighborhood_id, "")
            price = f"€{r.price:,}" if r.price else "-"
            ppm2 = f"{r.price_per_m2:,.0f}" if r.price_per_m2 else "-"
            size = f"{r.size_m2:.0f}" if r.size_m2 else "-"
            rooms = str(r.num_rooms) if r.num_rooms else "-"
            dt = str(r.listing_date or r.sold_date or "")
            click.echo(
                f"{(r.address or ''):<35} {nbhd_name:<22} {r.status:<8} {price:>10} {ppm2:>7} {size:>5} {rooms:>5} {dt:<12} {r.url}"
            )
        click.echo(f"\n{len(rows)} listing(s) shown.")
    finally:
        session.close()


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
