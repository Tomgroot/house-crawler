# house-crawler

Scrapes Funda listings (for-sale and recently sold) across Utrecht neighborhoods, stores them in a local SQLite database, and ranks neighborhoods by flip opportunity using undervaluation, price momentum, and liquidity scores.

## Requirements

- Python 3.11+
- Playwright browsers

## Setup

```bash
python3.12 -m venv venv          # or python3.13; must be 3.11+
source venv/bin/activate

pip install --upgrade pip
pip install -e ".[dev]"
playwright install chromium

cp .env.example .env   # adjust MAX_PAGES or DATABASE_URL if needed
```

## Usage

```bash
# 1. Initialize the database and seed neighborhoods
house-crawler db init

# 2. Crawl listings
house-crawler crawl all               # for-sale + sold
house-crawler crawl forsale --max-pages 5   # active listings only
house-crawler crawl sold   --max-pages 5   # sold listings only

# 3. Compute monthly snapshots
house-crawler analyze snapshots
house-crawler analyze snapshots --month 2026-05   # specific month

# 4. Score neighborhoods
house-crawler analyze scores

# 5. Generate charts
house-crawler report neighborhoods    # median €/m² bar chart
house-crawler report trends           # price trend over time
house-crawler report opportunities    # undervaluation vs momentum bubble chart
house-crawler report proximity        # price vs distance to Utrecht Centraal
```

## Streamlit UI

```bash
streamlit run app.py
```

Opens a dashboard at `http://localhost:8501` with neighborhood scores, charts, and crawl controls.

## Database status

```bash
house-crawler db status
```

## Neighborhoods covered

Binnenstad, Lombok, Wittevrouwen/Oudwijk, Hoograven, Kanaleneiland, Overvecht, Leidsche Rijn, Vleuten-De Meern, Zuilen/Ondiep, Rivierenwijk/Dichterswijk, Tuinwijk, Abstede.
