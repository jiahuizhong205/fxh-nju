# Task 5 report — store, deduplicate, retrieve, and format memories

## Outcome

- Added transactional, user-scoped candidate upsert, manual update, and hard delete.
- Added canonical-key overwrite, deterministic Mock text/category deduplication, and real embedding cosine deduplication within the same category.
- Added mode-aware retrieval: Mock keyword/category/importance/freshness ranking and real pgvector candidate retrieval followed by combined semantic/importance/freshness/last-use/intent ranking.
- Added a single user-scoped `last_used_at` telemetry update whose failure does not discard or expire returned retrieval rows.
- Added bounded JSON-line memory context with an explicit “未经验证的用户背景” warning and fail-closed credential/prompt-injection filtering.
- Fixed the carried Task 4 safety breaker: a non-token ASCII period between adjacent CJK characters is now a sentence boundary, without splitting URL, email, decimal, or JWT token periods.

## TDD evidence

### RED

1. Carried privacy breaker:

   ```powershell
   python -m unittest tests.test_memory_extraction.MemoryExtractionTests.test_mock_scopes_consent_across_cjk_ascii_period_boundary tests.test_memory_extraction.MemoryExtractionTests.test_real_provider_scopes_consent_across_cjk_ascii_period_boundary -v
   ```

   Result: 2 tests ran, 2 expected assertion failures. Both Mock and provider paths accepted a candidate whose explicit consent leaked across `课程.我的手机号`.

2. Task 5 modules:

   ```powershell
   python -m unittest tests.test_memory_store tests.test_memory_retrieval -v
   ```

   Result: 2 loader errors, as expected, because `services.memory.store` and `services.memory.retrieval` did not exist.

3. Self-review regressions:

   ```powershell
   python -m unittest tests.test_memory_retrieval.MemoryRankingTests.test_real_ranking_accepts_vector_types_with_ambiguous_truth_value tests.test_memory_retrieval.MemoryRetrievalTests.test_telemetry_rollback_keeps_returned_orm_content_readable tests.test_memory_retrieval.MemoryFormattingTests.test_formatter_respects_total_character_budget -v
   ```

   Result: 3 tests ran, 3 expected errors: ambiguous vector truth evaluation, ORM expiration after telemetry rollback, and truncated invalid JSON.

### GREEN

1. Privacy regression plus preserved token/punctuation behavior:

   ```powershell
   python -m unittest tests.test_memory_extraction.MemoryExtractionTests.test_mock_scopes_consent_across_cjk_ascii_period_boundary tests.test_memory_extraction.MemoryExtractionTests.test_real_provider_scopes_consent_across_cjk_ascii_period_boundary tests.test_memory_extraction.MemoryExtractionTests.test_sentence_splitter_preserves_internal_english_periods tests.test_memory_extraction.MemoryExtractionTests.test_full_jwt_fails_closed_before_mock_or_provider_extraction tests.test_memory_extraction.MemoryExtractionTests.test_consecutive_terminal_marks_remain_one_question_sentence -v
   ```

   Result: 5/5 passed.

2. Task 5 focused tests after implementation:

   ```powershell
   python -m unittest tests.test_memory_store tests.test_memory_retrieval -v
   ```

   Result: 21/21 passed.

3. Planned focused matrix plus carried extraction safety:

   ```powershell
   python -m unittest tests.test_memory_extraction tests.test_memory_store tests.test_memory_retrieval tests.test_backend_contracts -v
   ```

   Result: 170/170 passed.

4. Full Python suite:

   ```powershell
   python -m unittest discover -s tests -p 'test_*.py'
   ```

   Result: 245/245 passed.

## Modified files

- `services/memory/extraction.py`
- `services/memory/store.py`
- `services/memory/retrieval.py`
- `tests/test_memory_extraction.py`
- `tests/test_memory_store.py`
- `tests/test_memory_retrieval.py`
- `.superpowers/sdd/2026-09-13-conversation-and-long-term-memory/task-5-report.md`

## Self-review

### Transaction boundaries

- `upsert_memory_candidates()` prepares and embeds all accepted candidates before database access, applies all row changes, and commits once; any persistence error rolls back the whole batch.
- `update_user_memory()` embeds changed real-mode content before database access and commits or rolls back as one unit.
- `delete_user_memory()` performs one hard `DELETE` for the owning user, so body and vector disappear in the same transaction.

### User isolation

- Every store/retrieval select, update, and delete predicate includes `UserMemory.user_id == user_id`.
- Canonical-key matching and same-category semantic matching are both restricted to the current user.
- The usage telemetry statement is restricted by both user ID and the returned memory IDs.

### Mock and real branches

- Mock writes keep `embedding=None` and `embedding_provider=""`; Mock retrieval never calls `embed_text()` and only uses deterministic textual/category/importance/freshness features.
- Real writes and queries call `embed_text()` through `asyncio.to_thread()` before database work.
- Real vector candidates require the active `embedding_signature()` and are initially ordered by pgvector cosine distance before combined ranking.

### Safety and formatting

- Store and update paths re-run credential/personal-sensitive sanitization instead of trusting upstream extraction.
- The formatter rejects credentials, fake role labels, tool/function call markers, and common Chinese/English prompt-injection instructions.
- Each emitted memory is a complete JSON object; both the warning and entries count toward the total character budget.
- Logging is limited to user ID, result count, and exception metadata; no complete memory text is logged.

## Remaining risks

- The pgvector `<=>` query was compiled against the PostgreSQL dialect and unit-tested around its ranking boundary, but no live PostgreSQL/pgvector service or external embedding provider was available in this task run.
- The semantic duplicate threshold (`0.92`) and score weights are deterministic implementation constants that may need production tuning with representative usage data.
- Concurrent inserts for a previously absent identical canonical key rely on the database unique constraint; a losing transaction fails closed and can be retried by the later maintenance cycle.

## Commit

- Subject: `feat: store and retrieve user memories`
- This report ships in that commit; its immutable hash is reported in the task completion message because a commit cannot contain its own final hash.

---

## Fix round 1

### Findings addressed

- **Critical — span-aware ASCII sentence stops:** replaced the adjacent-CJK-only rule with explicit protected spans for JWT/dotted ASCII tokens, Unicode email addresses, ASCII/IDN URLs, and decimal numbers. A period outside those spans now ends a sentence when the next character begins CJK text, regardless of the preceding character.
- **Important — embedding migration fallback:** real retrieval still computes cosine similarity only for rows with the active embedding signature, while NULL-vector and stale-signature rows are loaded through a separate user-scoped fallback query and ranked by keywords, category, importance, and freshness. The two sources are deterministically merged, deduplicated by memory ID, and limited.
- **Important — concurrent first upsert:** PostgreSQL upserts now acquire transaction-scoped advisory locks for each sorted `(user, category)` key before any memory query, including the empty-set case. New rows use atomic `ON CONFLICT (user_id, canonical_key) DO UPDATE`; SQLite keeps its ORM-compatible branch.

### RED evidence

```powershell
python -m unittest tests.test_memory_extraction.MemoryExtractionTests.test_mock_scopes_consent_after_decimal_or_url_sentence tests.test_memory_extraction.MemoryExtractionTests.test_real_provider_scopes_consent_after_decimal_or_url_sentence tests.test_memory_extraction.MemoryExtractionTests.test_cjk_url_and_email_periods_remain_inside_token_spans tests.test_memory_retrieval.MemoryRetrievalTests.test_real_retrieval_falls_back_to_old_and_null_vectors_per_user tests.test_memory_retrieval.MemoryRetrievalTests.test_real_retrieval_merges_deduplicates_and_limits_mixed_sources tests.test_memory_store.MemoryStoreTests.test_postgres_first_insert_locks_empty_category_and_uses_atomic_upsert -v
```

Result before implementation: 6 tests ran with 9 expected assertion failures and 2 expected errors. Consent crossed decimal/URL sentence stops, CJK URL/email periods were split, stale/NULL vectors were invisible, the fallback loader was absent, and the PostgreSQL path attempted a non-atomic ORM add without an empty-set lock.

### GREEN evidence

```powershell
python -m unittest tests.test_memory_extraction.MemoryExtractionTests.test_mock_scopes_consent_after_decimal_or_url_sentence tests.test_memory_extraction.MemoryExtractionTests.test_real_provider_scopes_consent_after_decimal_or_url_sentence tests.test_memory_extraction.MemoryExtractionTests.test_cjk_url_and_email_periods_remain_inside_token_spans tests.test_memory_retrieval.MemoryRetrievalTests.test_real_retrieval_falls_back_to_old_and_null_vectors_per_user tests.test_memory_retrieval.MemoryRetrievalTests.test_real_retrieval_merges_deduplicates_and_limits_mixed_sources tests.test_memory_store.MemoryStoreTests.test_postgres_first_insert_locks_empty_category_and_uses_atomic_upsert -v
```

Result: 6/6 passed.

```powershell
python -m unittest tests.test_memory_extraction tests.test_memory_store tests.test_memory_retrieval tests.test_backend_contracts -v
```

Result: 176/176 passed.

```powershell
python -m unittest discover -s tests -p 'test_*.py'
```

Result: 251/251 passed.

### Fix-round self-review

- Protected token periods are computed before sentence scanning; a generic bare-IDN pattern was intentionally rejected because it misclassified arbitrary `中文.中文` prose. IDN URLs require a URL scheme, and Unicode email spans require `@` context.
- Both the active-vector and fallback queries include the current `user_id`. Old signatures never participate in cosine scoring; fallback rows never use their obsolete vector.
- Merge ordering is deterministic by score, source priority, update time, and UUID. Duplicate IDs keep their strongest source score before the final limit.
- Advisory lock keys include both user UUID and category and are acquired in sorted category order to avoid cross-batch lock-order deadlocks. The lock precedes exact-key and semantic-duplicate queries.
- Atomic conflict updates preserve row identity and update content, scoring fields, sources, embedding, provider signature, and `updated_at` without rolling back unrelated candidates in the batch.
- No new log statement includes memory content or embedding data.

### Remaining risks after fix round 1

- PostgreSQL SQL compilation and call ordering are contract-tested, but advisory locking, `ON CONFLICT`, and pgvector execution were not exercised against a live PostgreSQL service in this task run.
- Fallback candidate loading is intentionally bounded before in-process ranking; installations with very large stale-memory collections may eventually need a database text index or background re-embedding migration.
- Similarity threshold and cross-source ranking weights still require tuning against representative production recall data.

### Fix commit

- Subject: `fix: harden memory concurrency and fallback retrieval`
- The immutable hash is reported in the fix-round completion message.

---

## Fix round 2

### Critical finding addressed

- Replaced greedy URL/email protection regexes with structural token scanning. URL authority is separated from path/query/fragment, while email local-part and domain spans are scanned independently.
- Clearly internal dots in ASCII/IDN URLs, Unicode emails, decimals, JWTs, and dotted ASCII tokens remain protected from sentence splitting.
- A `.中文` sequence inside a URL suffix or after an already complete IDN email/domain label is treated as ambiguous. Extraction fails closed for the entire message before deterministic extraction or any provider call, so later sensitive text cannot inherit an earlier memory instruction.
- A completed ASCII host followed by `.中文` remains a deterministic sentence boundary; ordinary URL path sentence endings followed by whitespace are also kept outside the token span.

### RED evidence

```powershell
python -m unittest tests.test_memory_extraction.MemoryExtractionTests.test_ambiguous_dotted_token_boundary_fails_closed_in_mock tests.test_memory_extraction.MemoryExtractionTests.test_ambiguous_dotted_token_boundary_skips_real_provider tests.test_memory_extraction.MemoryExtractionTests.test_cjk_url_and_email_periods_remain_inside_token_spans -v
```

Initial result: 3 test methods ran. All three Mock reproductions returned an unsafe combined candidate, and the first real-provider reproduction called the provider and accepted the combined candidate. A misplaced provider control-loop in the newly added test then raised one test-harness `NameError`; that test-only placement was corrected before implementation.

### GREEN evidence

Focused security and token-boundary regression set:

```powershell
python -m unittest tests.test_memory_extraction.MemoryExtractionTests.test_ambiguous_dotted_token_boundary_fails_closed_in_mock tests.test_memory_extraction.MemoryExtractionTests.test_ambiguous_dotted_token_boundary_skips_real_provider tests.test_memory_extraction.MemoryExtractionTests.test_cjk_url_and_email_periods_remain_inside_token_spans tests.test_memory_extraction.MemoryExtractionTests.test_mock_scopes_consent_after_decimal_or_url_sentence tests.test_memory_extraction.MemoryExtractionTests.test_real_provider_scopes_consent_after_decimal_or_url_sentence tests.test_memory_extraction.MemoryExtractionTests.test_full_jwt_fails_closed_before_mock_or_provider_extraction tests.test_memory_extraction.MemoryExtractionTests.test_sentence_splitter_preserves_internal_english_periods tests.test_memory_extraction.MemoryExtractionTests.test_consecutive_terminal_marks_remain_one_question_sentence -v
```

Result: 8/8 passed.

Task-focused suite:

```powershell
python -m unittest tests.test_memory_extraction tests.test_memory_store tests.test_memory_retrieval tests.test_backend_contracts -v
```

Result: 178/178 passed.

Full Python suite:

```powershell
python -m unittest discover -s tests -p 'test_*.py'
```

Result: 253/253 passed.

### Fix-round self-review

- All three reported ambiguous URL-path/Unicode-email/IDN-URL inputs return no Mock candidates. The real-provider path returns before invocation, verified by the provider spy remaining untouched for every case.
- Normal ASCII URL paths (including an internal dotted path), a two-label IDN URL with a CJK path, and a two-label Unicode/IDN email remain one complete evidence span in both Mock and provider modes.
- URL/email scanners stop on whitespace and sentence punctuation and trim a terminal ASCII full stop, preventing token protection from absorbing the next whitespace-delimited sentence.
- Credential/JWT, decimal, consecutive punctuation, and the previously fixed ASCII-host/CJK-boundary tests remain green.
- Store and retrieval implementations were not changed in this round.

### Remaining risks after fix round 2

- Multi-label IDN authorities or domains followed by CJK are intentionally rejected when a later dot cannot be distinguished from a sentence boundary. This is a conservative availability tradeoff required to prevent consent propagation.
- ASCII host recognition is syntactic rather than based on the public suffix list. Unusual URL/email forms outside the supported scanner grammar fail conservatively or are left to the ordinary sentence/source safety gates.

### Fix commit

- Subject: `fix: fail closed on ambiguous dotted memory text`
- The immutable hash is reported in the fix-round completion message.
