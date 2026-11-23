"""Private on-disk storage for the latest local prompt QA report."""

from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4


def report_path() -> Path:
    state_root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return state_root / "multi_modal" / "prompt-qa" / "latest.json"


def report_archive_dir() -> Path:
    return report_path().parent / "runs"


def ensure_report_archive_dir() -> Path:
    directory = report_archive_dir()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    return directory


def list_reports(path: Path | None = None) -> list[Path]:
    directory = (path or report_path()).parent / "runs"
    if not directory.is_dir():
        return []
    return sorted(directory.glob("*.json"), reverse=True)


def _write_private_json(target: Path, report: dict) -> None:
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(target.parent, 0o700)
    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(target)
        os.chmod(target, 0o600)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def save_report(report: dict, path: Path | None = None) -> Path:
    target = path or report_path()
    archive_dir = target.parent / "runs"
    started_at = report.get("started_at") if isinstance(report, dict) else None
    try:
        stamp = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        stamp = stamp.astimezone(timezone.utc)
    except (TypeError, ValueError):
        stamp = datetime.now(timezone.utc)
    archive = archive_dir / f"{stamp.strftime('%Y%m%dT%H%M%S.%fZ')}-{uuid4().hex[:8]}.json"
    _write_private_json(archive, report)
    _write_private_json(target, report)
    return target


def load_report(path: Path | None = None) -> str:
    target = path or report_path()
    contents = target.read_text(encoding="utf-8")
    json.loads(contents)
    return contents
