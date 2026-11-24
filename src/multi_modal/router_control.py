"""Start and probe the user's already-configured llama router service."""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from .client import QWEN, LocalClient, LocalModelError

SERVICE = "llama-router.service"
SERVER_ENV = Path.home() / ".config/llama.cpp/server.env"
MODELS_PRESET = Path.home() / ".config/llama.cpp/models.ini"
FALLBACK_MODELS_DIR = Path.home() / ".local/share/llama.cpp/models"
MODELS_DIR_KEY = "LLAMA_MODELS_DIR"


class RouterControlError(RuntimeError):
    pass


def _repair_missing_models_dir() -> bool:
    """Point the user service at the existing user-owned model store if stale.

    Only the LLAMA_MODELS_DIR assignment is changed. All other lines are
    preserved verbatim, and no model files are downloaded or removed.
    """
    if (FALLBACK_MODELS_DIR.is_symlink() or not FALLBACK_MODELS_DIR.is_dir()
            or not os.access(FALLBACK_MODELS_DIR, os.W_OK)):
        raise RouterControlError(
            f"Router repair needs a writable model directory at {FALLBACK_MODELS_DIR}; "
            "create or select one before starting the router."
        )

    try:
        if SERVER_ENV.is_symlink():
            raise RouterControlError(f"Router repair will not modify symlinked settings: {SERVER_ENV}")
        original = SERVER_ENV.read_text(encoding="utf-8") if SERVER_ENV.exists() else ""
    except OSError as exc:
        raise RouterControlError(f"Could not inspect router settings at {SERVER_ENV}: {exc}") from exc

    current = None
    for line in original.splitlines():
        if line.startswith(f"{MODELS_DIR_KEY}="):
            current = line.split("=", 1)[1].strip().strip("\"")
    if current and Path(current).is_dir():
        return False

    replacement = f"{MODELS_DIR_KEY}={FALLBACK_MODELS_DIR}\n"
    lines = original.splitlines(keepends=True)
    updated: list[str] = []
    inserted = False
    for line in lines:
        if line.startswith(f"{MODELS_DIR_KEY}="):
            if not inserted:
                previous_value = line.split("=", 1)[1].strip()
                if previous_value:
                    updated.append(f"# Multi Modal repair replaced {MODELS_DIR_KEY}={previous_value}\n")
                updated.append(replacement)
                inserted = True
            continue
        updated.append(line)
    if not inserted:
        if updated and not updated[-1].endswith(("\n", "\r")):
            updated.append("\n")
        updated.append(replacement)
    content = "".join(updated)

    try:
        SERVER_ENV.parent.mkdir(parents=True, exist_ok=True)
        mode = SERVER_ENV.stat().st_mode & 0o777 if SERVER_ENV.exists() else 0o600
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=SERVER_ENV.parent,
            prefix=f".{SERVER_ENV.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temp_path = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_path, mode)
        os.replace(temp_path, SERVER_ENV)
    except OSError as exc:
        try:
            temp_path.unlink(missing_ok=True)
        except (OSError, UnboundLocalError):
            pass
        raise RouterControlError(f"Could not repair the model-directory setting: {exc}") from exc
    return True


def _repair_qwen_gpu_fit() -> bool:
    """Set Qwen to llama.cpp's memory-adaptive GPU layer offload profile."""
    try:
        if MODELS_PRESET.is_symlink():
            raise RouterControlError(f"Router repair will not modify symlinked presets: {MODELS_PRESET}")
        original = MODELS_PRESET.read_text(encoding="utf-8")
    except OSError as exc:
        raise RouterControlError(f"Could not inspect llama.cpp model presets at {MODELS_PRESET}: {exc}") from exc

    lines = original.splitlines(keepends=True)
    section_header = f"[{QWEN}]"
    section_start = next((i for i, line in enumerate(lines) if line.strip() == section_header), None)
    if section_start is None:
        raise RouterControlError(f"Qwen preset [{QWEN}] is missing from {MODELS_PRESET}; GPU settings were not changed.")
    section_end = next((i for i in range(section_start + 1, len(lines))
                        if lines[i].lstrip().startswith("[")), len(lines))

    desired = {"n-gpu-layers": "auto", "fit": "on"}
    found: set[str] = set()
    changed_lines: list[str] = []
    changed = False
    for line in lines[section_start + 1:section_end]:
        stripped = line.strip()
        key, separator, value = stripped.partition("=")
        key = key.strip()
        if separator and key in desired:
            found.add(key)
            new_value = desired[key]
            if value.strip().strip('"') != new_value:
                changed_lines.append(f"# Multi Modal repair replaced {key}={value.strip()}\n")
                changed_lines.append(f"{key} = {new_value}\n")
                changed = True
                continue
        changed_lines.append(line)
    if changed_lines and not changed_lines[-1].endswith(("\n", "\r")):
        changed_lines[-1] += "\n"
    for key, value in desired.items():
        if key not in found:
            changed_lines.append(f"{key} = {value}\n")
            changed = True

    if not changed:
        return False
    updated = "".join(lines[:section_start + 1] + changed_lines + lines[section_end:])
    try:
        mode = MODELS_PRESET.stat().st_mode & 0o777
        temp_path: Path | None = None
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=MODELS_PRESET.parent,
            prefix=f".{MODELS_PRESET.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temp_path = Path(stream.name)
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_path, mode)
        os.replace(temp_path, MODELS_PRESET)
    except OSError as exc:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise RouterControlError(f"Could not repair Qwen GPU offload settings: {exc}") from exc
    return True


def start_user_router(*, ready_timeout: float = 30.0,
                      client_factory: Callable[[], LocalClient] = LocalClient,
                      run: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> tuple[list[dict[str, str]], bool]:
    """Use the desktop user's systemd bus and wait for the loopback API.

    Returns (catalog, started_here). If the configured model directory is
    stale, repair only that setting to the existing user-owned model store.
    This deliberately starts only the preconfigured user service; it never
    invokes a shell or uses sudo.
    """
    client = client_factory()
    try:
        return client.model_catalog(), False
    except (LocalModelError, ValueError):
        pass

    _repair_missing_models_dir()
    _repair_qwen_gpu_fit()

    try:
        result = run(["systemctl", "--user", "restart", SERVICE],
                     capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RouterControlError(f"Could not start {SERVICE} from this desktop session: {exc}") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout or "systemctl returned an error").strip()
        raise RouterControlError(f"Could not start {SERVICE}: {detail}")

    deadline = time.monotonic() + max(0.0, ready_timeout)
    last_error = "router has not advertised models yet"
    while True:
        try:
            return client.model_catalog(), True
        except (LocalModelError, ValueError) as exc:
            last_error = str(exc)
        if time.monotonic() >= deadline:
            break
        time.sleep(min(0.5, max(0.0, deadline - time.monotonic())))
    raise RouterControlError(f"{SERVICE} started but the local model API did not become ready: {last_error}")
