import pandas as pd
import pytest

import climate as cl


def test_summer_is_the_mean_of_june_to_august_and_stops_on_a_missing_month():
    m = pd.DataFrame({"region": "a", "year": 2020, "month": [5, 6, 7, 8, 9], "tmax_c": [10.0, 20.0, 26.0, 29.0, 22.0]})
    s = cl.summer(m)
    assert s.summer_tmax_c.iloc[0] == pytest.approx(25.0)
    with pytest.raises(ValueError):
        cl.summer(m[m.month != 7])
