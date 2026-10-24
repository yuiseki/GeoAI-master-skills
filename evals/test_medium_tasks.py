"""Keep the medium-difficulty task tier complete and distinct from proposals."""

import re
import unittest
from pathlib import Path



ROOT = Path(__file__).resolve().parent


class MediumTaskTests(unittest.TestCase):
    def test_task_and_rubric_are_paired(self):
        tasks = (ROOT / "tasks/medium-tasks.md").read_text()
        rubric = (ROOT / "tasks/medium-rubric.md").read_text()
        task_ids = re.findall(r"^## 課題 (\d+):", tasks, re.MULTILINE)
        rubric_ids = re.findall(r"^## 課題 (\d+):", rubric, re.MULTILINE)
        self.assertEqual(task_ids, ["1", "2"])
        self.assertEqual(rubric_ids, task_ids)
        for section in re.split(r"^## 課題 \d+:", tasks, flags=re.MULTILINE)[1:]:
            for field in ("問い:", "使い道:", "使うデータ:", "範囲:", "提出:"):
                self.assertIn(field, section)

    def test_cards_disclose_review_and_evidence_status(self):
        cards = ROOT / "curriculum/task-cards"
        for name in (
            "2026-10-24-hill-bus-elevation.md",
            "2026-10-24-border-conflict-scale.md",
            "2026-10-24-persistent-land-cover-change.md",
            "2026-10-24-station-route-cooccurrence.md",
            "2026-10-24-grocery-access.md",
        ):
            text = (cards / name).read_text()
            self.assertIn("提供情報・未再検証", text)
            self.assertIn("作業仮説", text)
            self.assertIn("停止条件", text)


if __name__ == "__main__":
    unittest.main()
