"""Start and probe the user's already-configured llama router service."""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable

from .client import LocalClient, LocalModelError

SERVICE = "llama-router.service"


class RouterControlError(RuntimeError):
    pass


def start_user_router(*, ready_timeout: float = 30.0,
                      client_factory: Callable[[], LocalClient] = LocalClient,
                      run: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> tuple[list[dict[str, str]], bool]:
    """Use the desktop user's systemd bus and wait for the loopback API.

    Returns (catalog, started_here). This deliberately starts only the
    preconfigured user service; it never invokes a shell or uses sudo.
    """
    client = client_factory()
    try:
        return client.model_catalog(), False
    except (LocalModelError, ValueError):
        pass

    try:
        result = run(["systemctl", "--user", "start", SERVICE],
                     capture_output=True, text=True, timeout=12, check=False)
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
