import unittest
import uuid
from pathlib import Path

from apps.api.routes import profile
from packages.contracts.schemas import FriendRequest


class FriendshipContractTests(unittest.TestCase):
    def test_friend_request_requires_a_user_id(self):
        target_id = uuid.uuid4()
        request = FriendRequest(user_id=target_id)
        self.assertEqual(request.user_id, target_id)

    def test_only_friend_visibility_requires_an_accepted_friendship(self):
        self.assertFalse(profile._can_view_profile("仅好友", is_self=False, same_major=False))
        self.assertTrue(
            profile._can_view_profile(
                "仅好友",
                is_self=False,
                same_major=False,
                is_friend=True,
            )
        )

    def test_friendship_migration_and_router_are_present(self):
        root = Path(__file__).parents[1]
        migration = root / "infra" / "migrations" / "039_user_friendships.sql"
        source = (root / "apps" / "api" / "routes" / "friends.py").read_text(encoding="utf-8")

        self.assertTrue(migration.exists())
        self.assertIn("/friends/requests", source)
        self.assertIn("/friends/{friendship_id}/accept", source)
        self.assertIn("/friends/{friendship_id}", source)
