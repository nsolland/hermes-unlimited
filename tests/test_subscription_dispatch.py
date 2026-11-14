import json
import subprocess
import unittest

from unlimited.hermes_kanban import HermesKanban
from unlimited.subscription_dispatch import (
    ProfileCapacity, choose_hermes_profile, enqueue_subscription_first,
)


def profile(name, source="customer_owned", **kwargs):
    return ProfileCapacity(
        tenant_id=kwargs.pop("tenant_id", "tenant-a"),
        profile=name, billing_source=source, task_kinds=("research",),
        expected_quality=kwargs.pop("expected_quality", 0.95),
        marginal_cost_minor=kwargs.pop("marginal_cost_minor", 1),
        **kwargs,
    )


class SubscriptionDispatchTests(unittest.TestCase):
    def test_owned_capacity_first_even_when_paid_is_cheaper(self):
        result = choose_hermes_profile(
            [profile("paid", "hermes_paid", marginal_cost_minor=0),
             profile("owned", marginal_cost_minor=2)],
            tenant_id="tenant-a", task_kind="research", min_quality=0.9,
            max_marginal_cost_minor=5, allow_paid_fallback=True,
        )
        self.assertEqual(result.profile, "owned")

    def test_paid_requires_explicit_permission(self):
        request = dict(tenant_id="tenant-a", task_kind="research",
                       min_quality=0.9, max_marginal_cost_minor=5)
        with self.assertRaisesRegex(LookupError, "NO_ELIGIBLE"):
            choose_hermes_profile([profile("paid", "hermes_paid")], **request)
        self.assertEqual(choose_hermes_profile(
            [profile("paid", "hermes_paid")], allow_paid_fallback=True,
            **request).profile, "paid")

    def test_reject_unavailable_expired_low_quality_or_cross_tenant(self):
        entries = [
            profile("offline", available=False),
            profile("quota", quota_remaining=0),
            profile("denied", permitted=False),
            profile("lowquality", expected_quality=0.1),
            profile("other", tenant_id="tenant-b"),
            profile("suitable"),
        ]
        selected = choose_hermes_profile(
            entries, tenant_id="tenant-a", task_kind="research",
            min_quality=0.9, max_marginal_cost_minor=2,
        )
        self.assertEqual(selected.profile, "suitable")

    def test_duplicate_bindings_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            choose_hermes_profile(
                [profile("same"), profile("same")],
                tenant_id="tenant-a", task_kind="research",
                min_quality=0, max_marginal_cost_minor=5,
            )

    def test_native_kanban_receives_scoped_customer_profile(self):
        calls = []
        def native(argv, **kwargs):
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, json.dumps({"id": "task-native"}), "")
        kanban = HermesKanban(board="unlimited-isolated", run=native)
        result = enqueue_subscription_first(
            kanban, profiles=[profile("owned"), profile("paid", "hermes_paid")],
            identity_evidence_by_profile={
                "owned": {"profile": "owned", "verified": True,
                          "authority_granted": False, "binding_digest": "signed"}
            },
            tenant_id="tenant-a", task_kind="research", min_quality=0.9,
            max_marginal_cost_minor=5, task_id="objective-01",
            title="Research customer issue", body="No external effect",
        )
        self.assertEqual(result["status"], "TASK_QUEUED")
        self.assertEqual(result["billing_source"], "customer_owned")
        self.assertFalse(result["executed"])
        self.assertIn("owned", calls[0])
        self.assertNotIn("--yolo", calls[0])

    def test_absent_identity_denies_without_paid_fallback(self):
        calls = []
        kanban = HermesKanban(board="unlimited-isolated", run=lambda *a, **kw: calls.append(a))
        with self.assertRaisesRegex(PermissionError, "IDENTITY_NOT_VERIFIED"):
            enqueue_subscription_first(
                kanban, profiles=[profile("owned"), profile("paid", "hermes_paid")],
                identity_evidence_by_profile={}, tenant_id="tenant-a",
                task_kind="research", min_quality=0.9, max_marginal_cost_minor=5,
                task_id="objective-02", title="Task", body="", allow_paid_fallback=True,
            )
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
