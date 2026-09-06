from pathlib import Path
import unittest


class ProductionDeploymentConfigTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_production_compose_uses_private_services_and_static_web(self) -> None:
        compose = (self.ROOT / "infra/compose/docker-compose.prod.yml").read_text(encoding="utf-8")

        self.assertIn("Dockerfile.web.prod", compose)
        self.assertIn("PYTHONPATH: /app", compose)
        self.assertIn('"127.0.0.1:${APP_PORT:-8080}:80"', compose)
        self.assertNotIn('"5432:5432"', compose)
        self.assertNotIn('"6379:6379"', compose)
        self.assertIn("condition: service_healthy", compose)

    def test_production_web_preserves_sse_and_spa_routing(self) -> None:
        nginx = (self.ROOT / "infra/nginx/fuxiaohe.conf").read_text(encoding="utf-8")

        self.assertIn("proxy_buffering off", nginx)
        self.assertIn("try_files $uri $uri/ /index.html", nginx)
        self.assertIn("proxy_pass http://api:8000", nginx)

    def test_database_bootstrap_creates_required_extensions(self) -> None:
        database = (self.ROOT / "apps/api/database.py").read_text(encoding="utf-8")

        self.assertIn("CREATE EXTENSION IF NOT EXISTS vector", database)
        self.assertIn("CREATE EXTENSION IF NOT EXISTS pg_trgm", database)

    def test_production_secret_template_is_not_trackable_as_runtime_env(self) -> None:
        gitignore = (self.ROOT / ".gitignore").read_text(encoding="utf-8")
        template = (self.ROOT / ".env.production.example").read_text(encoding="utf-8")

        self.assertIn(".env.*", gitignore)
        self.assertIn("! .env.production.example".replace(" ", ""), gitignore)
        self.assertIn("LLM_API_KEY=replace_with_chat_api_key", template)


if __name__ == "__main__":
    unittest.main()
