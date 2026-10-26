import numpy as np
import pandas as pd

import dev_compare as d


def test_blocks_group_consecutive_origins_in_thirteen_week_blocks_in_time_order():
    weeks = [str(np.datetime64("2023-04-10") + np.timedelta64(7 * k, "D")) for k in range(30)]
    shuffled = weeks[::-1]
    b = d.origin_blocks(shuffled, size=13)
    assert b[weeks[0]] == 0 and b[weeks[12]] == 0 and b[weeks[13]] == 1 and b[weeks[26]] == 2


def test_season_of_a_target_week_by_month():
    assert d.season("2026-01-12") == "1 Jan-Mar"
    assert d.season("2026-05-04") == "2 Apr-May"
    assert d.season("2026-07-20") == "3 Jun-Aug"
    assert d.season("2026-10-05") == "4 Sep-Dec"
