"""uvx --with pyyaml --with pytest pytest test_check_skills.py"""

from check_skills import frontmatter_problems

GOOD = """\
---
kind: dataset
id: org/a-2026
description: d
url: https://example.org
license: CC-BY-4.0
spatial_coverage: s
temporal_coverage: t
contents:
  - x
tables:
  - name: t1
    read: hf://x/t1.parquet
    grain: 1 つの行
    id:
      - k
    join_keys:
      - column: k
        type: VARCHAR
        meaning: m
        joins:
          - b:t2.k
          - t1.k
---
body
"""
OTHER = GOOD.replace("org/a-2026", "org/b").replace("t1", "t2").replace("          - b:t2.k\n          - t2.k\n", "          []\n")
SERVICE = """\
---
kind: service
id: svc
description: d
url: https://example.org
protocol: overpass
license: ODbL-1.0
spatial_coverage: s
temporal_coverage: t
operations:
  - name: q
    method: GET
    path: /q
    returns: json
---
"""


def write(tmp_path, name, text):
    (tmp_path / name).write_text(text)


def pair(tmp_path, a=GOOD, b=OTHER):
    write(tmp_path, "a.md", a)
    write(tmp_path, "b.md", b)
    return frontmatter_problems(tmp_path)


def test_complete_frontmatter_and_resolvable_joins_pass(tmp_path):
    assert pair(tmp_path) == []


def test_a_file_without_frontmatter_is_reported(tmp_path):
    write(tmp_path, "a.md", "# no frontmatter\n")
    assert any("no YAML frontmatter" in p for p in frontmatter_problems(tmp_path))


def test_a_missing_required_key_is_reported(tmp_path):
    assert any("missing license" in p for p in pair(tmp_path, GOOD.replace("license: CC-BY-4.0\n", "")))


def test_a_table_without_grain_is_reported(tmp_path):
    assert any("missing grain" in p for p in pair(tmp_path, GOOD.replace("    grain: 1 つの行\n", "")))


def test_a_join_to_a_dataset_or_table_that_does_not_exist_is_reported(tmp_path):
    assert any("no dataset nope" in p for p in pair(tmp_path, GOOD.replace("b:t2.k", "nope:t2.k")))
    assert any("no table zzz" in p for p in pair(tmp_path, GOOD.replace("b:t2.k", "b:zzz.k")))


def test_invalid_yaml_is_reported(tmp_path):
    write(tmp_path, "a.md", "---\nkind: [unclosed\n---\n")
    assert any("not valid YAML" in p for p in frontmatter_problems(tmp_path))


def test_a_complete_service_passes_and_an_operation_without_returns_is_reported(tmp_path):
    write(tmp_path, "s.md", SERVICE)
    assert frontmatter_problems(tmp_path) == []
    write(tmp_path, "s.md", SERVICE.replace("    returns: json\n", ""))
    assert any("operation q is missing returns" in p for p in frontmatter_problems(tmp_path))


def test_flow_style_is_refused_but_empty_collections_pass(tmp_path):
    assert any("block style" in p for p in pair(tmp_path, GOOD.replace("contents:\n  - x", "contents: [x, y: z]")))
    assert any("block style" in p for p in pair(tmp_path, GOOD.replace("      - column: k", "      - {column: k}")))
    assert pair(tmp_path, GOOD.replace("    id:\n      - k", "    id: []")) == []


def test_a_column_without_type_is_reported(tmp_path):
    columns = "    columns:\n      - name: c\n        meaning: m\n"
    assert any("a column needs name, type and meaning" in p
               for p in pair(tmp_path, GOOD.replace("    join_keys:", columns + "    join_keys:")))


def test_joining_columns_of_different_types_needs_a_cast(tmp_path):
    other = OTHER.replace("type: VARCHAR", "type: INTEGER")
    assert any("say how to cast" in p for p in pair(tmp_path, GOOD, other))
    cast = GOOD.replace("        meaning: m\n", "        meaning: m\n        cast: cast(k as integer)\n")
    assert pair(tmp_path, cast, other) == []
