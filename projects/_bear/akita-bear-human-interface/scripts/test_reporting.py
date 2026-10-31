"""Known-answer tests for the reporting-process diagnostics."""

import numpy as np
import pytest

import interface_reporting as ir


def test_per_cell_counts_reports_per_positive_cell():
    out = ir.per_cell(np.array([0, 0, 0, 2, 5]))
    assert out == {"positive_cells": 3, "reports": 5, "reports_per_cell": pytest.approx(5 / 3),
                   "share_cells_2plus": pytest.approx(1 / 3)}


def test_jsd_dict_aligns_missing_categories_as_zero():
    assert ir.jsd_dict({"a": 1}, {"a": 2}) == pytest.approx(0.0)
    assert ir.jsd_dict({"a": 1}, {"b": 1}) == pytest.approx(1.0)
