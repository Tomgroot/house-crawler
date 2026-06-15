import json
from pathlib import Path

_STATE_FILE = Path(__file__).parents[1] / "crawl_state.json"


def get_last_page(mode: str) -> int:
    """Return the last completed page for a given crawl mode, or 0 if unset."""
    if not _STATE_FILE.exists():
        return 0
    data = json.loads(_STATE_FILE.read_text())
    return data.get(mode, {}).get("last_page", 0)


def save_page(mode: str, page: int) -> None:
    data: dict = {}
    if _STATE_FILE.exists():
        data = json.loads(_STATE_FILE.read_text())
    data.setdefault(mode, {})["last_page"] = page
    _STATE_FILE.write_text(json.dumps(data, indent=2))


def reset_mode(mode: str) -> None:
    if not _STATE_FILE.exists():
        return
    data = json.loads(_STATE_FILE.read_text())
    if mode in data:
        data[mode]["last_page"] = 0
        _STATE_FILE.write_text(json.dumps(data, indent=2))
