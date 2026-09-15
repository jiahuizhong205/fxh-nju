import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class MemoryFrontendRuntimeTests(unittest.TestCase):
    def run_node(self, source: str) -> dict:
        result = subprocess.run(
            ["node", "--experimental-strip-types", "--input-type=module", "-e", source],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_memory_client_builds_requests_unwraps_preferences_and_keeps_safe_status(self):
        client_url = (ROOT / "apps/web/src/api/client.ts").as_uri()
        source = f"""
          globalThis.localStorage = {{ getItem: () => 'test-token' }}
          const calls = []
          const responses = [
            {{ ok: true, status: 200, json: async () => ({{ items: [], next_cursor: 'next' }}) }},
            {{ ok: true, status: 201, json: async () => ({{ id: 'm1' }}) }},
            {{ ok: true, status: 200, json: async () => ({{ id: 'm1', category: 'career_goal' }}) }},
            {{ ok: true, status: 204, json: async () => ({{}}) }},
            {{ ok: true, status: 200, json: async () => ({{ preferences: {{ auto_capture_enabled: false }} }}) }},
            {{ ok: true, status: 200, json: async () => ({{ preferences: {{ auto_capture_enabled: true }} }}) }},
            {{ ok: false, status: 422, json: async () => ({{ detail: 'private server body' }}) }},
          ]
          globalThis.fetch = async (url, init = {{}}) => {{ calls.push({{ url, init }}); return responses.shift() }}
          const client = await import('{client_url}')
          const page = await client.fetchMemories('learning_goal', 'a+b/c=')
          await client.createMemory({{ category: 'career_goal', content: 'safe text', importance: .7 }})
          await client.updateMemory('m/1', {{ importance: .9 }})
          await client.deleteMemory('m/1')
          const preferences = await client.fetchMemoryPreferences()
          const savedPreferences = await client.saveMemoryPreferences({{ auto_capture_enabled: true }})
          let error
          try {{ await client.createMemory({{ category: 'career_goal', content: 'x', importance: .7 }}) }} catch (caught) {{ error = {{ status: caught.status, message: caught.message }} }}
          console.log(JSON.stringify({{ calls, page, preferences, savedPreferences, error }}))
        """
        result = self.run_node(source)

        self.assertEqual(result["calls"][0]["url"], "/api/v1/memories?category=learning_goal&cursor=a%2Bb%2Fc%3D")
        self.assertEqual(result["calls"][0]["init"]["headers"]["Authorization"], "Bearer test-token")
        self.assertEqual(result["calls"][1]["init"]["method"], "POST")
        self.assertEqual(json.loads(result["calls"][1]["init"]["body"]), {
            "category": "career_goal", "content": "safe text", "importance": 0.7,
        })
        self.assertEqual(result["calls"][2]["url"], "/api/v1/memories/m%2F1")
        self.assertEqual(result["calls"][2]["init"]["method"], "PATCH")
        self.assertEqual(json.loads(result["calls"][2]["init"]["body"]), {"importance": 0.9})
        self.assertEqual(result["calls"][3]["init"]["method"], "DELETE")
        self.assertEqual(result["calls"][5]["init"]["method"], "PUT")
        self.assertEqual(json.loads(result["calls"][5]["init"]["body"]), {"auto_capture_enabled": True})
        self.assertEqual(result["page"]["next_cursor"], "next")
        self.assertFalse(result["preferences"]["auto_capture_enabled"])
        self.assertTrue(result["savedPreferences"]["auto_capture_enabled"])
        self.assertEqual(result["error"]["status"], 422)
        self.assertTrue(result["error"]["message"])
        self.assertNotEqual(result["error"]["message"], "private server body")

    def test_memory_state_rejects_stale_list_results_disables_unknown_preference_and_skips_cancelled_delete(self):
        state_url = (ROOT / "apps/web/src/views/memorySettingsState.ts").as_uri()
        source = f"""
          const state = await import('{state_url}')
          const requests = state.createLatestRequestGuard()
          const first = requests.begin()
          const second = requests.begin()
          const initial = state.initialMemoryPreferenceState()
          const failed = state.memoryPreferenceReadFailed(initial)
          const loaded = state.memoryPreferenceLoaded(failed, true)
          let deletes = 0
          const cancelled = await state.runConfirmedMemoryDelete(() => false, async () => {{ deletes += 1 }})
          console.log(JSON.stringify({{
            firstIsStale: !requests.isCurrent(first),
            secondIsCurrent: requests.isCurrent(second),
            failed,
            loaded,
            cancelled,
            deletes,
          }}))
        """
        result = self.run_node(source)

        self.assertTrue(result["firstIsStale"])
        self.assertTrue(result["secondIsCurrent"])
        self.assertEqual(result["failed"], {"value": None, "loading": False, "readFailed": True})
        self.assertEqual(result["loaded"], {"value": True, "loading": False, "readFailed": False})
        self.assertFalse(result["cancelled"])
        self.assertEqual(result["deletes"], 0)

    def test_memory_state_syncs_saved_rows_clears_stale_pagination_error_and_uses_native_dialog_order(self):
        state_url = (ROOT / "apps/web/src/views/memorySettingsState.ts").as_uri()
        source = f"""
          const state = await import('{state_url}')
          const rows = [
            {{ id: 'one', category: 'learning_goal' }},
            {{ id: 'two', category: 'career_goal' }},
          ]
          const created = state.syncMemoryAfterSave(rows, {{ id: 'new', category: 'learning_goal' }}, 'learning_goal')
          const moved = state.syncMemoryAfterSave(created, {{ id: 'two', category: 'career_goal' }}, 'learning_goal')
          const events = []
          const dialog = {{ open: false, showModal() {{ this.open = true; events.push('show') }}, close() {{ this.open = false; events.push('close') }} }}
          state.showMemoryDialog(dialog, () => events.push('focus-first'))
          state.closeMemoryDialog(dialog, () => events.push('restore-trigger'))
          console.log(JSON.stringify({{
            created: created.map(row => row.id),
            moved: moved.map(row => row.id),
            clearOnFullLoad: state.nextAppendError(false, 'old append failure'),
            keepOnAppendLoad: state.nextAppendError(true, 'old append failure'),
            events,
            open: dialog.open,
          }}))
        """
        result = self.run_node(source)

        self.assertEqual(result["created"], ["new", "one", "two"])
        self.assertEqual(result["moved"], ["new", "one"])
        self.assertEqual(result["clearOnFullLoad"], "")
        self.assertEqual(result["keepOnAppendLoad"], "old append failure")
        self.assertEqual(result["events"], ["show", "focus-first", "close", "restore-trigger"])
        self.assertFalse(result["open"])

    def test_memory_state_cycles_dialog_focus_restores_a_missing_trigger_and_appends_the_retry_cursor(self):
        state_url = (ROOT / "apps/web/src/views/memorySettingsState.ts").as_uri()
        source = f"""
          const state = await import('{state_url}')
          const events = []
          const first = {{ focus() {{ events.push('first') }} }}
          const middle = {{ focus() {{ events.push('middle') }} }}
          const last = {{ focus() {{ events.push('last') }} }}
          const forward = {{ key: 'Tab', shiftKey: false, preventDefault() {{ events.push('prevent-forward') }} }}
          const backward = {{ key: 'Tab', shiftKey: true, preventDefault() {{ events.push('prevent-backward') }} }}
          state.trapDialogTabFocus(forward, [first, middle, last], last)
          state.trapDialogTabFocus(backward, [first, middle, last], first)
          state.restoreDialogTrigger({{ isConnected: false, focus() {{ events.push('stale-trigger') }} }}, {{ focus() {{ events.push('fallback-add') }} }})
          const retryCursor = state.appendRequestCursor('original-retry-cursor')
          const appended = state.appendMemoryPage(
            [{{ id: 'one', category: 'learning_goal' }}],
            {{ items: [{{ id: 'two', category: 'learning_goal' }}], next_cursor: 'original-retry-cursor' }},
          )
          console.log(JSON.stringify({{ events, retryCursor, appended, clearAfterSave: state.nextAppendError(false, 'old append failure') }}))
        """
        result = self.run_node(source)

        self.assertEqual(result["events"], ["prevent-forward", "first", "prevent-backward", "last", "fallback-add"])
        self.assertEqual(result["retryCursor"], "original-retry-cursor")
        self.assertEqual(result["appended"], {
            "rows": [
                {"id": "one", "category": "learning_goal"},
                {"id": "two", "category": "learning_goal"},
            ],
            "nextCursor": "original-retry-cursor",
        })
        self.assertEqual(result["clearAfterSave"], "")

    def test_memory_list_coordinator_blocks_add_until_success_and_invalidates_a_delayed_load_before_save(self):
        state_url = (ROOT / "apps/web/src/views/memorySettingsState.ts").as_uri()
        source = f"""
          const state = await import('{state_url}')
          const coordinator = state.createMemoryListCoordinator()
          const oldRequest = coordinator.begin()
          let resolveList
          const delayedList = new Promise(resolve => {{ resolveList = resolve }})
          const beforeLoad = coordinator.canAdd(true, '')
          const afterError = coordinator.canAdd(false, '加载失败')
          const afterSuccess = coordinator.canAdd(false, '')
          coordinator.invalidateForSave()
          resolveList({{ items: [{{ id: 'stale' }}] }})
          const staleResponse = await delayedList
          const afterSave = coordinator.stableAfterSave()
          console.log(JSON.stringify({{
            beforeLoad,
            afterError,
            afterSuccess,
            staleCanApply: coordinator.isCurrent(oldRequest),
            staleResponse,
            afterSave,
          }}))
        """
        result = self.run_node(source)

        self.assertFalse(result["beforeLoad"])
        self.assertFalse(result["afterError"])
        self.assertTrue(result["afterSuccess"])
        self.assertFalse(result["staleCanApply"])
        self.assertEqual(result["staleResponse"], {"items": [{"id": "stale"}]})
        self.assertEqual(result["afterSave"], {
            "initialLoading": False,
            "initialListError": "",
            "appendError": "",
            "loadingMore": False,
        })
