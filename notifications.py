import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def _state_path() -> Path:
    """Derive notification state file path from DATABASE_URL."""
    db_url = os.getenv("DATABASE_URL", "sqlite:///./house_crawler.db")
    for prefix in ("sqlite:////", "sqlite:///"):
        if db_url.startswith(prefix):
            db_file = Path(db_url[len(prefix):])
            return db_file.parent / "notification_state.json"
    return Path("notification_state.json")


def get_last_notified_at() -> datetime | None:
    """Return the timestamp of the last successful notification run, or None."""
    path = _state_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        raw = data.get("last_notified_at")
        if raw:
            return datetime.fromisoformat(raw)
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def save_last_notified_at(dt: datetime) -> None:
    path = _state_path()
    data: dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            pass
    data["last_notified_at"] = dt.isoformat()
    path.write_text(json.dumps(data, indent=2))


def send_webhook(deal: dict) -> bool:
    """POST deal info to the Home Assistant webhook. Returns True on success."""
    url = os.getenv("HA_WEBHOOK_URL", "").strip()
    if not url:
        logger.debug("HA_WEBHOOK_URL not set — skipping notification")
        return False

    payload = json.dumps({k: v for k, v in deal.items() if v is not None}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
    except urllib.error.HTTPError as e:
        logger.error("Webhook HTTP %s for %s: %s", e.code, deal.get("address"), e.reason)
        return False
    except (urllib.error.URLError, OSError) as e:
        logger.error("Webhook request failed for %s: %s", deal.get("address"), e)
        return False

    if status < 300:
        logger.info(
            "Notified HA: %s — %.1f%% below comparable median",
            deal.get("address"),
            deal.get("discount_pct", 0),
        )
        return True

    logger.error("Webhook returned status %d for %s", status, deal.get("address"))
    return False


def notify_deals(deals: list[dict]) -> int:
    """Send webhook for each deal. Returns number of successful notifications."""
    if not deals:
        return 0
    sent = sum(1 for deal in deals if send_webhook(deal))
    return sent


def run_notify(
    deal_threshold: float,
    min_size_m2: float,
    since_dt=None,
    dry_run: bool = False,
) -> tuple[int, int]:
    """
    Find deals and notify. Returns (deals_found, notifications_sent).

    If since_dt is None, uses last_notified_at from state file.
    """
    from analysis.deal_score import find_deals

    if since_dt is None:
        since_dt = get_last_notified_at()

    deals = find_deals(since_dt=since_dt, deal_threshold=deal_threshold, min_size_m2=min_size_m2)

    if dry_run:
        return len(deals), 0

    sent = notify_deals(deals)
    if not dry_run:
        save_last_notified_at(datetime.now(tz=timezone.utc))

    return len(deals), sent
