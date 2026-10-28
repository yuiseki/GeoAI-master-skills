"""uv run --no-project --with pytest --with numpy --with pyproj python3 -m pytest -q projects/__exp/japan-grid-population-audit/scripts/test_population_sensitivity.py"""

from population_sensitivity import compare_cutoff


def test_cutoff_recomputes_rankings_on_same_eligible_set():
    rows = [
        {
            "mesh_code": "a",
            "census_population": 1000,
            "ghsl_area": 900,
            "ghsl_center": 100,
        },
        {
            "mesh_code": "b",
            "census_population": 900,
            "ghsl_area": 800,
            "ghsl_center": 950,
        },
        {
            "mesh_code": "c",
            "census_population": 10,
            "ghsl_area": 1000,
            "ghsl_center": 1000,
        },
        {"mesh_code": "d", "census_population": 5, "ghsl_area": 1, "ghsl_center": 1},
    ]
    result = compare_cutoff(rows, 100, 0.5)
    assert result["eligible_meshes"] == 2
    assert result["excluded_meshes"] == 2
    assert result["rankings"][0]["method"] == "ghsl_area"
    assert result["rankings"][0]["recall"] == 1
    assert result["rankings"][1]["recall"] == 0
