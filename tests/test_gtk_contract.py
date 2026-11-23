"""GTK API contract checks that can run without a display server."""

from __future__ import annotations

import unittest

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


class GtkDialogContractTests(unittest.TestCase):
    def test_message_dialog_secondary_text_is_a_property(self) -> None:
        # Gtk.MessageDialog exposes secondary-text as a GObject property, not
        # as set_secondary_text() in the system PyGObject bindings.
        self.assertIsNotNone(Gtk.MessageDialog.find_property("secondary-text"))
        self.assertFalse(hasattr(Gtk.MessageDialog, "set_secondary_text"))


if __name__ == "__main__":
    unittest.main()
