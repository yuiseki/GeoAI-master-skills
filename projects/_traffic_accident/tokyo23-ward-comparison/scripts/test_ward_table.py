"""uvx --python 3.12 --with pytest pytest -q -p no:cacheprovider test_ward_table.py"""

import csv

import ward_table

PROFILE = {"code": "113", "name": "渋谷区", "high": "", "low": "高齢の歩行者", "rank_per_1000": "3",
           "rank_per_road_km": "1", "rank_per_km2": "2", "trend_2025": "減", "ratio_2025_2019": "0.81",
           "trend_2025_without_bike_alone": "減"}


def test_every_ward_code_has_a_slug():
    assert sorted(ward_table.SLUG) == [str(c) for c in range(101, 124)]
    assert len(set(ward_table.SLUG.values())) == 23


def test_rows_link_existing_reports_and_fill_empty_cells():
    out = ward_table.rows([PROFILE, dict(PROFILE, code="101", name="千代田区", high="自転車", low="")],
                          lambda slug: slug == "shibuya")
    assert out[0].count("|") == 8 and out[1] == "|---|---|---|---|---|---|---|"
    assert out[2] == ("| 渋谷区 | なし | 高齢の歩行者 | 3、1、2 | 減 (0.81) | 減 | "
                      "[shibuya](../shibuya-accident-trends-by-role/report.md) |")
    assert out[3] == "| 千代田区 | 自転車 | なし | 3、1、2 | 減 (0.81) | 減 | 作成中 |"


def test_main_rewrites_only_between_the_markers(tmp_path, monkeypatch):
    project = tmp_path / "tokyo23-ward-comparison"
    (project / "outputs").mkdir(parents=True)
    (tmp_path / "shibuya-accident-trends-by-role").mkdir()
    (tmp_path / "shibuya-accident-trends-by-role/report.md").write_text("x", encoding="utf-8")
    with (project / "outputs/profiles.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(PROFILE))
        w.writeheader()
        w.writerow(PROFILE)
        w.writerow(dict(PROFILE, code="101", name="千代田区"))
    report = project / "report.md"
    report.write_text("# head\n<!-- ward-table -->\nold table\n<!-- /ward-table -->\ntail\n", encoding="utf-8")
    monkeypatch.setattr(ward_table, "PROJECT", project)
    monkeypatch.setattr(ward_table, "REPORT", report)
    ward_table.main()
    text = report.read_text(encoding="utf-8")
    assert text.startswith("# head\n<!-- ward-table -->\n| 区 |") and text.endswith("<!-- /ward-table -->\ntail\n")
    assert "old table" not in text
    assert "[shibuya](../shibuya-accident-trends-by-role/report.md)" in text and "| 千代田区 |" in text
    assert text.count("作成中") == 1
    # Running it again leaves the report unchanged (the table never drifts).
    ward_table.main()
    assert report.read_text(encoding="utf-8") == text
