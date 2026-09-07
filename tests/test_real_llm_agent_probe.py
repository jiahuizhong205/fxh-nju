from pathlib import Path
import unittest


class RealLlmAgentProbeTests(unittest.TestCase):
    def test_probe_covers_all_agent_intents_and_cleanup(self) -> None:
        source = (Path(__file__).parents[1] / "scripts/verify_real_llm_agents.py").read_text(encoding="utf-8")

        for intent in ("policy", "recommend", "schedule", "tutor", "career"):
            self.assertIn(f'("{intent}"', source)
        self.assertIn("insert_test_job", source)
        self.assertIn("finally:", source)
        self.assertIn("delete(Job)", source)
        self.assertIn("delete(User)", source)
        self.assertIn('parser.add_argument("--intent"', source)

    def test_probe_reports_sse_error_detail_or_tail_when_final_is_missing(self) -> None:
        source = (Path(__file__).parents[1] / "scripts/verify_real_llm_agents.py").read_text(encoding="utf-8")

        self.assertIn("SSE末尾", source)
        self.assertIn("错误事件：", source)


if __name__ == "__main__":
    unittest.main()
