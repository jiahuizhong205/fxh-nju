import unittest
from pathlib import Path
from unittest.mock import Mock, patch


class LlmProviderConfigTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_real_provider_fields_are_explicit_and_local_model_is_not_defaulted(self):
        from apps.api.config import Settings

        configured = Settings(_env_file=None)
        self.assertTrue(configured.mock_llm)
        self.assertEqual(configured.llm_base_url, "")
        self.assertEqual(configured.embedding_base_url, "")
        self.assertEqual(configured.embedding_api_key, "")
        self.assertEqual(configured.embedding_api_dimensions, 0)
        self.assertEqual(configured.embedding_dimension, 384)

    def test_embedding_api_uses_its_own_endpoint_key_and_dimension(self):
        from services.rag import retrieval

        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"data": [{"embedding": [0.25] * 384}]}
        with (
            patch.object(retrieval.settings, "embedding_base_url", "https://embedding.example/v1/"),
            patch.object(retrieval.settings, "embedding_api_key", "embedding-secret"),
            patch.object(retrieval.settings, "embedding_api_model", "embedding-model"),
            patch.object(retrieval.settings, "embedding_api_dimensions", 384),
            patch.object(retrieval.settings, "embedding_dimension", 384),
            patch("services.rag.retrieval.httpx.post", return_value=response) as post,
        ):
            vector = retrieval._embed_via_api("测试")

        self.assertEqual(len(vector), 384)
        self.assertEqual(post.call_args.args[0], "https://embedding.example/v1/embeddings")
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer embedding-secret")
        self.assertEqual(post.call_args.kwargs["json"]["dimensions"], 384)

    def test_embedding_api_omits_optional_dimensions_for_generic_providers(self):
        from services.rag import retrieval

        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"data": [{"embedding": [0.25] * 384}]}
        with (
            patch.object(retrieval.settings, "embedding_base_url", "https://embedding.example/v1"),
            patch.object(retrieval.settings, "embedding_api_key", "embedding-secret"),
            patch.object(retrieval.settings, "embedding_api_model", "embedding-model"),
            patch.object(retrieval.settings, "embedding_api_dimensions", 0),
            patch.object(retrieval.settings, "embedding_dimension", 384),
            patch("services.rag.retrieval.httpx.post", return_value=response) as post,
        ):
            retrieval._embed_via_api("测试")

        self.assertNotIn("dimensions", post.call_args.kwargs["json"])

    def test_embedding_dimension_mismatch_fails_instead_of_silently_hashing(self):
        from services.rag import retrieval

        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"data": [{"embedding": [0.25] * 3}]}
        with (
            patch.object(retrieval.settings, "embedding_base_url", "https://embedding.example/v1"),
            patch.object(retrieval.settings, "embedding_api_key", "embedding-secret"),
            patch.object(retrieval.settings, "embedding_dimension", 384),
            patch("services.rag.retrieval.httpx.post", return_value=response),
        ):
            with self.assertRaisesRegex(ValueError, "向量维度"):
                retrieval._embed_via_api("测试")

    def test_readiness_and_reindex_workflow_are_exposed(self):
        main = (self.ROOT / "apps/api/main.py").read_text(encoding="utf-8")
        compose = (self.ROOT / "infra/compose/docker-compose.yml").read_text(encoding="utf-8")
        env_example = (self.ROOT / ".env.example").read_text(encoding="utf-8")
        reindex = self.ROOT / "scripts/reembed_documents.py"
        preflight = self.ROOT / "scripts/check_external_llm.py"
        dockerignore = (self.ROOT / ".dockerignore").read_text(encoding="utf-8")

        self.assertIn('@app.get("/api/readiness")', main)
        self.assertIn("EMBEDDING_BASE_URL", compose)
        self.assertIn("LLM_API_KEY", compose)
        self.assertIn("EMBEDDING_API_KEY=", env_example)
        self.assertTrue(reindex.exists())
        self.assertTrue(preflight.exists())
        self.assertIn("embedding 连通性检查", preflight.read_text(encoding="utf-8"))
        self.assertIn(".env", dockerignore.splitlines())

    def test_agents_are_scoped_to_authenticated_user_and_database_data(self):
        chat = (self.ROOT / "apps/api/routes/chat.py").read_text(encoding="utf-8")
        state = (self.ROOT / "services/agent_runtime/state.py").read_text(encoding="utf-8")
        agents = "\n".join(
            (self.ROOT / f"services/agent_runtime/{name}").read_text(encoding="utf-8")
            for name in ("recommend_agent.py", "plan_agent.py", "tutor_agent.py", "career_agent.py")
        )

        self.assertIn('"user_id": str(user_id)', chat)
        self.assertIn("user_id: str", state)
        self.assertGreaterEqual(agents.count("StudentProfile.user_id == state.get(\"user_id\")"), 4)
        self.assertNotIn("PROGRAM_PLANS", agents)
        self.assertNotIn("match_jobs(major, minor)", agents)


if __name__ == "__main__":
    unittest.main()
