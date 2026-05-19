"""Disk-backed JSON cache with TTL (Phase 1 -- simple file-per-key, no SQLite)."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Optional


class JsonDiskCache:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        h = hashlib.sha256(key.encode()).hexdigest()
        return self.root / f"{h}.json"

    def get(self, key: str) -> Optional[Any]:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            raw = json.loads(p.read_text())
            if raw.get("expires_at", 0) < time.time():
                return None
            return raw["value"]
        except (json.JSONDecodeError, KeyError):
            return None

    def set(self, key: str, value: Any, ttl_seconds: int = 86400) -> None:
        payload = {
            "value": value,
            "expires_at": time.time() + ttl_seconds,
        }
        self._path(key).write_text(json.dumps(payload, default=str))
