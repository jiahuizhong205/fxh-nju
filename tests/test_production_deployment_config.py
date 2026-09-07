from pathlib import Path
import unittest


class ProductionDeploymentConfigTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_production_compose_uses_private_services_and_static_web(self) -> None:
        compose = (self.ROOT / "infra/compose/docker-compose.prod.yml").read_text(encoding="utf-8")
        development_compose = (self.ROOT / "infra/compose/docker-compose.yml").read_text(encoding="utf-8")

        self.assertIn("Dockerfile.web.prod", compose)
        self.assertIn("PYTHONPATH: /app", compose)
        self.assertIn('"${WEB_BIND_ADDRESS:-127.0.0.1}:${APP_PORT:-8080}:80"', compose)
        self.assertNotIn('"5432:5432"', compose)
        self.assertNotIn('"6379:6379"', compose)
        self.assertIn("condition: service_healthy", compose)
        self.assertIn("PIP_INDEX_URL: ${PIP_INDEX_URL:-https://pypi.org/simple}", compose)
        self.assertIn("PIP_DEFAULT_TIMEOUT: ${PIP_DEFAULT_TIMEOUT:-300}", compose)
        self.assertIn("../../scripts:/app/scripts", development_compose)
        self.assertIn("../../infra/migrations:/app/infra/migrations", development_compose)

    def test_production_web_preserves_sse_and_spa_routing(self) -> None:
        nginx = (self.ROOT / "infra/nginx/fuxiaohe.conf").read_text(encoding="utf-8")

        self.assertIn("proxy_buffering off", nginx)
        self.assertIn("try_files $uri $uri/ /index.html", nginx)
        self.assertIn("proxy_pass http://api:8000", nginx)

    def test_database_bootstrap_creates_required_extensions(self) -> None:
        database = (self.ROOT / "apps/api/database.py").read_text(encoding="utf-8")

        self.assertIn("CREATE EXTENSION IF NOT EXISTS vector", database)
        self.assertIn("CREATE EXTENSION IF NOT EXISTS pg_trgm", database)
        migration = (self.ROOT / "infra/migrations/042_embedding_dimension_1024.sql").read_text(encoding="utf-8")
        self.assertIn("vector(1024)", migration)

    def test_production_secret_template_is_not_trackable_as_runtime_env(self) -> None:
        gitignore = (self.ROOT / ".gitignore").read_text(encoding="utf-8")
        template = (self.ROOT / ".env.production.example").read_text(encoding="utf-8")

        self.assertIn(".env.*", gitignore)
        self.assertIn("! .env.production.example".replace(" ", ""), gitignore)
        self.assertIn("LLM_API_KEY=replace_with_chat_api_key", template)
        self.assertIn("PIP_DEFAULT_TIMEOUT=300", template)
        self.assertIn("WEB_BIND_ADDRESS=127.0.0.1", template)

    def test_api_image_allows_a_reliable_configurable_pip_download(self) -> None:
        dockerfile = (self.ROOT / "infra/docker/Dockerfile.api").read_text(encoding="utf-8")

        self.assertIn("ARG PIP_INDEX_URL=https://pypi.org/simple", dockerfile)
        self.assertIn("--timeout \"${PIP_DEFAULT_TIMEOUT}\"", dockerfile)
        self.assertIn("--retries \"${PIP_RETRIES}\"", dockerfile)


if __name__ == "__main__":
    unittest.main()
