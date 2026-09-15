import json
import unittest

from scripts.verify_real_llm_agents import AGENT_CHECKS, final_content, response_json


class RealLlmAgentProbeTests(unittest.TestCase):
    def test_probe_contract_covers_all_agent_intents(self) -> None:
        self.assertEqual(
            {intent for intent, _message in AGENT_CHECKS},
            {"policy", "recommend", "schedule", "tutor", "career"},
        )

    def test_probe_parses_final_sse_content(self) -> None:
        body = (
            "event: token\r\n"
            f"data: {json.dumps({'content': 'partial'}, ensure_ascii=False)}\r\n\r\n"
            "event: final\r\n"
            f"data: {json.dumps({'content': '最终回答'}, ensure_ascii=False)}\r\n\r\n"
        )
        self.assertEqual(final_content(body, "policy"), "最终回答")

    def test_probe_errors_do_not_echo_response_content(self) -> None:
        private_text = "用户问题或完整记忆"
        for body in (
            f"event: error\ndata: {json.dumps({'message': private_text}, ensure_ascii=False)}\n\n",
            f"event: token\ndata: {json.dumps({'content': private_text}, ensure_ascii=False)}\n\n",
        ):
            with self.subTest(body=body), self.assertRaises(AssertionError) as caught:
                final_content(body, "policy")
            self.assertNotIn(private_text, str(caught.exception))

    def test_response_json_rejects_non_success_without_body_leak(self) -> None:
        class Response:
            status_code = 503

            @staticmethod
            def json():
                return {"detail": "private provider response"}

        with self.assertRaisesRegex(AssertionError, "HTTP 503") as caught:
            response_json(Response(), "就绪检查")
        self.assertNotIn("private provider response", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
