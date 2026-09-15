from datetime import datetime, timedelta
import unittest
from uuid import UUID

from services.memory.conversation import (
    MessageSnapshot,
    assemble_conversation_context,
    group_turns,
)


def make_snapshots(items):
    start = datetime(2026, 1, 1)
    return [
        MessageSnapshot(
            id=UUID(int=index + 1),
            role=role,
            content=content,
            created_at=start + timedelta(seconds=index),
        )
        for index, (role, content) in enumerate(items)
    ]


def make_numbered_turns(count):
    return make_snapshots([
        item
        for number in range(1, count + 1)
        for item in (("user", f"问题 {number}"), ("assistant", f"回答 {number}"))
    ])


class ConversationContextTests(unittest.TestCase):
    def test_trimming_never_keeps_an_orphan_assistant_message(self):
        snapshots = make_snapshots([
            ("user", "旧问题"), ("assistant", "旧回答"),
            ("user", "新问题"), ("assistant", "新回答"),
            ("user", "最新追问"),
        ])

        context = assemble_conversation_context(
            snapshots, summary="更早内容摘要", recent_turn_limit=1, character_budget=40,
        )

        self.assertEqual(
            [(message.type, message.content) for message in context.messages],
            [("human", "新问题"), ("ai", "新回答"), ("human", "最新追问")],
        )

    def test_summary_candidates_exclude_recent_complete_turns(self):
        context = assemble_conversation_context(
            make_numbered_turns(8), summary="", recent_turn_limit=3,
            character_budget=12_000,
        )

        self.assertEqual(len(context.summary_candidates), 10)
        self.assertEqual(context.summary_candidates[-1].content, "回答 5")

    def test_grouping_leaves_the_latest_user_segment_pending(self):
        turns, pending = group_turns(make_snapshots([
            ("assistant", "不应成为轮次"),
            ("user", "先问"), ("user", "补充条件"), ("assistant", "完整回答"),
            ("user", "最新问题"), ("user", "最新补充"),
        ]))

        self.assertEqual(
            [snapshot.content for snapshot in turns[0].users],
            ["先问", "补充条件"],
        )
        self.assertEqual(turns[0].assistant.content, "完整回答")
        self.assertEqual([snapshot.content for snapshot in pending], ["最新问题", "最新补充"])

    def test_context_budget_counts_message_separators(self):
        context = assemble_conversation_context(
            make_snapshots([
                ("user", "one"), ("assistant", "two"), ("user", "three"),
            ]),
            summary="", recent_turn_limit=1, character_budget=13,
        )

        self.assertEqual(
            [(message.type, message.content) for message in context.messages],
            [("human", "three")],
        )

    def test_context_returns_summary_separately_when_it_fits_the_budget(self):
        context = assemble_conversation_context(
            make_snapshots([("user", "最新问题")]),
            summary="更早内容摘要", recent_turn_limit=1, character_budget=20,
        )

        self.assertEqual(context.summary, "更早内容摘要")
        self.assertEqual(
            [(message.type, message.content) for message in context.messages],
            [("human", "最新问题")],
        )

    def test_context_omits_separate_summary_when_the_combined_budget_is_insufficient(self):
        context = assemble_conversation_context(
            make_snapshots([("user", "最新问题")]),
            summary="更早内容摘要", recent_turn_limit=1, character_budget=9,
        )

        self.assertEqual(context.summary, "")
        self.assertEqual(
            [(message.type, message.content) for message in context.messages],
            [("human", "最新问题")],
        )


if __name__ == "__main__":
    unittest.main()
