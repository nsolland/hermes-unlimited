import unittest
from decimal import Decimal

from unlimited.communications_cost import Scenario, compare, seat_break_even


class CommunicationsCostTests(unittest.TestCase):
    def test_100_seat_illustration_with_complete_costs(self):
        s = Scenario(
            paid_seats=100, current_monthly_seat_price="7.25",
            alternative_monthly_base="199", alternative_monthly_operations="75",
            alternative_monthly_support="100", one_time_migration="2000",
            one_time_training="500",
        )
        result = compare(s)
        self.assertEqual(result["current_total"], "8700.00")
        self.assertEqual(result["alternative_total"], "6988")
        self.assertEqual(result["difference"], "1712.00")
        self.assertFalse(result["migration_feasible"])
        self.assertTrue(result["potential_savings_not_verified"])
        self.assertEqual(seat_break_even(s), 81)

    def test_no_savings_if_operations_are_expensive(self):
        s = Scenario(10, Decimal("7.25"), Decimal("500"))
        self.assertLess(Decimal(compare(s)["difference"]), 0)

    def test_per_seat_variable_cost(self):
        s = Scenario(10, "10", "0", alternative_monthly_per_seat="5")
        self.assertEqual(compare(s)["difference"], "600")

    def test_eligible_only_if_both_gates_verified(self):
        s = Scenario(10, "10", "0", capability_parity_verified=True,
                     security_requirements_verified=True)
        self.assertTrue(compare(s)["migration_feasible"])

    def test_no_break_even_for_worse_unit_cost(self):
        self.assertIsNone(seat_break_even(Scenario(10, "5", "0", alternative_monthly_per_seat="6")))

    def test_reject_negative_nan_and_infinite(self):
        for bad in ("-1", "NaN", "Infinity", "-Infinity", "abc"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                Scenario(10, bad, "0")

    def test_reject_invalid_seats_and_months(self):
        for bad in (0, -1, True, 1.5):
            with self.subTest(seats=bad), self.assertRaises(ValueError):
                Scenario(bad, "5", "0")
        with self.assertRaises(ValueError):
            Scenario(10, "5", "0", months=0)

    def test_zero_cost_existing_license_cannot_make_savings(self):
        s = Scenario(10, "0", "1")
        self.assertEqual(compare(s)["difference_pct"], "0")
        self.assertLess(Decimal(compare(s)["difference"]), 0)


if __name__ == "__main__":
    unittest.main()
