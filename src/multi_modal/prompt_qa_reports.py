"""Private on-disk storage for the latest local prompt QA report."""

from __future__ import annotations

import json
import os
from pathlib import Path


def report_path() -> Path:
    state_root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    return state_root / "multi_modal" / "prompt-qa" / "latest.json"


def save_report(report: dict, path: Path | None = None) -> Path:
    target = path or report_path()
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
    return target


def load_report(path: Path | None = None) -> str:
    target = path or report_path()
    contents = target.read_text(encoding="utf-8")
    json.loads(contents)
    return contents
