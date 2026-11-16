import unittest
from scripts.harness_preflight import inspect_host


class HarnessPreflightTests(unittest.TestCase):
    def test_healthy_machine(self):
        x = inspect_host(load1=1, cpu_count=4,
                         meminfo={"MemAvailable": 4_000_000_000,
                                  "SwapTotal": 10_000, "SwapFree": 10_000})
        self.assertTrue(x["admissible"])
        self.assertEqual(x["reasons"], [])

    def test_reject_swap_and_load(self):
        x = inspect_host(load1=12, cpu_count=4,
                         meminfo={"MemAvailable": 2_000_000_000,
                                  "SwapTotal": 10_000, "SwapFree": 1000})
        self.assertFalse(x["admissible"])
        self.assertIn("HIGH_LOAD", x["reasons"])
        self.assertIn("SWAP_PRESSURE", x["reasons"])

    def test_reject_low_ram(self):
        x = inspect_host(load1=0, cpu_count=4,
                         meminfo={"MemAvailable": 100,
                                  "SwapTotal": 0, "SwapFree": 0})
        self.assertFalse(x["admissible"])
        self.assertIn("LOW_AVAILABLE_MEMORY", x["reasons"])

    def test_invalid_swap(self):
        with self.assertRaises(ValueError):
            inspect_host(load1=0, cpu_count=4,
                         meminfo={"MemAvailable": 4_000_000_000,
                                  "SwapTotal": 100, "SwapFree": 200})


if __name__ == "__main__":
    unittest.main()
