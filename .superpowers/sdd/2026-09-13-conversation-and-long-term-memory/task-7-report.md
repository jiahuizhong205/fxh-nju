# Task 7 Report: Maintain memories after successful chat responses

## Outcome

- Added `services.memory.maintenance.refresh_memory_state()` as the timeout-bounded, exception-containing background boundary.
- The inner maintenance flow refreshes the rolling summary, opens a fresh `async_session`, validates conversation ownership, reads the current account-level capture preference, loads only the committed latest user/assistant message pair, extracts from the user message, and upserts accepted candidates with the committed source IDs.
- Successful assistant persistence schedules exactly one Starlette `BackgroundTasks` item. Prompt-injection rejection, model failure, and assistant persistence failure schedule none.
- The chat route loads the bounded current-conversation summary and user-scoped long-term memories into `AssistantState`; disabling auto-capture keeps the summary but skips cross-conversation retrieval and extraction.
- Memory retrieval and maintenance failures degrade safely without replacing or appending an SSE error after a successful final event.
- New logs contain IDs, counts, booleans, elapsed time, timeout, and exception type only. They do not include message text, memory text, exception details, or secrets.
- Existing SSE event names/order and token streaming remain intact. The existing shared `mock_llm` and embedding behavior were not split into additional switches.

## TDD Evidence

### Initial RED

Command:

```powershell
python -m unittest tests.test_memory_maintenance tests.test_agent_resilience -v
```

Observed result before production changes: 9 tests ran with 2 expected errors. `services.memory.maintenance` did not exist, and `_stream_answer()` rejected the new committed-message/background-task arguments.

### Security logging RED

Command:

```powershell
python -m unittest tests.test_memory_maintenance.MemoryMaintenanceTests.test_failure_is_logged_without_escaping_background_boundary tests.test_chat_context_streaming.ChatContextTests.test_memory_retrieval_failure_degrades_without_logging_secret_details -v
```

Observed result before the logging fix: 2/2 tests failed because traceback logging exposed the sentinel secret and omitted the bounded `error_type` field.

### Focused GREEN

Command:

```powershell
python -m unittest tests.test_memory_maintenance tests.test_chat_context_streaming tests.test_agent_resilience -v
```

Result: 28 tests passed, 0 failures.

### Full Python verification

Command:

```powershell
python -m unittest discover -s tests -p 'test_*.py'
```

Result: 273 tests passed, 0 failures.

Additional checks:

```powershell
python -m compileall -q apps services tests
git diff --check
```

Both completed successfully; Git emitted only the repository's expected LF-to-CRLF checkout notices.

## Files Changed

- `services/memory/maintenance.py`
- `apps/api/routes/chat.py`
- `tests/test_memory_maintenance.py`
- `tests/test_chat_context_streaming.py`
- `tests/test_agent_resilience.py`
- `.superpowers/sdd/2026-09-13-conversation-and-long-term-memory/task-7-report.md`

## Self-review

- **Session lifecycle:** the request `AsyncSession` is never captured by the background callable. Summary refresh uses its existing independent session; maintenance opens and closes another fresh session. Message strings are copied before the read transaction is rolled back, and the store layer owns its commit/rollback.
- **Commit-before-schedule:** both user and assistant UUIDs are assigned before their respective commits, but the maintenance task is registered only after the assistant commit returns successfully.
- **Exactly once:** there is one `add_task()` call site after persistence. The streaming success test observes one queued task before executing it and verifies the exact four committed IDs passed to it.
- **Failure isolation:** injection rejection, graph/model failure, and persistence failure have explicit zero-task tests. Timeout and exception tests prove the public background boundary does not raise. An end-to-end stream/background test proves the final SSE survives maintenance failure.
- **Consent behavior:** a fresh background read observes preference changes made after the request began. Disabled capture still invokes summary maintenance, but it does not load messages for extraction or call the extractor/store. The request path also skips retrieval and supplies an empty `memory_context` while retaining `conversation_summary`.
- **User isolation:** retrieval receives the authenticated user UUID, existing Task 5 queries filter on that UUID, and background extraction first verifies `(conversation_id, user_id)` ownership before loading both source messages by exact ID, conversation, and role.
- **Streaming compatibility:** `stream_graph_events()` and its token queue were not changed; the final event remains the last SSE event on success, and background execution occurs only after the streaming body completes.
- External subagent review was not used because the task explicitly prohibited spawning subagents.

## Remaining Risks

- PostgreSQL/pgvector and external LLM/embedding providers were not available for a live integration run; SQL/session orchestration is covered with focused test doubles and the existing Task 3–5 suites.
- Starlette background execution order is covered through the real `BackgroundTasks` object and streaming generator, but not through a client-disconnect ASGI integration test.
- Timeout cancellation depends on the async database/provider stack responding cooperatively to cancellation; the outer boundary still prevents such failure from changing a completed SSE response.

## Commit

- Subject: `feat: maintain memories after chat responses`
- Branch: `codex/memory-system`
- This report is included in the task commit; the immutable hash is reported after commit creation.

---

## Fix round 1

### Findings addressed

- **Final-before-schedule lifecycle:** maintenance registration now occurs only when `StreamingResponse` resumes the async generator after successfully sending the final SSE chunk. A final serialization failure, or a consumer that never completes the final yield recovery, leaves the background task list empty. Normal full response consumption registers exactly one task before Starlette executes `BackgroundTasks`.
- **Write-time consent race:** after extraction, maintenance starts a new transaction, re-reads `User.preferences` with `FOR UPDATE`, and keeps that row lock until the memory upsert commits. If auto-capture was disabled while extraction ran, the candidates are counted for safe telemetry but discarded without calling upsert; the already-completed summary refresh remains valid.
- **Safe retrieval telemetry logs:** usage telemetry failure logs now contain only `operation=mark_used`, `user_id`, count, and exception type. Tracebacks and exception text are omitted, while retrieval still returns the selected memories.

### RED evidence

Final lifecycle:

```powershell
python -m unittest tests.test_chat_context_streaming.ChatContextTests.test_successful_full_consumption_schedules_once_after_final_yield tests.test_chat_context_streaming.ChatContextTests.test_final_serialization_failure_schedules_no_maintenance -v
```

Result before implementation: 2/2 failed. A task was already present while the generator was suspended at the final yield, and final serialization failure still left one queued task.

Write-time consent:

```powershell
python -m unittest tests.test_memory_maintenance.MemoryMaintenanceTests.test_capture_disabled_during_extraction_abandons_write_after_locked_recheck -v
```

Result before implementation: 1/1 failed because upsert was awaited after the simulated preference changed from enabled to disabled.

Telemetry logging:

```powershell
python -m unittest tests.test_memory_retrieval.MemoryRetrievalTests.test_telemetry_failure_does_not_discard_retrieval_result -v
```

Result before implementation: 1/1 failed because the log omitted the operation/error-type fields and included a traceback containing the sentinel secret.

### GREEN verification

Task 7 focused suite:

```powershell
python -m unittest tests.test_memory_maintenance tests.test_chat_context_streaming tests.test_agent_resilience tests.test_memory_retrieval -v
```

Result: 43 tests passed, 0 failures.

Full Python suite:

```powershell
python -m unittest discover -s tests -p 'test_*.py'
```

Result: 275 tests passed, 0 failures.

`python -m compileall -q apps services tests` and `git diff --check` also completed successfully; Git emitted only expected LF-to-CRLF checkout notices.

### Fix-round self-review

- The final SSE payload is constructed and serialized before the yield. Code after the yield is unreachable on serialization failure and runs only after the response iterator resumes, matching normal Starlette streaming/background order.
- The unique scheduling call site remains guarded by successful assistant persistence, non-injection input, valid committed IDs, and an attached `BackgroundTasks` object. Existing injection, model-failure, and persistence-failure zero-task tests remain green.
- The pre-extraction transaction is explicitly rolled back before the potentially slow model operation. The post-extraction `SELECT ... FOR UPDATE` therefore starts a new transaction and locks the user preference row through `upsert_memory_candidates()`'s commit.
- A preference update committed during extraction is observed and prevents the write. If maintenance acquires the lock first, a concurrent preference update linearizes after the memory commit rather than racing between recheck and upsert.
- The summary refresh order was intentionally not changed; the review's ownership-before-summary Minor remains outside this fix round.
- Retrieval telemetry still detaches returned ORM rows and rolls back the failed telemetry transaction before logging and returning them.
- No Mock LLM/embedding switch, SSE event name, prompt context shape, retrieval ranking, or memory candidate safety rule changed.

### Remaining risks after fix round 1

- `FOR UPDATE` provides the intended row-lock semantics on the production PostgreSQL database; SQLite test environments ignore row-level locking, so the exact concurrent blocking behavior still requires live PostgreSQL validation.
- If a client disconnects immediately after receiving the final bytes but before Starlette resumes the generator, maintenance is intentionally not registered. This favors the invariant that only normally completed response iteration schedules maintenance.
- PostgreSQL/pgvector and external LLM/embedding providers were not available for a live end-to-end run.

### Fix commit

- Subject: `fix: harden post-response memory maintenance`
- Branch: `codex/memory-system`
- The immutable hash is reported in the fix-round completion message.
