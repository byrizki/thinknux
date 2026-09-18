"""Tests for Polkit rule generation and helper script hardening."""

import unittest

from thinknux.core.permissions import HELPER_SCRIPT_CONTENT, polkit_rule


class TestPermissions(unittest.TestCase):
    def test_polkit_rule_content(self):
        rule = polkit_rule()
        self.assertIn("thinknux-fan-control", rule)
        self.assertIn("subject.local && subject.active", rule)
        self.assertIn('subject.isInGroup("wheel")', rule)
        self.assertIn('subject.isInGroup("sudo")', rule)
        self.assertIn("polkit.Result.YES", rule)

    def test_helper_script_safety(self):
        self.assertIn("watchdog 30", HELPER_SCRIPT_CONTENT)
        self.assertIn("level auto", HELPER_SCRIPT_CONTENT)
        self.assertIn("level full-speed", HELPER_SCRIPT_CONTENT)
        self.assertIn('echo "Invalid command" >&2', HELPER_SCRIPT_CONTENT)
        self.assertIn("exit 1", HELPER_SCRIPT_CONTENT)


if __name__ == "__main__":
    unittest.main()
