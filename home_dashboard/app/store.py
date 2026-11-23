"""Tiny JSON store in the add-on's private /data volume (never in the repo)."""
from __future__ import annotations

import json
import os
import secrets
import tempfile
from pathlib import Path

from .schema import SERVICES, default_rows, make_row


class Store:
    def __init__(self, data_dir: str | os.PathLike):
        self.dir = Path(data_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.dir / "state.json"
        self.tokens_path = self.dir / "tokens.json"
        self.state = self._load(self.state_path) or {"rows": default_rows()}
        self._ensure_all_services()
        self.tokens = self._load(self.tokens_path) or {}
        if not self.tokens.get("read") or not self.tokens.get("write"):
            self.rotate_tokens()

    # -- persistence -------------------------------------------------------
    @staticmethod
    def _load(path: Path):
        try:
            return json.loads(path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def _save(self, path: Path, data) -> None:
        fd, tmp = tempfile.mkstemp(dir=self.dir)
        with os.fdopen(fd, "w") as fh:
            json.dump(data, fh, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)

    def _ensure_all_services(self) -> None:
        have = {r["service"] for r in self.state["rows"]}
        for row in default_rows():
            if row["service"] not in have:
                self.state["rows"].append(row)
        order = list(SERVICES)
        self.state["rows"] = sorted(
            (r for r in self.state["rows"] if r["service"] in SERVICES),
            key=lambda r: order.index(r["service"]),
        )

    # -- rows ----------------------------------------------------------------
    @property
    def rows(self) -> list[dict]:
        return [dict(r) for r in self.state["rows"]]

    def put_row(self, row: dict) -> None:
        rows = [r for r in self.state["rows"] if r["service"] != row["service"]]
        rows.append(row)
        self.state["rows"] = rows
        self._ensure_all_services()
        self._save(self.state_path, self.state)

    def get_row(self, service: str) -> dict | None:
        return next((dict(r) for r in self.state["rows"] if r["service"] == service), None)

    def set_manual(self, service: str, pct_used, resets_at) -> dict:
        if SERVICES.get(service, {}).get("live"):
            raise ValueError(f"{service} is a live row")
        row = make_row(service, pct_used=pct_used, resets_at=resets_at or None, status="manual")
        self.put_row(row)
        return row

    # -- tokens ----------------------------------------------------------------
    def rotate_tokens(self) -> None:
        self.tokens = {"read": secrets.token_urlsafe(24), "write": secrets.token_urlsafe(32)}
        self._save(self.tokens_path, self.tokens)
