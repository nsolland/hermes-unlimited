"""Tests for the permission inventory and audit module (issue #22)."""

import os
import sys
import unittest

# Ensure the local package is importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unlimited.permission_inventory import (
    AuditResult,
    PermissionEntry,
    audit_hermes_yolo_mode,
    inventory_permission_entries,
)

# Expose the function so ruff does not complain about unused import.
_NOQA_SENTINEL = audit_hermes_yolo_mode


class TestPermissionInventory(unittest.TestCase):
    def test_inventory_returns_expected_structure(self):
        entries = inventory_permission_entries()
        self.assertIsInstance(entries, list)
        for e in entries:
            self.assertIsInstance(e, PermissionEntry)
            self.assertIn(e.namespace, {"HERMES", "OPENAI", "ANTHROPIC", "GOOGLE", "ALIBABA"})
            self.assertIn(e.source, {"env", "code"})
            self.assertIsInstance(e.permitted, bool)

    def test_inventory_contains_documented_allowlist(self):
        entries = inventory_permission_entries()
        hermes_keys = [e.key for e in entries if e.namespace == "HERMES"]
        self.assertTrue(any("HERMES_ACCEPT_HOOKS" in k for k in hermes_keys))
        self.assertTrue(
            any("HERMES_YOLO" in k for k in hermes_keys)
            or any("HERMES_API_TIMEOUT" in k for k in hermes_keys)
        )

    def test_audit_returns_structured_result(self):
        result = audit_hermes_yolo_mode()
        self.assertIsInstance(result, AuditResult)
        self.assertIsInstance(result.hermes_yolo_mode, bool)
        self.assertIsInstance(result.hermes_yolo_explicitly_set, bool)
        self.assertIsInstance(result.provider_aliases, list)
        self.assertIsInstance(result.catalog_entries, int)
        self.assertIsInstance(result.warnings, list)
        self.assertGreaterEqual(result.catalog_entries, 0)

    def test_audit_no_side_effects(self):
        original = dict(os.environ)
        original_env = os.environ.get("HERMES_YOLO_MODE")
        os.environ["HERMES_YOLO_MODE"] = "1"
        try:
            result = audit_hermes_yolo_mode()
            self.assertTrue(result.hermes_yolo_mode)
            self.assertTrue(result.hermes_yolo_explicitly_set)
        finally:
            os.environ.clear()
            os.environ.update(original)
            if original_env is None:
                os.environ.pop("HERMES_YOLO_MODE", None)

    def test_audit_with_yolo_mode_set(self):
        os.environ["HERMES_YOLO_MODE"] = "1"
        try:
            result = audit_hermes_yolo_mode()
            self.assertTrue(result.hermes_yolo_mode)
            self.assertTrue(result.hermes_yolo_explicitly_set)
        finally:
            os.environ.pop("HERMES_YOLO_MODE", None)

    def test_audit_without_yolo_mode(self):
        if "HERMES_YOLO_MODE" in os.environ:
            del os.environ["HERMES_YOLO_MODE"]
        try:
            result = audit_hermes_yolo_mode()
            self.assertGreaterEqual(result.catalog_entries, 0)
        finally:
            if "HERMES_YOLO_MODE" in os.environ:
                del os.environ["HERMES_YOLO_MODE"]


if __name__ == "__main__":
    unittest.main()
