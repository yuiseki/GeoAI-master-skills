"""uvx --with pyyaml --with pytest pytest test_check_skills.py"""

import textwrap

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
contents: [x]
tables:
  - name: t1
    read: hf://x/t1.parquet
    grain: 1 つの行
    id: [k]
    join_keys:
      - {column: k, meaning: m, joins: ["b:t2.k", "t1.k"]}
---
body
"""
OTHER = GOOD.replace("org/a-2026", "org/b").replace("t1", "t2").replace('joins: ["b:t2.k", "t2.k"]', "joins: []")


def write(tmp_path, name, text):
    (tmp_path / name).write_text(textwrap.dedent(text) if text.startswith(" ") else text)


def test_complete_frontmatter_and_resolvable_joins_pass(tmp_path):
    write(tmp_path, "a.md", GOOD)
    write(tmp_path, "b.md", OTHER.replace("kind: dataset", "kind: dataset"))
    assert frontmatter_problems(tmp_path) == []


def test_a_file_without_frontmatter_is_reported(tmp_path):
    write(tmp_path, "a.md", "# no frontmatter\n")
    assert any("no YAML frontmatter" in p for p in frontmatter_problems(tmp_path))


def test_a_missing_required_key_is_reported(tmp_path):
    write(tmp_path, "a.md", GOOD.replace("license: CC-BY-4.0\n", ""))
    write(tmp_path, "b.md", OTHER)
    assert any("missing license" in p for p in frontmatter_problems(tmp_path))


def test_a_table_without_grain_is_reported(tmp_path):
    write(tmp_path, "a.md", GOOD.replace("    grain: 1 つの行\n", ""))
    write(tmp_path, "b.md", OTHER)
    assert any("missing grain" in p for p in frontmatter_problems(tmp_path))


def test_a_join_to_a_dataset_or_table_that_does_not_exist_is_reported(tmp_path):
    write(tmp_path, "a.md", GOOD.replace("b:t2.k", "nope:t2.k"))
    write(tmp_path, "b.md", OTHER)
    assert any("no dataset nope" in p for p in frontmatter_problems(tmp_path))
    write(tmp_path, "a.md", GOOD.replace("b:t2.k", "b:zzz.k"))
    assert any("no table zzz" in p for p in frontmatter_problems(tmp_path))


def test_invalid_yaml_is_reported(tmp_path):
    write(tmp_path, "a.md", "---\nkind: [unclosed\n---\n")
    assert any("not valid YAML" in p for p in frontmatter_problems(tmp_path))


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
  - {name: q, method: GET, path: /q, returns: json}
---
"""


def test_a_complete_service_passes_and_an_operation_without_returns_is_reported(tmp_path):
    write(tmp_path, "s.md", SERVICE)
    assert frontmatter_problems(tmp_path) == []
    write(tmp_path, "s.md", SERVICE.replace(", returns: json", ""))
    assert any("operation q is missing returns" in p for p in frontmatter_problems(tmp_path))
