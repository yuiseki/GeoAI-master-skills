# uvx --with pytest pytest scripts/test_summarize_existing.py
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("summarize_existing", Path(__file__).with_name("summarize_existing.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_counts_all_sites_and_the_ones_open_in_an_arakawa_flood():
    rows = [
        {"capacity": "129", "arakawa_open": "False"},
        {"capacity": "200", "arakawa_open": "True"},
        {"capacity": "50", "arakawa_open": "True"},
    ]
    assert module.summarize(rows) == {
        "existing_shelters_count": 3,
        "existing_shelters_capacity_total": 379,
        "arakawa_open_shelters_count": 2,
        "arakawa_open_shelters_capacity": 250,
    }
