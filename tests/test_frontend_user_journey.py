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

    def test_avatar_is_uploaded_and_shared_across_primary_pages(self):
        client = (ROOT / "apps/web/src/api/client.ts").read_text(encoding="utf-8")
        edit_profile = (ROOT / "apps/web/src/views/EditProfileView.vue").read_text(encoding="utf-8")
        home = (ROOT / "apps/web/src/views/HomeView.vue").read_text(encoding="utf-8")
        profile = (ROOT / "apps/web/src/views/ProfileView.vue").read_text(encoding="utf-8")

        self.assertIn("export async function uploadAvatar", client)
        self.assertIn("export async function fetchAvatar", client)
        self.assertIn("await avatarStore.upload(avatarFile.value)", edit_profile)
        self.assertIn(':src="avatarStore.avatarUrl"', home)
        self.assertIn(':src="avatarStore.avatarUrl"', profile)
        self.assertNotIn('src="/illustrations/avatar-wreath.png"', home)
        self.assertNotIn('src="/illustrations/avatar-wreath.png"', profile)

    def test_primary_dashboard_uses_server_progress_participants_and_favorites(self):
        client = (ROOT / "apps/web/src/api/client.ts").read_text(encoding="utf-8")
        home = (ROOT / "apps/web/src/views/HomeView.vue").read_text(encoding="utf-8")
        profile = (ROOT / "apps/web/src/views/ProfileView.vue").read_text(encoding="utf-8")
        career = (ROOT / "apps/web/src/views/CareerView.vue").read_text(encoding="utf-8")

        self.assertIn("fetchLearningProgress", client)
        self.assertIn("fetchFavoriteJobIds", client)
        self.assertIn("participant_count", home)
        self.assertNotIn("已有 234 名", home)
        self.assertIn("fetchLearningProgress()", profile)
        self.assertNotIn("const harvestedCredits = 28", profile)
        self.assertNotIn("120 天", profile)
        self.assertIn("fetchFavoriteJobIds()", career)
        self.assertNotIn("fxh_favorite_jobs", client)

    def test_memory_settings_route_entry_and_typed_client_contract_exist(self):
        router = (ROOT / "apps/web/src/router/index.ts").read_text(encoding="utf-8")
        settings = (ROOT / "apps/web/src/views/SettingsView.vue").read_text(encoding="utf-8")
        client = (ROOT / "apps/web/src/api/client.ts").read_text(encoding="utf-8")

        self.assertIn("/settings/memory", router)
        self.assertIn("MemorySettingsView.vue", router)
        self.assertIn("我的记忆", settings)
        self.assertIn("export type MemoryCategory", client)
        self.assertIn("export interface MemoryPage", client)
        self.assertIn("next_cursor: string | null", client)
        for method in [
            "fetchMemories",
            "createMemory",
            "updateMemory",
            "deleteMemory",
            "fetchMemoryPreferences",
            "saveMemoryPreferences",
        ]:
            self.assertIn(f"export async function {method}", client)

    def test_memory_settings_page_exposes_safe_accessible_states(self):
        page = (ROOT / "apps/web/src/views/MemorySettingsView.vue").read_text(encoding="utf-8")
        state = (ROOT / "apps/web/src/views/memorySettingsState.ts").read_text(encoding="utf-8")

        for text in [
            "自动记忆",
            "添加记忆",
            "编辑",
            "删除",
            "还没有形成长期记忆",
            "请勿保存密码、验证码、访问令牌或其他凭证",
            "aria-live",
            "aria-checked",
            "加载更多",
            "confirm(",
            "prefers-reduced-motion",
            "retryPreferences",
            ":deep(.back)",
        ]:
            self.assertIn(text, page)

    def test_memory_settings_uses_dialog_field_errors_and_separate_pagination_recovery(self):
        page = (ROOT / "apps/web/src/views/MemorySettingsView.vue").read_text(encoding="utf-8")
        state = (ROOT / "apps/web/src/views/memorySettingsState.ts").read_text(encoding="utf-8")
        client = (ROOT / "apps/web/src/api/client.ts").read_text(encoding="utf-8")

        for markup in [
            '<dialog',
            '@cancel="onDialogCancel"',
            '@close="onDialogClosed"',
            'required',
            'aria-invalid',
            'memory-content-error',
            '状态未知',
            'initialListError',
            'appendError',
            '重试加载更多',
            'runConfirmedMemoryDelete',
            'if (categoryField.value)',
            'showMemoryDialog',
            'closeMemoryDialog',
            'syncMemoryAfterSave',
        ]:
            self.assertIn(markup, page)
        self.assertIn('showModal', state)
        self.assertIn('dialog.close()', state)
        self.assertIn("created_at: string", client)
        self.assertIn("class MemoryApiError", client)
        self.assertIn("memoryJsonResponse", client)

    def test_memory_dialog_keeps_keyboard_focus_inside_and_resets_pagination_errors_after_save(self):
        page = (ROOT / "apps/web/src/views/MemorySettingsView.vue").read_text(encoding="utf-8")

        for contract in [
            '@keydown="onDialogKeydown"',
            'trapDialogTabFocus',
            'restoreDialogTrigger',
            'appendError.value = nextAppendError(false, appendError.value)',
            '.form-card::backdrop',
        ]:
            self.assertIn(contract, page)

    def test_memory_add_button_uses_the_list_coordinator_gate_and_save_invalidates_pending_loads(self):
        page = (ROOT / "apps/web/src/views/MemorySettingsView.vue").read_text(encoding="utf-8")

        for contract in [
            'const listCoordinator = createMemoryListCoordinator()',
            'const canAddMemory = computed(() => listCoordinator.canAdd(initialLoading.value, initialListError.value))',
            ':disabled="!canAddMemory || formSaving || !!deletingId"',
            ':aria-disabled="!canAddMemory || formSaving || !!deletingId"',
            'listCoordinator.invalidateForSave()',
            'const stableList = listCoordinator.stableAfterSave()',
            'loadingMore.value = stableList.loadingMore',
            'if (!listCoordinator.isCurrent(request)) return',
            'if (listCoordinator.isCurrent(request)) append ? loadingMore.value = false : initialLoading.value = false',
        ]:
            self.assertIn(contract, page)
