from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RESULTS_DIR = Path(os.environ.get("DOT11_RESULTS_DIR", "results"))


def _default(obj: Any) -> Any:
    if is_dataclass(obj):
        return asdict(obj)
    raise TypeError(f"Not serializable: {type(obj)}")


def record(name: str, data: dict[str, Any]) -> Path:
    """Persist a test result as JSON under results/<timestamp>_<name>.json."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe = name.replace("/", "_").replace(" ", "_")
    path = RESULTS_DIR / f"{ts}_{safe}.json"
    payload = {"timestamp": ts, "name": name, **data}
    with path.open("w") as f:
        json.dump(payload, f, indent=2, default=_default)
    return path
