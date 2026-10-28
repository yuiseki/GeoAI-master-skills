"""Assemble the interactive map page: the template, the MapLibre stylesheet inlined (the page may not load
stylesheets from other hosts), and the table of checks read from the evaluation results.

Usage:
    python3 build_page.py TEMPLATE MAPLIBRE_CSS EVAL_DIR WEB_DIR/index.html
"""

import json
import sys

COLS = [("B_env", "地図のモデル (環境)"), ("M_full", "環境と過去の通報"), ("B_hist", "過去の通報の密度"), ("B_pop", "人口")]
ROWS = [("b2_confirm_2023-2024_to_2025.json", "2025 年度 (2023〜2024 年度で学習)"),
        ("b3_confirm_2023-2025_to_2026.json", "2026 年度 4〜9 月 (2023〜2025 年度で学習)")]


def checks(eval_dir):
    rows = []
    for f, label in ROWS:
        d = json.load(open(f"{eval_dir}/{f}"))
        rows.append({"label": label, "values": [d[m]["capture@5%"] for m, _ in COLS]})
    return {"columns": [{"key": m, "label": l} for m, l in COLS], "rows": rows,
            "note": "地図は 2026 年度の行の「地図のモデル (環境)」の予測です。このモデルを地図に選んだのは、2 つの年度の結果を見た後です。区間と判断の規則は報告書にあります。"}


def main():
    tpl, css, eval_dir, out = sys.argv[1:5]
    html = open(tpl, encoding="utf-8").read()
    for marker in ("/*MAPLIBRE_CSS*/", "/*CHECKS_JSON*/null"):
        if html.count(marker) != 1:
            raise SystemExit(f"the template must hold {marker} once")
    html = html.replace("/*MAPLIBRE_CSS*/", open(css, encoding="utf-8").read())
    html = html.replace("/*CHECKS_JSON*/null", json.dumps(checks(eval_dir), ensure_ascii=False))
    open(out, "w", encoding="utf-8").write(html)
    print("wrote", out, len(html.encode()), "bytes")


if __name__ == "__main__":
    main()
