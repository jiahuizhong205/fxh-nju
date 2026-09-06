import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class FrontendUserJourneyContractTests(unittest.TestCase):
    def test_registration_routes_by_server_onboarding_state(self):
        login = (ROOT / "apps/web/src/views/LoginView.vue").read_text(encoding="utf-8")
        client = (ROOT / "apps/web/src/api/client.ts").read_text(encoding="utf-8")

        self.assertIn("onboarding_completed: boolean", client)
        self.assertIn("res.user.onboarding_completed", login)
        self.assertIn("至少 8 位且包含字母和数字", login)

    def test_onboarding_completion_is_saved_to_backend(self):
        onboarding = (ROOT / "apps/web/src/views/InterestSelectionView.vue").read_text(encoding="utf-8")

        self.assertIn("updateOnboardingStatus(true)", onboarding)
        self.assertNotIn("fxh_onboarding_complete", onboarding)

    def test_profile_options_are_loaded_from_shared_backend_dictionary(self):
        client = (ROOT / "apps/web/src/api/client.ts").read_text(encoding="utf-8")
        onboarding = (ROOT / "apps/web/src/views/InterestSelectionView.vue").read_text(encoding="utf-8")
        edit_profile = (ROOT / "apps/web/src/views/EditProfileView.vue").read_text(encoding="utf-8")

        self.assertIn("fetchProfileOptions", client)
        self.assertIn("fetchProfileOptions()", onboarding)
        self.assertIn("fetchProfileOptions()", edit_profile)
