import unittest

from memory_hub.policy import resolve_task_type, roles_for_task


class PolicyTests(unittest.TestCase):
    def test_explicit_task_type_wins(self) -> None:
        self.assertEqual(resolve_task_type("anything", "implement"), "implement")

    def test_keyword_classification(self) -> None:
        self.assertEqual(resolve_task_type("请帮我做架构设计", "auto"), "design")
        self.assertEqual(resolve_task_type("please write code to fix bug", "auto"), "implement")
        self.assertEqual(resolve_task_type("create a roadmap and milestones", "auto"), "planning")

    def test_roles_for_task(self) -> None:
        self.assertEqual(roles_for_task("planning"), ["pm", "architect"])
        self.assertEqual(roles_for_task("implement"), ["architect", "dev"])
        self.assertEqual(roles_for_task("review"), ["qa", "dev", "architect"])


if __name__ == "__main__":
    unittest.main()
