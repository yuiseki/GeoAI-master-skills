"""Keep the medium-difficulty task tier complete and distinct from proposals."""

import re
import unittest
from pathlib import Path
import sys



ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from prepare_workdir import parse_frontmatter


class MediumTaskTests(unittest.TestCase):
    def test_task_and_rubric_are_paired(self):
        task_paths = sorted((ROOT / "tasks/medium").glob("[0-9][0-9].md"))
        self.assertEqual([path.stem for path in task_paths], ["01", "02", "03"])
        tasks = []
        for path in task_paths:
            metadata, body = parse_frontmatter(path.read_text(encoding="utf-8"))
            rubric_metadata, rubric = parse_frontmatter(
                (path.parent / "rubrics" / path.name).read_text(encoding="utf-8"))
            self.assertEqual(metadata["kind"], "task")
            self.assertEqual(rubric_metadata["kind"], "rubric")
            self.assertEqual(metadata["task_id"], rubric_metadata["task_id"])
            tasks.append(body)
        for section in tasks:
            for field in ("問い:", "使い道:", "使うデータ:", "範囲:", "提出:"):
                self.assertIn(field, section)
        self.assertIn("公表登録", "\n".join(tasks))
        self.assertNotIn("熱海市", "\n".join(tasks))

    def test_subagent_review_preserves_unverified_pilot_status(self):
        review = (ROOT / "curriculum/reviews/2026-10-25-subagent-topics.md").read_text()
        self.assertIn("提供情報・未再検証", review)
        self.assertIn("中難易度課題 3", review)
        for number in range(1, 6):
            self.assertIn(f"候補{number}", review)

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
