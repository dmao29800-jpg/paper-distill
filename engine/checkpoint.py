"""Checkpoint manager for resumable processing."""

import json
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class Checkpoint:
    """Tracks per-file processing status in a JSON file."""

    def __init__(self, path: Path):
        self.path = path
        self._data: dict = {}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self._data = {}

    def save(self):
        """Atomic save via temp file + rename."""
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", delete=False,
            suffix=".json", dir=self.path.parent,
        ) as tmp:
            json.dump(self._data, tmp, ensure_ascii=False, indent=2)
        Path(tmp.name).replace(self.path)

    def is_done(self, filename: str) -> bool:
        return self._data.get(filename, {}).get("status") == "success"

    def mark(self, filename: str, status: str, sample_count: int,
             duration: float, error: str = ""):
        from datetime import datetime
        self._data[filename] = {
            "status": status,
            "sample_count": sample_count,
            "duration": round(duration, 1),
            "error": error,
            "time": datetime.now().isoformat(),
        }

    @property
    def stats(self) -> dict:
        total = len(self._data)
        success = sum(1 for v in self._data.values() if v["status"] == "success")
        failed = sum(1 for v in self._data.values() if v["status"] == "failed")
        samples = sum(v.get("sample_count", 0) for v in self._data.values())
        duration = sum(v.get("duration", 0) for v in self._data.values())
        return {
            "total": total, "success": success, "failed": failed,
            "total_samples": samples, "total_duration": duration,
        }

    def failed_files(self) -> list[tuple[str, str]]:
        return [
            (k, v.get("error", "unknown"))
            for k, v in self._data.items()
            if v["status"] == "failed"
        ]
