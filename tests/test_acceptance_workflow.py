import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AcceptanceWorkflowContractTests(unittest.TestCase):
    def test_fresh_user_verifier_covers_primary_journey_and_cleanup(self):
        source = (ROOT / "scripts/verify_user_journey.py").read_text(encoding="utf-8")
        for path in (
            "/auth/register", "/profile/options", "/profile/avatar", "/auth/onboarding",
            "/recommend", "/programs/plan", "/knowledge/search", "/chat",
            "/conversations", "/learning/progress",
        ):
            self.assertIn(path, source)
        self.assertIn("delete(User)", source)
        self.assertIn("finally:", source)
        self.assertIn("trust_env=False", source)


if __name__ == "__main__":
    unittest.main()
