import unittest

from unlimited.specialist_factory import (
    Trial, build_specialist, discover_capabilities, rank_models, specialist_manifest,
)


SCHEMAS = [
    {"name": "dns_list", "description": "List records", "effect": "read",
     "parameters": {"type": "object", "properties": {"zone": {"type": "string"}},
                    "required": ["zone"]}},
    {"name": "dns_update", "description": "Update records", "effect": "write",
     "parameters": {"type": "object", "properties": {"zone": {"type": "string"}},
                    "required": ["zone"]}},
]


class SpecialistFactoryTests(unittest.TestCase):
    def test_tool_first_inventory_and_bounded_agent(self):
        catalog = discover_capabilities(SCHEMAS)
        self.assertFalse(catalog[0].verified_access)
        agent = build_specialist("Diagnose DNS", ["dns_list"], catalog)
        self.assertEqual(agent.tools, ("dns_list",))
        self.assertEqual(agent.status, "DRAFT_UNVERIFIED")
        self.assertFalse(specialist_manifest(agent)["execution_authorized"])
        self.assertEqual(agent, build_specialist("Diagnose DNS", ["dns_list"], catalog))

    def test_no_silent_permission_expansion(self):
        catalog = discover_capabilities(SCHEMAS)
        with self.assertRaises(PermissionError):
            build_specialist("Change DNS", ["dns_update"], catalog)
        with self.assertRaises(ValueError):
            build_specialist("Something", ["invented"], catalog)
        changed = build_specialist("Change DNS", ["dns_update"], catalog,
                                   allowed_effects=("read", "write"))
        self.assertFalse(specialist_manifest(changed)["execution_authorized"])

    def test_schema_validation_and_drift(self):
        with self.assertRaises(ValueError):
            discover_capabilities([SCHEMAS[0], SCHEMAS[0]])
        with self.assertRaises(ValueError):
            discover_capabilities([{"name": "x", "parameters": {"type": "string"}}])
        other = [dict(SCHEMAS[0], description="Different semantics")]
        self.assertNotEqual(discover_capabilities(other)[0].schema_digest,
                            discover_capabilities(SCHEMAS)[0].schema_digest)

    def test_model_selection_uses_real_coverage_and_cost(self):
        trials = [
            Trial(model, case, True, cost, latency, True, f"{model}-{case}-{rep}")
            for model, cost, latency in (("frontier", 12, 2), ("small", 1, 0.2))
            for case in ("normal", "failure")
            for rep in range(4)
        ]
        result = rank_models(trials, ["normal", "failure"])
        self.assertEqual(result["recommended_model"], "small")
        self.assertEqual(result["status"], "QUALIFIED")
        self.assertEqual(len(result["models"]), 2)

    def test_unverified_incomplete_and_duplicate_fail_closed(self):
        unverified = [Trial("tiny", "normal", True, 0, 0, False, f"a{x}") for x in range(4)]
        self.assertEqual(rank_models(unverified, ["normal"])["status"], "NO_QUALIFIED_MODEL")
        partial = [Trial("tiny", "normal", True, 0, 0, True, f"b{x}") for x in range(3)]
        self.assertIsNone(rank_models(partial, ["normal", "failure"])["recommended_model"])
        dup = [Trial("tiny", "normal", True, 0, 0, True, "same") for _ in range(3)]
        self.assertFalse(rank_models(dup, ["normal"])["models"][0]["qualified"])

    def test_failure_rate_and_latency_constraints(self):
        trials = [Trial("tiny", "case", rep != 0, 1, 9, True, f"r{rep}") for rep in range(10)]
        self.assertIsNone(rank_models(trials, ["case"], min_pass_rate=.95)["recommended_model"])
        self.assertIsNone(rank_models(trials, ["case"], min_pass_rate=.8,
                                       max_latency_seconds=5)["recommended_model"])
        self.assertEqual(rank_models(trials, ["case"], min_pass_rate=.8)["recommended_model"], "tiny")


if __name__ == "__main__":
    unittest.main()

class HostIntegrationTests(unittest.TestCase):
    def test_registry_based_discovery(self):
        from unlimited.specialist_factory import discover_host_tools
        class Registry:
            def get_all_tool_names(self):
                return ["dns_lookup", "other_tool", "unlimited_specialist_factory"]
            def get_toolset_for_tool(self, name):
                return "dns" if name == "dns_lookup" else "other"
            def get_definitions(self, names, quiet=False):
                return [{"function": {"name": "dns_lookup", "description": "Lookup DNS",
                                      "parameters": {"type": "object", "properties": {}}}}] if names else []
        capabilities = discover_host_tools(Registry(), toolset="dns")
        self.assertEqual([cap.tool_name for cap in capabilities], ["dns_lookup"])
        self.assertEqual(capabilities[0].effect, "unknown")
        with self.assertRaises(PermissionError):
            build_specialist("Check DNS", ["dns_lookup"], capabilities)

    def test_reviewed_effect_is_not_execution_authority(self):
        from unlimited.specialist_factory import review_capability_effects
        unknown = [dict(SCHEMAS[0], effect="unknown")]
        caps = discover_capabilities(unknown)
        with self.assertRaises(PermissionError):
            build_specialist("Inspect", ["dns_list"], caps)
        reviewed = review_capability_effects(caps, {"dns_list": "read"})
        proposal = build_specialist("Inspect", ["dns_list"], reviewed)
        self.assertFalse(specialist_manifest(proposal)["execution_authorized"])
        with self.assertRaises(ValueError):
            review_capability_effects(caps, {"unknown": "read"})

    def test_host_owned_live_probe_requires_measured_cost_and_exact_model(self):
        from types import SimpleNamespace
        from unlimited.specialist_factory import run_live_probe
        class LLM:
            def complete(self, messages, **options):
                self.options = options
                return SimpleNamespace(text="OK", model="small",
                                       usage=SimpleNamespace(cost_usd=0.0001))
        host = LLM()
        trial = run_live_probe(host, model_id="small", case_id="exact", prompt="Respond OK",
                               expected="OK", cost_usd_to_minor=10000, run_id="r1")
        self.assertTrue(trial.passed)
        self.assertEqual(trial.cost_minor, 1)
        self.assertTrue(trial.independently_verified)
        self.assertEqual(host.options["model"], "small")
        class MissingCost(LLM):
            def complete(self, *args, **kwargs):
                return SimpleNamespace(text="OK", model="small",
                                       usage=SimpleNamespace(cost_usd=None))
        with self.assertRaises(ValueError):
            run_live_probe(MissingCost(), model_id="small", case_id="exact", prompt="Respond OK",
                           expected="OK", cost_usd_to_minor=10000, run_id="r2")

class ModelMatrixTests(unittest.TestCase):
    def test_matrix_runs_each_case_on_each_model_three_times(self):
        from types import SimpleNamespace
        from unlimited.specialist_factory import run_model_matrix
        class Host:
            def complete(self, messages, **kwargs):
                return SimpleNamespace(
                    model=kwargs["model"],
                    text="OK" if "good" in kwargs["model"] else "wrong",
                    usage=SimpleNamespace(cost_usd=.001 if "good" in kwargs["model"] else .0001),
                )
        result = run_model_matrix(
            Host(), models=["good-small", "bad-tiny"],
            cases=[{"case_id": "simple", "prompt": "Output OK", "expected": "OK"},
                   {"case_id": "exception", "prompt": "Output OK exactly", "expected": "OK"}],
            repetitions=3, cost_usd_to_minor=1000,
        )
        self.assertEqual(result["recommended_model"], "good-small")
        self.assertEqual(len(result["observations"]), 12)
        self.assertEqual(len({t["run_id"] for t in result["observations"]}), 12)
        self.assertFalse(next(x for x in result["models"] if x["model_id"] == "bad-tiny")["qualified"])

    def test_matrix_bounds_and_no_silent_pricing(self):
        from types import SimpleNamespace
        from unlimited.specialist_factory import run_model_matrix
        class MissingPrice:
            def complete(self, *args, **kwargs):
                return SimpleNamespace(text="OK", model=kwargs["model"],
                                       usage=SimpleNamespace(cost_usd=None))
        case = [{"case_id": "one", "prompt": "OK", "expected": "OK"}]
        with self.assertRaises(ValueError):
            run_model_matrix(MissingPrice(), models=["small"], cases=case,
                             repetitions=2, cost_usd_to_minor=100)
        with self.assertRaises(ValueError):
            run_model_matrix(MissingPrice(), models=["small"], cases=case,
                             repetitions=3, cost_usd_to_minor=100)
        with self.assertRaises(ValueError):
            run_model_matrix(MissingPrice(), models=["a", "b", "c", "d"],
                             cases=case * 4, repetitions=3, cost_usd_to_minor=100)
