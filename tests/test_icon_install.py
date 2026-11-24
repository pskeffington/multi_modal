"""The two desktop launchers install visible, named SVG icons."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICON_ROOT = ROOT / "data/icons/hicolor/scalable/apps"


class DesktopIconInstallTests(unittest.TestCase):
    def test_icon_assets_are_well_formed_svg(self) -> None:
        for name in ("multi-modal-router", "multi-modal-gpu-optimizer"):
            with self.subTest(name=name):
                root = ET.parse(ICON_ROOT / f"{name}.svg").getroot()
                self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
                self.assertEqual(root.attrib.get("viewBox"), "0 0 128 128")

    def test_installers_copy_the_matching_icon_and_desktop_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            data = Path(tmp) / "data"
            env = dict(os.environ, HOME=str(home), XDG_DATA_HOME=str(data),
                       XDG_BIN_HOME=str(Path(tmp) / "bin"),
                       XDG_CONFIG_HOME=str(Path(tmp) / "config"),
                       XDG_CACHE_HOME=str(Path(tmp) / "cache"))
            subprocess.run(["sh", str(ROOT / "scripts/install-user.sh")],
                           check=True, env=env, capture_output=True, text=True)
            subprocess.run(["sh", str(ROOT / "scripts/install-gpu-optimizer.sh")],
                           check=True, env=env, capture_output=True, text=True)
            for name in ("multi-modal-router", "multi-modal-gpu-optimizer"):
                with self.subTest(name=name):
                    icon = data / "icons/hicolor/scalable/apps" / f"{name}.svg"
                    self.assertTrue(icon.is_file())
                    self.assertEqual(icon.read_bytes(), (ICON_ROOT / f"{name}.svg").read_bytes())
            launchers = list(data.rglob("*.desktop")) + list(home.rglob("*.desktop"))
            self.assertTrue(any("Icon=multi-modal-router" in path.read_text() for path in launchers))
            self.assertTrue(any("Icon=multi-modal-gpu-optimizer" in path.read_text() for path in launchers))


if __name__ == "__main__":
    unittest.main()
