import unittest
from amp.amp.quantities import completion, number, progress_values, structural_progress_values, unique_match, weighted_completion


class QuantityTests(unittest.TestCase):
    def test_mixed_units_are_weighted_not_added(self):
        rows = [dict(budget_qty=1000, executed_qty=1000, progress_weight=1),
                dict(budget_qty=2, executed_qty=0, progress_weight=3)]
        self.assertEqual(weighted_completion(rows), 25)

    def test_overrun_is_visible_but_completion_capped(self):
        result = progress_values(10, 8, 5)
        self.assertEqual(result['overrun_qty'], 3)
        self.assertEqual(result['remaining_qty'], 0)
        self.assertEqual(result['percent_progress'], 100)

    def test_zero_budget_and_unallocated_lines_do_not_dilute_progress(self):
        self.assertEqual(weighted_completion([dict(budget_qty=10, executed_qty=5, progress_weight=1),
            dict(budget_qty=0, executed_qty=20, progress_weight=0)]), 50)
        self.assertEqual(completion(10, 0), 0)

    def test_legacy_matching_never_guesses_duplicate_item(self):
        rows = [dict(item_code='STEEL', uom='Kg', discipline='Civil'), dict(item_code='STEEL', uom='Kg', discipline='Structural')]
        self.assertIsNone(unique_match(rows, 'STEEL', 'Kg'))
        self.assertEqual(unique_match(rows, 'STEEL', 'Kg', 'Civil'), rows[0])

    def test_reject_nonfinite_quantities(self):
        for value in ['NaN', 'Infinity', '-Infinity']:
            with self.assertRaises(ValueError):
                number(value)

    def test_structural_stages_are_weighted_not_added(self):
        result = structural_progress_values(100, 40, 60, 50, 20)
        self.assertEqual(result['executed_qty'], 32)
        self.assertEqual(result['percent_progress'], 32)
        self.assertEqual((result['fabricated_qty'], result['erected_qty']), (50, 20))

    def test_structural_rejects_invalid_stage_order_and_weights(self):
        with self.assertRaisesRegex(ValueError, 'Erected'):
            structural_progress_values(100, 50, 50, 10, 11)
        with self.assertRaisesRegex(ValueError, 'weights'):
            structural_progress_values(100, 25, 50, 10, 5)
