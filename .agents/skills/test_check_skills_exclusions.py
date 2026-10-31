"""Run with: python3 .agents/skills/test_check_skills_exclusions.py"""

import tempfile
import unittest
from pathlib import Path

import check_skills


class ExcludedSkillsTest(unittest.TestCase):
    def test_only_three_external_skills_are_excluded_from_all_scans(self):
        self.assertEqual(
            check_skills.EXCLUDED_SKILLS,
            {"natural-japanese", "stop-describing-ui", "yomiyasu"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "TODO.md").write_text("- test (0 / 0)\n")
            names = (*sorted(check_skills.EXCLUDED_SKILLS), "kept-skill")
            for name in names:
                skill = root / name
                scripts = skill / "scripts"
                scripts.mkdir(parents=True)
                (skill / "SKILL.md").write_text("**bad style**\n")
                (scripts / "broken.py").write_text("ROOT = __file__  # parents[2]\n")
                (scripts / "missing.py").write_text("VALUE = 1\n")
                (scripts / "test_broken.py").write_text("import sys\n")

            self.assertEqual(check_skills.skill_names(root), ["kept-skill"])
            checks = (
                check_skills.cross_skill_problems(root, check_skills.skill_names(root)),
                check_skills.style_problems(root),
                check_skills.script_test_problems(root),
                check_skills.todo_problems(root),
                check_skills.test_command_problems(root),
            )
            for problems in checks:
                self.assertTrue(problems)
                self.assertTrue(all("kept-skill" in item for item in problems), problems)


if __name__ == "__main__":
    unittest.main()
