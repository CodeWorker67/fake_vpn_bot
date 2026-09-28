import os
from typing import Set

from dotenv import load_dotenv

load_dotenv()


def _parse_id_set(raw: str | None) -> Set[int]:
    if not raw:
        return set()
    return {int(part.strip()) for part in raw.split(",") if part.strip()}


ADMIN_IDS: Set[int] = _parse_id_set(os.environ.get("ADMIN_IDS"))
DB_PATH: str = os.environ.get("DB_PATH", "db.sqlite3")

_checker_raw = os.environ.get("CHECKER_ID")
CHECKER_ID: int | None = int(_checker_raw) if _checker_raw and _checker_raw.strip() else None
