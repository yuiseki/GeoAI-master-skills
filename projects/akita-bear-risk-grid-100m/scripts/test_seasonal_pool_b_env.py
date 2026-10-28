import unittest

import numpy as np

from grid import Grid
from seasonal_transfer_b_env import seasonal_labels
from seasonal_pool_b_env import fit_pooled, verify_previous_labels


class SeasonalPoolTest(unittest.TestCase):
    def test_2023_seasonal_counts_and_full_reconciliation(self):
        grid = Grid(0, 0, 2, 1, 100)
        muni = np.array([[0, 0]])
        dates = np.array(["2023-04-01", "2023-09-30", "2023-10-01",
                          "2024-04-01"], dtype="datetime64[m]")
        counts, info = seasonal_labels(grid, muni, [50, 150, 50, 150],
                                       [50, 50, 50, 50], dates,
                                       {2023: np.array([[2, 1]]), 2024: np.array([[0, 1]])},
                                       years=(2023, 2024))
        self.assertEqual(counts[2023].tolist(), [[1, 1]])
        self.assertEqual(info[2023]["positive_cells"], 2)

    def test_fit_rows_stacked_in_year_order_without_year_feature(self):
        X = np.arange(3 * 28, dtype=np.float32).reshape(3, 28)
        ys = {2023: np.array([True, False, False]),
              2024: np.array([False, True, False])}
        seen = []

        class Fake:
            def fit(self, XX, yy):
                seen.append((XX.copy(), yy.copy()))
                return self

            def predict_proba(self, XX):
                return np.column_stack([np.full(len(XX), .4), np.full(len(XX), .6)])

        scores, n_rows, n_positive = fit_pooled(X, ys, (2023, 2024), Fake)
        self.assertEqual(len(seen), 1)
        np.testing.assert_array_equal(seen[0][0], np.vstack([X, X]))
        self.assertEqual(seen[0][0].shape[1], 28)
        np.testing.assert_array_equal(seen[0][1], np.r_[ys[2023], ys[2024]])
        self.assertEqual((n_rows, n_positive), (6, 2))
        self.assertEqual(scores.tolist(), [.6, .6, .6])

    def test_previous_label_mismatch_rejected(self):
        current = {2024: {"positive_cells": 3, "inside_window_reports": 4,
                          "outside_window_reports": 0}}
        old = {"labels": {"2024": {"positive_cells": 2, "inside_window_reports": 4,
                                      "outside_window_reports": 0}}}
        with self.assertRaisesRegex(ValueError, "2024"):
            verify_previous_labels(current, old)


if __name__ == "__main__":
    unittest.main()
