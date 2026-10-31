# uvx --with pytest pytest scripts/test_summarize_drop.py
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("summarize_drop", Path(__file__).with_name("summarize_drop.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_two_is_a_fall_and_minus_two_is_between():
    assert module.classify([2.0, 3.5, -2.0, -2.1, 0.0]) == {
        "fall_at_least_2": 2, "rise_more_than_2": 1, "between": 2, "cells": 5}
