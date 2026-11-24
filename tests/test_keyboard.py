import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.keyboard import single_key_action, is_text_input_widget, alt_shortcut_action


class DummyWidget:
    def __init__(self, cls):
        self.cls = cls
    def winfo_class(self):
        return self.cls


class KeyboardShortcutTests(unittest.TestCase):
    def test_alt_shortcuts_match_requested_navigation(self):
        self.assertEqual(alt_shortcut_action("h"), "home")
        self.assertEqual(alt_shortcut_action("1"), "help")
        self.assertEqual(alt_shortcut_action("g"), "goto")
        self.assertIsNone(alt_shortcut_action("x"))

    def test_single_letter_shortcuts_route_only_when_safe(self):
        self.assertEqual(single_key_action("r"), "payment")
        self.assertEqual(single_key_action("P"), "purchase")
        self.assertIsNone(single_key_action("r", text_input_focused=True))
        self.assertIsNone(single_key_action("x"))

    def test_text_entry_search_and_combo_widgets_are_protected(self):
        for cls in ("Entry", "Text", "TCombobox", "Spinbox"):
            self.assertTrue(is_text_input_widget(DummyWidget(cls)))
        self.assertFalse(is_text_input_widget(DummyWidget("Treeview")))
        self.assertFalse(is_text_input_widget(None))


if __name__ == "__main__":
    unittest.main()
