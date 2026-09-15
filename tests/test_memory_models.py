import unittest

from sqlalchemy import Integer, UniqueConstraint

from apps.api.config import Settings
from apps.api.models import ConversationSummary, UserMemory
from apps.api.routes.preferences import MemoryPreferences, PreferencesData, _SECTION_MODELS


class MemoryModelContractTests(unittest.TestCase):
    def test_conversation_summary_is_one_row_per_conversation_with_revision_cursor(self):
        self.assertEqual(ConversationSummary.__tablename__, "conversation_summaries")
        columns = ConversationSummary.__table__.c

        self.assertEqual(
            set(columns.keys()),
            {
                "conversation_id",
                "summary",
                "summarized_through_message_id",
                "revision",
                "created_at",
                "updated_at",
            },
        )
        self.assertTrue(columns.conversation_id.primary_key)
        self.assertFalse(columns.conversation_id.nullable)
        conversation_foreign_key = next(iter(columns.conversation_id.foreign_keys))
        self.assertEqual(conversation_foreign_key.column.table.name, "conversations")
        self.assertEqual(conversation_foreign_key.ondelete, "CASCADE")
        self.assertTrue(columns.summarized_through_message_id.nullable)
        cursor_foreign_key = next(iter(columns.summarized_through_message_id.foreign_keys))
        self.assertEqual(cursor_foreign_key.column.table.name, "messages")
        self.assertEqual(cursor_foreign_key.ondelete, "SET NULL")
        self.assertIsInstance(columns.revision.type, Integer)
        self.assertFalse(columns.revision.nullable)
        self.assertEqual(columns.revision.default.arg, 0)
        self.assertFalse(columns.created_at.nullable)
        self.assertFalse(columns.updated_at.nullable)

    def test_user_memory_captures_source_lifecycle_and_deduplication_contracts(self):
        self.assertEqual(UserMemory.__tablename__, "user_memories")
        columns = UserMemory.__table__.c
        self.assertEqual(
            set(columns.keys()),
            {
                "id",
                "user_id",
                "canonical_key",
                "category",
                "content",
                "importance",
                "confidence",
                "source_message_id",
                "source_conversation_id",
                "embedding",
                "embedding_provider",
                "last_used_at",
                "created_at",
                "updated_at",
            },
        )
        memory_foreign_keys = {
            foreign_key.column.table.name: foreign_key.ondelete
            for column in columns
            for foreign_key in column.foreign_keys
        }
        self.assertEqual(memory_foreign_keys["users"], "CASCADE")
        self.assertEqual(memory_foreign_keys["messages"], "SET NULL")
        self.assertEqual(memory_foreign_keys["conversations"], "SET NULL")
        self.assertTrue(columns.source_message_id.nullable)
        self.assertTrue(columns.source_conversation_id.nullable)
        self.assertTrue(columns.last_used_at.nullable)
        self.assertFalse(columns.importance.nullable)
        self.assertFalse(columns.embedding_provider.nullable)
        self.assertEqual(columns.embedding.type.dim, 1024)
        self.assertTrue(
            any(
                isinstance(constraint, UniqueConstraint)
                and [column.name for column in constraint.columns] == ["user_id", "canonical_key"]
                for constraint in UserMemory.__table__.constraints
            )
        )

    def test_memory_settings_defaults_match_context_budget_contract(self):
        settings = Settings()

        self.assertEqual(settings.chat_recent_turn_limit, 5)
        self.assertEqual(settings.chat_context_character_budget, 12_000)
        self.assertEqual(settings.chat_summary_trigger_character_count, 8_000)
        self.assertEqual(settings.chat_summary_max_characters, 2_400)
        self.assertEqual(settings.memory_retrieval_limit, 5)
        self.assertEqual(settings.memory_context_character_budget, 2_000)
        self.assertEqual(settings.memory_capture_confidence_threshold, 0.70)
        self.assertEqual(settings.memory_background_timeout_seconds, 45.0)

    def test_memory_preferences_default_to_enabled(self):
        data = PreferencesData()

        self.assertIsInstance(data.memory, MemoryPreferences)
        self.assertTrue(data.memory.auto_capture_enabled)
        self.assertIs(_SECTION_MODELS["memory"], MemoryPreferences)


if __name__ == "__main__":
    unittest.main()
