# Task 8 Report: Authenticated memory management APIs

## Outcome

- Added authenticated CRUD routes at `/api/v1/memories` and `/api/v1/memories/{memory_id}`, with typed create, patch, response, and page schemas.
- Added typed `GET`/`PUT /api/v1/preferences/memory` routes. The memory section is merged into the existing versioned preferences document, so notification, reminder, job-push, and visibility fields are preserved.
- Resource reads, updates, and hard deletes use both the memory UUID and authenticated user UUID. Missing and cross-user resources return the same 404 response.
- Added stable descending pagination over `(updated_at, id)`. The opaque cursor is URL-safe base64 containing an ISO timestamp and UUID; invalid base64, invalid types, renamed/missing/extra fields, invalid timestamps, and invalid UUIDs fail with 422.
- Manual creates and edits reuse the memory security classifier and sanitizer. Credentials are rejected unconditionally with 422; the authenticated manual save action is treated as explicit user intent for other personal-sensitive information. Memory bodies and secrets are not logged.
- Mock mode stores `embedding = NULL` and an empty provider signature. Real mode calls the existing embedding function through `asyncio.to_thread()` and stores the current `embedding_signature()`; no second feature switch was introduced.
- Manual canonical keys carry the selected category and an opaque per-row suffix. Category changes rewrite that prefix, while content changes refresh or clear embedding-derived fields according to the shared Mock/real mode.
- Store updates now issue an explicit SQL `UPDATE` scoped by both `(memory_id, user_id)`, followed by an equally scoped refresh. Existing transactional delete and rollback behavior remains intact.

## TDD Evidence

### Initial RED

Command:

```powershell
python -m unittest tests.test_memory_api tests.test_acceptance_workflow -v
```

Observed before production changes: the new API test module failed to import because `apps.api.routes.memories` did not exist; the existing acceptance workflow test remained green.

### Typed-preferences RED

Command:

```powershell
python -m unittest tests.test_memory_api.MemoryApiSchemaTests.test_memory_preference_endpoints_publish_typed_responses -v
```

Observed before adding response models: the OpenAPI response schema had no named `$ref`, so the test failed with the expected missing typed response contract.

### Focused GREEN

Command:

```powershell
python -m unittest tests.test_memory_api tests.test_acceptance_workflow tests.test_backend_contracts -v
```

Result: 122 tests passed, 0 failures.

Task 5 storage regression:

```powershell
python -m unittest tests.test_memory_store -v
```

Result: 11 tests passed, 0 failures.

### Full Python verification

Command:

```powershell
python -m unittest discover -s tests -p 'test_*.py'
```

Result: 290 tests passed, 0 failures.

Additional checks:

```powershell
python -m compileall -q apps services tests
git diff --check
```

Both completed successfully. Git reports only the repository's expected LF-to-CRLF checkout notices.

## Files Changed

- `apps/api/routes/memories.py`
- `apps/api/routes/preferences.py`
- `apps/api/main.py`
- `services/memory/store.py`
- `tests/test_memory_api.py`
- `.superpowers/sdd/2026-09-13-conversation-and-long-term-memory/task-8-report.md`

`tests/test_acceptance_workflow.py` was exercised unchanged so its existing verifier contract remains compatible.

## Self-review

- **Authentication:** every new route declares the existing `get_current_user` dependency; the published OpenAPI contract exposes the authorization header on each operation.
- **Isolation:** list queries always scope by `user_id`; detail reads, update selection, the SQL update itself, post-update refresh, and hard delete all scope by both `id` and `user_id`.
- **Pagination:** the order and cursor predicate use the same descending pair, including the UUID tie-breaker, and tests drain multiple tied-timestamp pages without duplicates or omissions.
- **Validation:** schemas forbid unknown fields, constrain the six categories, enforce content length 1–500, importance 0–1, and page limits 1–100. Whitespace-only content is rejected after normalization.
- **Privacy:** credential detection precedes normalization/persistence in both create and edit paths. No route logger records request content, response bodies, embeddings, or exception text containing secrets.
- **Embedding lifecycle:** creation performs the external call before adding the row. Content edits use Task 5's `asyncio.to_thread()` path; Mock edits explicitly clear stale vectors and signatures. Category-only edits retain the content vector.
- **Transactions:** create, scoped update, and hard delete each commit once and roll back on exceptions. A memory row stores body and vector together, so hard delete removes both atomically.
- **Preferences:** the existing `PreferencesData` validator supplies safe defaults and `_save_preference_section()` assigns only the memory section. Task 7 continues reading `user.preferences["memory"]["auto_capture_enabled"]` without a schema change.
- **Compatibility:** no chat request, SSE event, conversation-history response, LLM provider selection, or existing preferences route was changed.
- External subagent review was not used because the task explicitly prohibited spawning subagents.

## Remaining Risks

- PostgreSQL/pgvector and a live external embedding provider were unavailable for an end-to-end API run. SQLAlchemy behavior, provider signatures, and off-loop invocation are covered by SQLite integration tests and provider doubles.
- The cursor is opaque and structurally validated but intentionally not cryptographically signed. Clients may construct another well-formed `(updated_at, id)` boundary; user scoping still prevents data disclosure.
- Concurrent category edits that produce an already-existing extracted canonical key can surface the database uniqueness conflict; manually created rows use UUID suffixes and cannot collide in normal operation.

## Commit

- Subject: `feat: add user memory management api`
- Branch: `codex/memory-system`
- This report is included in the task commit; the immutable hash is reported after commit creation.

---

## Fix round 1

### Findings addressed

1. Expanded the credential classifier to reject Slack `xoxb`/`xoxp`, GitHub
   `ghp_`/`github_pat_`, GitLab `glpat-`, npm tokens, other common token families,
   and conservatively detected high-entropy token-shaped values.  Create and
   PATCH reject them before embedding/provider work or persistence; ordinary
   prose and UUIDs remain accepted.
2. Isolated the memory-preference endpoints from the legacy root preference
   schema.  They validate only `preferences.memory`, shallow-copy the root
   object on write, and preserve unrelated keys such as
   `knowledge_pathway_mode` without coercing them.
3. Rejected empty PATCH payloads and all-null updates at schema validation, so
   `update_user_memory()` and `updated_at` cannot be touched for a no-op.
4. Converted `OverflowError` and timestamp `ValueError` during cursor UTC
   normalization to the existing generic 422 cursor response.
5. Content/category PATCHes now detach from extracted semantic keys by assigning
   a stable `category:manual-{memory_id.hex}` canonical key.  The manual key is
   collision-safe, cannot be overwritten through an old automatic key, and
   preserves the existing user-scoped vector refresh/clear behavior.
6. Enabled SQLAlchemy `hide_parameters`; database/provider failures now roll
   back and return generic 5xx responses while logs contain only operation,
   exception type, and non-sensitive UUIDs.  The same safe boundary now also
   covers list/detail database failures, preventing a query exception from
   leaking SQL or request content.

### RED/GREEN evidence

The inherited interrupted worktree already contained the primary review
regressions and their implementation, so it was preserved rather than reset.
During takeover, a new query-error regression was added before its production
change:

```powershell
python -m unittest tests.test_memory_api.MemoryApiTests.test_read_database_failures_are_rolled_back_and_safely_reported -v
```

RED: both list and get propagated `RuntimeError: SENTINEL READ SQL PARAMETER
MEMORY BODY`; no safe API log was emitted.  After adding the common database
error boundary to those reads, the same test was GREEN (1 test passed).

Focused Task 8 plus Task 4/5/7 safety regression coverage was then run:

```powershell
python -m unittest tests.test_memory_api tests.test_acceptance_workflow tests.test_backend_contracts tests.test_memory_extraction tests.test_memory_store tests.test_memory_retrieval tests.test_memory_maintenance tests.test_chat_context_streaming tests.test_agent_resilience -v
```

The suite completed successfully; the final full-suite command below is the
authoritative count.

### Files changed in this fix round

- `apps/api/database.py`
- `apps/api/routes/memories.py`
- `apps/api/routes/preferences.py`
- `services/memory/security.py`
- `services/memory/store.py`
- `tests/test_memory_api.py`
- `tests/test_memory_extraction.py`
- `.superpowers/sdd/2026-09-13-conversation-and-long-term-memory/task-8-report.md`

### Self-review

- Secret tests cover create/PATCH rejection, zero provider calls, no newly
  persisted row or changed original row, natural language and UUID false-positive
  resistance, and sentinel content absence from public errors/log records.
- GET/PUT memory preferences no longer construct `PreferencesData`, retaining
  extension keys verbatim.  Failed preference commits roll back and restore the
  original in-memory document.
- Manual canonical keys derive solely from the edited row UUID and effective
  category, so a same-suffix extracted key cannot create a uniqueness conflict
  or redirect the update to another user's row.
- All mutation predicates remain scoped by `memory_id` and `user_id`; content
  edits still recalculate real embeddings and clear vectors/signatures in Mock
  mode.
- API error logs interpolate no exception text, SQL, content, vectors, or
  credentials.  SQLAlchemy also hides bound parameters at engine level.

### Remaining risks

- Pattern/entropy classification deliberately fails closed for token-shaped
  data; future credential formats may need explicit signatures, while an unusual
  high-entropy non-secret identifier could conservatively be rejected.
- PostgreSQL/pgvector and live providers remain untested end-to-end; SQLite and
  provider doubles exercise API transactions, rollback, vector lifecycle, and
  non-leakage behavior.

---

## Fix round 2

### Findings addressed

1. Replaced the overly broad generic entropy token match with compact-token and
   long-hex checks.  URL/email spans are excluded before generic evaluation;
   generic base64/API-key candidates require `_`, `+`, or `=` in addition to
   length, mixed character classes, and entropy.  This keeps readable path and
   hyphenated course-slug text out of the secret classifier while explicit
   platform signatures remain unconditional rejects.
2. Moved real-mode PATCH embedding behind the initial user-scoped
   `SELECT ... FOR UPDATE`.  Other-user and nonexistent resources now return
   404 before any embedding/provider call.  The final `UPDATE` still repeats
   both ownership predicates; a row disappearing after the check takes the
   existing row-count-zero rollback path and becomes 404.  An owned resource
   whose provider fails still rolls back and returns the generic safe 500.

### RED/GREEN evidence

Before production changes, four added regressions failed as expected:

```powershell
python -m unittest tests.test_memory_api.MemoryApiTests.test_urls_and_course_slugs_are_not_rejected_as_high_entropy_secrets tests.test_memory_api.MemoryApiTests.test_real_patch_checks_ownership_before_calling_embedding_provider tests.test_memory_extraction.MemoryExtractionTests.test_urls_and_course_slugs_are_eligible_for_automatic_extraction tests.test_memory_extraction.MemorySecurityTests.test_high_entropy_guard_does_not_reject_ordinary_language_or_uuids -v
```

RED: both required URL/slug examples returned 422 or empty extraction results;
PATCH against other-user and nonexistent IDs called the failing embedding stub
and returned 500.  After the narrow token classifier and ownership-first store
ordering, the regression set was GREEN.  The final focused suite ran 212 tests:

```powershell
python -m unittest tests.test_memory_api tests.test_acceptance_workflow tests.test_backend_contracts tests.test_memory_extraction tests.test_memory_store tests.test_memory_retrieval -q
```

### Files changed

- `services/memory/security.py`
- `services/memory/store.py`
- `tests/test_memory_api.py`
- `tests/test_memory_extraction.py`
- `.superpowers/sdd/2026-09-13-conversation-and-long-term-memory/task-8-report.md`

### Self-review

- Explicit Slack, GitHub, GitLab, npm, and other known provider signatures are
  still checked before the generic classifier.  Random base64url and 64-hex
  regression values are rejected, while the required GitHub URL and course slug
  are accepted by both manual POST and real-model candidate validation.
- The provider spy proves zero calls for a cross-user row and a nonexistent ID
  even when the provider is configured to fail.  It proves an owned row still
  reaches that failure safely as one generic 500.
- The precheck and the final update both scope by `(memory_id, user_id)`;
  no-provider missing reads end their read-only transaction, while a failed
  post-check mutation takes rollback before the API emits 404.

### Remaining risks

- An unlabeled base64url secret containing no `_`, `+`, or `=` cannot be
  distinguished reliably from a readable hyphenated identifier and is left to
  explicit provider patterns or future context-aware rules.  This is an
  intentional false-positive reduction.
- PostgreSQL lock behavior and live embedding providers remain covered by SQL
  shape tests and doubles, not a production-service integration environment.

---

## Fix round 3

### Findings addressed

1. Replaced whole-URL protection with structural URL handling.  Only an email
   address or URL authority is protected from generic token scanning.  For every
   URL path, query, and fragment, the classifier scans both its raw and
   percent-decoded form for known credential signatures, long hex values, and
   high-entropy compact tokens.  Path/query/fragment secrets can therefore no
   longer hide behind an otherwise ordinary URL.
2. Added a separate 32–128-character pure-alphanumeric token branch.  It
   requires lowercase, uppercase, and digit mixing plus at least 4.0 bits of
   per-character entropy, so 44/48-character base64-like values are rejected
   without treating ordinary prose, short identifiers, GitHub paths, or
   hyphenated course slugs as credentials.

### RED/GREEN evidence

Before implementation, the three credential suites had 21 expected failures:

```powershell
python -m unittest tests.test_memory_api.MemoryApiTests.test_token_families_and_high_entropy_secrets_never_reach_providers tests.test_memory_extraction.MemoryExtractionTests.test_common_token_families_and_high_entropy_values_skip_provider tests.test_memory_extraction.MemorySecurityTests.test_sanitizer_rejects_secrets_even_when_explicit -v
```

RED demonstrated that URL path/fragment Q-style values and long hex values,
plus 44/48-character alphanumeric values, reached the embedding or LLM test
doubles.  URL `?token=` remained rejected by its explicit keyword, while the
percent-encoded query value regression proves the new decoded-component scan.
After the structural scanner, all three suites were GREEN with zero provider
calls, 422 manual API responses, empty real-extraction results, and no rows
persisted.  The Task 8/Task 4/5 focused regression command passed 212 tests:

```powershell
python -m unittest tests.test_memory_api tests.test_acceptance_workflow tests.test_backend_contracts tests.test_memory_extraction tests.test_memory_store tests.test_memory_retrieval -q
```

### Files changed

- `services/memory/security.py`
- `tests/test_memory_api.py`
- `tests/test_memory_extraction.py`
- `.superpowers/sdd/2026-09-13-conversation-and-long-term-memory/task-8-report.md`

### Self-review

- The URL parser is used only for structural component selection; it emits no
  logs or exceptions containing input.  Raw and one-level percent-decoded path,
  query, and fragment values are checked with the same policy helper.
- Known platform prefixes still take priority.  Standalone, path, query,
  decoded-query, and fragment secret cases cover create, PATCH, and real-mode
  extraction, asserting no embedding/LLM invocation and no persistence.
- The previous PATCH ownership-before-provider ordering is untouched; this
  round changes no route or store transaction behavior.

### Remaining risks

- The generic alphanumeric threshold can conservatively reject an unusually
  random-looking, unlabeled long identifier.  Conversely, deliberately encoded
  multi-layer URL values beyond one percent-decode pass remain a future policy
  decision rather than being recursively decoded without a bounded limit.
- Live PostgreSQL and provider integration remains outside this SQLite/double
  verification environment.

---

## Fix round 4

### Findings addressed

1. URL handling now discovers and parses URL spans before ordinary credential
   label scanning.  Parsed URLs are removed from the non-URL scan, while their
   userinfo, path segments, query values, and fragment are inspected
   structurally.  A readable hostname such as `token.example.com` and a path
   such as `/token-economics/` no longer match the standalone `token` label.
2. Every non-empty URL password is an unconditional credential, including a
   one-character value.  Usernames remain subject to known-pattern and entropy
   checks rather than being hidden with the hostname.  Path/query/fragment
   values still reject known provider prefixes, long hex, compact base64-like
   values, percent-decoded values, and explicit credential `label=value`
   forms.
3. URL authorities must expose a valid hostname and port.  Hostnames are
   validated as IPv4, IPv6, or IDNA DNS labels.  All parsing, component-property,
   port, IDNA, and address-validation exceptions are caught inside the
   classifier and fail closed as credentials without logging input or exception
   text.  NFKC-invalid netlocs therefore reach manual APIs only as the existing
   generic 422 response and never escape into ASGI error handling.

### RED/GREEN evidence

The first RED command covered POST, PATCH, real extraction, sanitizer behavior,
and both required safe URL forms:

```powershell
python -m unittest tests.test_memory_api.MemoryApiTests.test_url_credentials_are_rejected_by_post_before_provider_or_persistence tests.test_memory_api.MemoryApiTests.test_url_credentials_are_rejected_by_patch_before_provider_or_persistence tests.test_memory_api.MemoryApiTests.test_urls_and_course_slugs_are_not_rejected_as_high_entropy_secrets tests.test_memory_extraction.MemoryExtractionTests.test_url_userinfo_and_invalid_netloc_fail_closed_before_provider tests.test_memory_extraction.MemoryExtractionTests.test_urls_and_course_slugs_are_eligible_for_automatic_extraction tests.test_memory_extraction.MemorySecurityTests.test_sanitizer_rejects_secrets_even_when_explicit tests.test_memory_extraction.MemorySecurityTests.test_high_entropy_guard_does_not_reject_ordinary_language_or_uuids -v
```

RED ran 7 test methods with 11 failing subtests and 7 errors.  The userinfo URL
called each POST/PATCH provider once and was persisted; NFKC-invalid input
escaped as `ValueError`; both ordinary `token` URLs were rejected by manual APIs
and real extraction.  After structural URL classification, the same 7 methods
were GREEN.  A second focused RED proved that `https://exam_ple.com/course` was
incorrectly accepted before hostname validation; its sanitizer test was GREEN
after the authority validator was added.  A final URL-span RED showed that a
legal bracketed IPv6 authority with `/token-economics/` was still handled as
non-URL text; allowing brackets only in the IPv6-host alternative made that
positive GREEN without widening ordinary bracket-delimited URL matches.

The final Task 8 plus Task 4/5 regression command passed 215 tests:

```powershell
python -m unittest tests.test_memory_api tests.test_acceptance_workflow tests.test_backend_contracts tests.test_memory_extraction tests.test_memory_store tests.test_memory_retrieval -q
```

The full Python suite passed 311 tests:

```powershell
python -m unittest discover -s tests -p 'test_*.py' -q
```

Additional checks completed with exit code 0:

```powershell
python -m compileall -q apps services tests
git diff --check
```

`git diff --check` emitted only the repository's expected LF-to-CRLF checkout
notices.

### Files changed

- `services/memory/security.py`
- `tests/test_memory_api.py`
- `tests/test_memory_extraction.py`
- `.superpowers/sdd/2026-09-13-conversation-and-long-term-memory/task-8-report.md`

### Self-review

- POST regressions assert a generic 422, zero embedding/signature calls, and no
  stored rows.  PATCH regressions assert the same provider boundary plus one
  unchanged original row.  Real extraction asserts an empty result and that the
  model double received no messages.
- The public error assertion contains no submitted URL or parser exception.
  The classifier has no logger, and its exception boundary returns a sensitivity
  value rather than propagating or interpolating exception text.
- URL masking occurs only after parsing and authority validation.  Hostname and
  port are the only protected authority data; any password is rejected and a
  username is independently scanned.
- Round 3 URL path/query/fragment, long-hex, provider-token, base64-like, and
  percent-decoding regressions all remain in the 215-test focused suite.  The
  ordinary GitHub URL, bracketed IPv6 authority, and readable course slug
  positives remain green alongside the new `token` hostname/path positives.
- No route, store transaction, ownership predicate, provider ordering, or
  persistence implementation changed in this round.

### Remaining risks

- URL extraction intentionally supports HTTP(S) spans only, matching the memory
  feature's existing policy.  A syntactically unusual authority or DNS label is
  rejected conservatively rather than being treated as ordinary memory text.
- URL values are percent-decoded once.  Recursively encoded values remain the
  same explicit future-policy decision recorded in round 3.
- PostgreSQL/pgvector and live providers remain outside the local integration
  environment; the unchanged provider and persistence boundaries are exercised
  through SQLite and deterministic doubles.

---

## Fix round 5 (final round)

### Findings addressed

The query classifier previously partitioned raw fields on a literal `=` before
decoding. Consequently `?token%3Dhunter2`, `?password%3Dhunter2`,
`?access_token%3Dshortsecret`, and `?%74%6f%6b%65%6e%3Dhunter2` bypassed the
credential guard. It now percent/plus-decodes the complete query exactly once
before interpreting `&` and `=`. Raw and decoded query text, keys, and values
are checked for credential signatures, explicit labels with values, and
high-entropy secrets. The raw scan preserves detection of literal `+` inside
compact credentials. Component checks explicitly disable further decoding.

Malformed percent escapes are rejected, and strict UTF-8 decoding errors fall
through the existing URL exception boundary to credential classification. No
input or exception text is logged or exposed by this boundary.

### RED/GREEN evidence

Before production edits, the expanded POST, PATCH, and real-extraction URL
tests reproduced the four required bypasses plus encoded separators, keys,
values, plus decoding, and malformed queries. POST/PATCH did not raise the
expected 422, and extraction reached the model double.

A second RED specifically exercised real extraction followed by the actual
SQLite store operation, alongside a safe-query control:

```powershell
python -m unittest tests.test_memory_api.MemoryApiTests.test_encoded_query_extraction_never_reaches_provider_or_persistence tests.test_memory_extraction.MemoryExtractionTests.test_safe_encoded_query_does_not_block_real_extraction -q
```

Result before implementation: 2 test methods, 14 failures. Unsafe input yielded
a candidate and reached embedding 13 times; the safe-query control passed.
After implementation, all targeted API/extraction methods passed. Final
coverage includes 18 unsafe query fixtures, four ordinary encoded query
fixtures, and explicit single-layer decoding characterization.

The Task 8/4/5 focused suite passed 218 tests:

```powershell
python -m unittest tests.test_memory_api tests.test_acceptance_workflow tests.test_backend_contracts tests.test_memory_extraction tests.test_memory_store tests.test_memory_retrieval -q
```

The full Python suite passed 314 tests:

```powershell
python -m unittest discover -s tests -p 'test_*.py' -q
```

Additional checks completed with exit code 0:

```powershell
python -m compileall -q apps services tests
git diff --check
```

The test runs emitted existing policy INFO and asyncio slow-task messages;
the diff check emitted only the expected LF-to-CRLF checkout notices.

### Files changed

- `services/memory/security.py`
- `tests/memory_query_cases.py`
- `tests/test_memory_api.py`
- `tests/test_memory_extraction.py`
- `.superpowers/sdd/2026-09-13-conversation-and-long-term-memory/task-8-report.md`

### Self-review

- The single decoding pass precedes parameter splitting, and raw/decoded
  component scans never invoke another percent or plus decoding pass. Tests
  characterize nested escapes and `%2B` as requiring no second interpretation.
- POST/PATCH regressions assert generic 422 errors and zero embedding/signature
  calls, with no created rows and an unchanged original PATCH row. The real
  extraction/store integration asserts empty candidates, zero model awaits,
  zero embedding/signature calls, zero stored candidates, and an empty table.
- Multi-parameter fields, encoded `&`/`=`, encoded credential names and values,
  credential values placed in keys or bare fields, and malformed UTF-8/percent
  escapes are exercised through all three entry paths.
- Safe query fixtures cover encoded spaces, Unicode, names, separators, plus,
  and literal percent signs. Manual POST/PATCH persist them verbatim. Real
  extraction still calls its model and retains an independent stable preference
  sentence in a message containing each safe URL.
- All earlier userinfo, NFKC, hostname/path `token` positives, path/query/fragment
  credentials, platform tokens, base64/hex secrets, ownership/provider ordering,
  and API regression tests passed. No API, persistence, or extraction production
  implementation changed. No subagents were spawned.

### Remaining risks

- Nested encoding beyond one layer remains outside the deliberate policy;
  percent-encoded byte sequences that are not valid UTF-8 fail closed.
- The existing extraction question rule treats `?` in a URL as a question
  marker. This round does not expand extraction eligibility: safe-query controls
  use a separate stable sentence, while manual APIs test the URL itself.
- Live PostgreSQL/pgvector and external providers were not exercised; the tests
  use SQLite and deterministic provider doubles.
