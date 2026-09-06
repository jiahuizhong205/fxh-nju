from pathlib import Path
import unittest


class WebProxyConfigTests(unittest.TestCase):
    def test_docker_vite_proxy_targets_api_service(self) -> None:
        source = (Path(__file__).parents[1] / "apps/web/vite.config.ts").read_text(encoding="utf-8")

        self.assertIn("target: 'http://api:8000'", source)
        self.assertNotIn("target: 'http://localhost:8000'", source)


if __name__ == "__main__":
    unittest.main()
