# uvx --with pytest pytest scripts/test_quote_source.py
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("quote_source", Path(__file__).with_name("quote_source.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_returns_the_line_that_holds_each_phrase():
    text = "# 事例\n\n- AUC は 0.849 から 0.988 に跳ねる。電柱は言い換え。\n- 別の行\n"
    assert module.quote(text, ["0.849 から 0.988"]) == {"0.849 から 0.988": "- AUC は 0.849 から 0.988 に跳ねる。電柱は言い換え。"}


def test_a_phrase_the_source_does_not_hold_stops():
    with pytest.raises(ValueError, match="does not say"):
        module.quote("# 事例\n", ["0.849 から 0.988"])
