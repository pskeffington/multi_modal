"""Desktop-session llama-router startup contract tests."""

from __future__ import annotations

import subprocess
import unittest
from unittest.mock import Mock

from multi_modal.client import LocalModelError
from multi_modal.router_control import RouterControlError, SERVICE, start_user_router


class RouterControlTests(unittest.TestCase):
    def test_existing_api_does_not_restart_user_service(self) -> None:
        client = Mock()
        client.model_catalog.return_value = [{"id": "qwen", "status": "available"}]
        run = Mock()
        catalog, started = start_user_router(client_factory=lambda: client, run=run)
        self.assertEqual(catalog[0]["id"], "qwen")
        self.assertFalse(started)
        run.assert_not_called()

    def test_starts_configured_user_service_then_waits_for_catalog(self) -> None:
        client = Mock()
        client.model_catalog.side_effect = [LocalModelError("offline"), [{"id": "qwen", "status": "available"}]]
        run = Mock(return_value=subprocess.CompletedProcess([], 0, "", ""))
        catalog, started = start_user_router(client_factory=lambda: client, run=run)
        self.assertTrue(started)
        self.assertEqual(catalog[0]["id"], "qwen")
        run.assert_called_once_with(["systemctl", "--user", "start", SERVICE],
                                    capture_output=True, text=True, timeout=12, check=False)

    def test_reports_missing_desktop_session_bus_without_shell_fallback(self) -> None:
        client = Mock()
        client.model_catalog.side_effect = LocalModelError("offline")
        run = Mock(side_effect=PermissionError("user bus unavailable"))
        with self.assertRaisesRegex(RouterControlError, "desktop session"):
            start_user_router(client_factory=lambda: client, run=run, ready_timeout=0)
        self.assertEqual(run.call_args.args[0], ["systemctl", "--user", "start", SERVICE])

    def test_systemd_service_error_is_reported(self) -> None:
        client = Mock()
        client.model_catalog.side_effect = LocalModelError("offline")
        run = Mock(return_value=subprocess.CompletedProcess([], 1, "", "unit not found"))
        with self.assertRaisesRegex(RouterControlError, "unit not found"):
            start_user_router(client_factory=lambda: client, run=run)


if __name__ == "__main__":
    unittest.main()
