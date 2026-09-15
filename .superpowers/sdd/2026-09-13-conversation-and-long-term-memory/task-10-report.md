# Task 10 report — end-to-end memory verification and operations

Date: 2026-09-15
Branch: `codex/memory-system`

## Delivered

- Added `scripts/verify_memory_system.py`, an opt-in real-provider smoke test that:
  - checks API readiness without logging credentials or response bodies;
  - creates a random temporary user and always deletes it in `finally`;
  - validates authenticated memory create/read/update/delete;
  - submits enough complete chat turns to trigger summary maintenance;
  - bounded-polls automatic extraction and the owned summary row;
  - requires both a non-empty summary and `summarized_through_message_id`;
  - opens a new conversation with `请明确复述你记得的校区和时间偏好`;
  - removes SSE whitespace before requiring both `仙林` and `下午`;
  - prints stage results only, never token, password, complete memory text, or model output.
- Extended `scripts/verify_core.py` with deterministic complete-turn trimming, Mock summary,
  authentication-secret rejection, and Mock keyword retrieval checks. External model and
  Embedding calls are fail-fast forbidden in these Mock checks.
- Replaced source-grep-heavy probe tests with behavioral contracts for SSE parsing, bounded
  polling, cleanup on failure, response privacy, and the five real agent intents.
- Added repository-root bootstrapping to the three directly executable verification commands,
  so the documented `python scripts/...` form works outside Compose as well as with
  `PYTHONPATH=/app` inside Compose.
- Documented memory configuration, migration 043, Mock/real degradation, Embedding signature
  fallback, automatic capture and secret policy, API/page contracts, hard deletion, background
  failure isolation, and local/real verification prerequisites in `README.md`.

## TDD evidence

RED command:

```text
python -m unittest tests.test_memory_verification tests.test_real_llm_agent_probe -v
```

Observed: 7 errors for the intentionally absent `scripts.verify_memory_system` module and absent
`AGENT_CHECKS` runtime contract. Direct invocation also reproduced the existing entry-point defect:
`python scripts/verify_core.py` failed 30 repository imports because the repository root was absent
from `sys.path`.

GREEN command:

```text
python -m unittest tests.test_memory_verification tests.test_real_llm_agent_probe -v
```

Observed: 10 tests passed.

## Full local verification matrix

| Command | Result |
|---|---|
| `python -m unittest discover -s tests -p 'test_*.py'` | PASS — 332 tests in 37.650s |
| `python scripts/verify_core.py` | PASS — 34 checks, 0 failures |
| `python -m compileall apps services packages scripts` | PASS — exit 0 |
| `npm run build` from `apps/web` | PASS — `vue-tsc -b`, 146 Vite modules in 4.57s, exit 0 |

## Real external verification

Environment precondition audit (values were not printed):

```text
MOCK_LLM=true
missing=LLM_BASE_URL,LLM_API_KEY,LLM_MODEL,EMBEDDING_BASE_URL,EMBEDDING_API_KEY,EMBEDDING_API_MODEL
```

Therefore these were **not run as external probes**:

- `python scripts/check_external_llm.py`
- `python scripts/verify_real_llm_agents.py`
- `python scripts/verify_memory_system.py`

The local precondition guard was exercised and rejected Mock mode before any network access. These
items remain deployment smoke checks and must be run only after the README prerequisites are met.

## Ledger and final-checklist triage

- Confirmed 43 ordered SQL migrations; `043_memory_system.sql` is present once and the migration
  runner records each filename once.
- The Task 2 role/message annotations remain deliberately wider than the runtime values. Tightening
  them is a future static-contract cleanup; it is not required by the Task 10 runtime probe and no
  mypy/pyright gate currently consumes those annotations.
- The Task 7 service-boundary ownership check remains after summary refresh. The authenticated chat
  route validates ownership before scheduling maintenance, so current callers are protected; moving
  that check ahead of summary refresh remains a defense-in-depth follow-up if this service gains
  additional callers.
- The Task 3 oversized-turn ruling is exercised offline by the complete-turn trimming/summary checks.
  The Task 10 recall ruling is implemented exactly and asserted behaviorally after SSE parsing.
