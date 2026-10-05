# ByteDaily / DevQuest Bot — Technical Audit Recommendations

**Date:** 2026-10-05  
**Scope:** Full repository (`main.py`, `config.py`, `features/bytedaily/**`, `legacy/**`, `bridge/**`)  
**Method:** Read-only static analysis. **No application code was modified.**  
**This document is the sole deliverable of the audit.**

---

## Executive summary

The ByteDaily path is largely async-correct (asyncpg, aiohttp, defer-first Discord interactions, atomic poll close). The highest-risk items are **default API credentials**, **concurrent rollover / force-cycle races that can create multiple open polls**, and **rollover latency from sequential personal DMs blocking the next challenge post**. Secondary themes: dual DB pools, `SELECT *` usage, unused sync dependencies in `requirements.txt`, and remaining leaderboard history purge on recreate.

---

## 1. MUST-DO (Critical / Essential)

### 1.1 Default weak API key + public bind address

| Field | Detail |
|---|---|
| **Location** | `config.py` (`BOT_API_KEY = os.getenv("BOT_API_KEY", "secret123")`); `legacy/api/server.py` (`AsyncAPIServer.start` → `API_HOST` default `0.0.0.0`); `POST /api/start-exam` |
| **Why** | If `BOT_API_KEY` is unset in production, anyone who can reach the service can start exams for arbitrary Discord user IDs. Binding `0.0.0.0` on Render exposes the API to the public internet by design. |
| **Recommendation** | Fail fast at startup if `BOT_API_KEY` is missing or equals a known default. Prefer constant-time comparison. Document that `/api/start-exam` must never ship with a default secret. Optionally restrict the mutating route behind network rules or disable it when not needed. |

### 1.2 Concurrent force-cycle vs scheduler tick can double-post

| Field | Detail |
|---|---|
| **Location** | `features/bytedaily/scheduler.py` — `ByteDailyScheduler._check_loop` / `_is_processing`; `force_cycle()`; `_post_question()`; `poll_repo.create()` |
| **Why** | `_check_loop` skips overlapping ticks via `_is_processing`, but `force_cycle()` does **not** take the same lock. A tick mid-rollover and an admin `/bytedaily-force-cycle` can both close and both call `_post_question`. There is **no DB constraint** ensuring at most one `bd_polls` row with `status='open'`. Result: two live challenges, ambiguous `get_open_poll()`, broken rolling-window IDs. |
| **Recommendation** | Share one asyncio lock / `_is_processing` across `_check_loop` and `force_cycle`. Add a partial unique index, e.g. `CREATE UNIQUE INDEX … ON bd_polls ((status)) WHERE status = 'open'`, and handle unique-violation on insert. |

### 1.3 Personal result DMs block the next challenge post

| Field | Detail |
|---|---|
| **Location** | `scheduler._close_poll` → `_dm_personal_results` (before `_rollover` continues to `_delete_poll` / `_post_question`); DM pacing `await asyncio.sleep(0.35)` per user |
| **Why** | With N participants, close holds `_is_processing` for roughly `0.35N` seconds plus Discord RTT. The next poll is not posted until DMs finish. Large polls delay the cycle, skip ticks, and extend the empty-channel window. Also concentrates Discord REST traffic (fetch user + DM) in a burst that can approach rate limits. |
| **Recommendation** | After public close + results embed + DB mark, **post the next question first**, then fan out DMs in a background `asyncio.create_task` (tracked/cancellable on unload) with concurrency limits (e.g. semaphore of 2–5) instead of serial sleep-only pacing. Never let DM delivery gate rollover completion. |

### 1.4 Privileged Discord intents enabled globally

| Field | Detail |
|---|---|
| **Location** | `main.py` — `intents = discord.Intents.all()` |
| **Why** | Requests every privileged intent (members, message content, presence). Increases Discord review surface, privacy exposure, and gateway payload volume. Most ByteDaily flows only need guilds + members (for roles) + interactions. |
| **Recommendation** | Enable only required intents (`guilds`, `guild_members`, `guild_messages` / `message_content` only if prefix/legacy message parsing needs them). Document which intents each cog requires. |

### 1.5 Unhandled interaction expiry on button defer

| Field | Detail |
|---|---|
| **Location** | `features/bytedaily/views.py` — `DynamicAnswerButton.callback`, `DynamicResultButton.callback` (first line `await interaction.response.defer(ephemeral=True)`) |
| **Why** | If the interaction token already expired (`discord.NotFound` / `InteractionResponded`), the bare defer raises. The exception can surface as an unhandled interaction error; followups never run. Under Render sleep / cold start this is the primary user-visible failure mode. |
| **Recommendation** | Wrap defer in `try/except (discord.NotFound, discord.HTTPException)` and return immediately on failure (same pattern as `rolling_window.safe_delete_message`). Do not run DB work if defer failed. |

### 1.6 Leaderboard recreate still scans channel history

| Field | Detail |
|---|---|
| **Location** | `features/bytedaily/services/leaderboard_service.py` — `_purge_bot_messages`, `_create_and_pin`, `refresh_leaderboard_embed` (fallback when saved ID is missing) |
| **Why** | Challenge-channel history scanning was removed, but leaderboard recreate still iterates `channel.history` and deletes messages one-by-one. On a busy channel or missing saved ID after deploy, this can 429 the bot while a close/rollover is also editing/posting. |
| **Recommendation** | Keep edit-in-place. On `NotFound`, create+pin **without** history purge (accept possible orphans), or delete only the previously known ID if still present. Align with Option A philosophy already applied to the challenge channel. |

### 1.7 Dual independent asyncpg pools on one DATABASE_URL

| Field | Detail |
|---|---|
| **Location** | `legacy/core/database.py` (`max_size=5`); `features/bytedaily/database/client.py` (`max_size=3`) |
| **Why** | Two pools → up to ~8 concurrent connections plus Supabase pooler limits. Under rollover (many `upsert_stats` + inserts) + legacy exams, connection exhaustion causes timeouts that look like “bot freeze” and can cascade into Discord interaction timeouts. |
| **Recommendation** | Prefer a single shared pool (or one pooler DSN with smaller max sizes). Cap total `max_size` to fit Supabase plan. Add health checks that fail soft when `bd_db.is_connected` is False before slash/button DB work. |

### 1.8 Secrets / sensitive artifacts hygiene

| Field | Detail |
|---|---|
| **Location** | `config.py` loads `.env` via sync `open`; `legacy/core/logger.py` writes `bot.log` at repo root; `.gitignore` ignores `.env` but **not** `bot.log`; Gemini URL in `ai_generator_service.py` embeds `?key=` |
| **Why** | Accidental commit of `bot.log` can leak tokens, user IDs, or API error bodies. API keys in query strings appear in proxies/access logs more easily than header-based auth. Default `BOT_API_KEY` compounds risk (see 1.1). |
| **Recommendation** | Add `bot.log`, `*.log` to `.gitignore`. Never log full request URLs containing keys. Refuse to start without strong `DISCORD_TOKEN` / `BOT_API_KEY` / `DATABASE_URL` in production (`RENDER` env detection). |

---

## 2. BEST PRACTICES (Recommended Enhancements)

### 2.1 Replace `SELECT *` with explicit column lists

| Field | Detail |
|---|---|
| **Location** | `question_repo.py`, `poll_repo.py`, `answer_repo.py`, `user_repo.py` (`get_by_id`, `get_leaderboard`, `get_all_for_poll`, etc.) |
| **Why** | Pulls unused columns over the wire; couples code to table shape; complicates future migrations (e.g. large `explanation` text when only IDs needed). |
| **Recommendation** | Define small column sets per use case (list/card vs full question for embeds). Keep `get_by_id` for embeds; use lean projections for existence/rank checks. |

### 2.2 Batch point awards on poll close

| Field | Detail |
|---|---|
| **Location** | `poll_service.close_poll` — loop calling `user_repo.upsert_stats` per answer |
| **Why** | N sequential round-trips during the hottest path (close). Extends `_is_processing` and pool hold time. |
| **Recommendation** | Add a SQL function that accepts arrays / JSON of `(user_id, is_correct, points)` and upserts in one transaction, or use `executemany` / a single `unnest` UPDATE. |

### 2.3 Guard ByteDaily commands when DB pool failed to init

| Field | Detail |
|---|---|
| **Location** | `features/bytedaily/database/client.py` (`initialize` sets `is_connected=False` on failure); cog slash commands and views assume DB works |
| **Why** | Failed init currently logs and continues. First button/slash then raises `RuntimeError: pool is not initialized`, often after defer → poor UX and error spam. |
| **Recommendation** | Early check `bd_db.is_connected` after defer; followup a clear “database unavailable” embed. Optionally keep scheduler stopped until connected. |

### 2.4 Standardize Discord error handling on all interaction paths

| Field | Detail |
|---|---|
| **Location** | ByteDaily: `views.py`, `cog.py`; Legacy: `legacy/views/exam_views.py` (`process_answer` still uses `response.send_message` without defer), `legacy/cogs/*.py` |
| **Why** | Inconsistent defer/followup; bare `except Exception`; legacy exam answers risk 3s timeout if DM/role work runs before ack. |
| **Recommendation** | Shared helpers: `defer_ephemeral`, `followup_embed`, catch `NotFound`/`Forbidden`/`HTTPException` explicitly. Migrate legacy exam answer flow to defer-first like ByteDaily. |

### 2.5 Reduce redundant admin permission checks

| Field | Detail |
|---|---|
| **Location** | `features/bytedaily/cog.py` — every admin command has `@app_commands.default_permissions(administrator=True)` **and** manual `guild_permissions.administrator` |
| **Why** | Discord already hides/blocks non-admins with `default_permissions`. Manual check is defense-in-depth but duplicates noise; DM context (`guild` is None) can throw if not guarded. |
| **Recommendation** | Keep one authoritative check (prefer decorator + `interaction.guild` null-guard). Extract `_require_admin(interaction) -> bool` helper for consistency. |

### 2.6 Remove or quarantine unused sync dependencies

| Field | Detail |
|---|---|
| **Location** | `requirements.txt` — `flask`, `requests`, `supabase`, `python-dotenv` (config uses a custom loader; no `flask`/`requests`/`supabase` imports found) |
| **Why** | Dead deps increase install surface and tempt future sync HTTP (`requests`) on the event loop. |
| **Recommendation** | Trim unused packages or document why they remain. If dotenv is desired, use it and delete the custom sync parser—or keep the custom parser and drop `python-dotenv`. |

### 2.7 Avoid sync filesystem I/O on the event loop

| Field | Detail |
|---|---|
| **Location** | `config._load_env` (`open` at import — startup only); `leaderboard_service._load_legacy_message_id` (`Path.read_text`) during refresh |
| **Why** | Import-time open is acceptable once. Legacy JSON read during an async refresh can block the loop on slow disks (rare but easy to eliminate). |
| **Recommendation** | Migrate fully to `bd_settings` (already primary path) and delete legacy file fallback, or `asyncio.to_thread` for the one-shot migration read. |

### 2.8 Track background tasks; cancel on shutdown

| Field | Detail |
|---|---|
| **Location** | `main.py` keepalive `create_task` (cancelled in `close` — good); `legacy/core/exam_engine.py` — fire-and-forget `asyncio.create_task(_cleanup_dm_messages(...))` |
| **Why** | Untasked cleanup can outlive cog unload / raise “Task was destroyed but pending”; errors may be lost without `task.add_done_callback`. |
| **Recommendation** | Store tasks on the bot, `add_done_callback` for logging, cancel in `close` / cog_unload. |

### 2.9 Logging volume of the 15s scheduler tick

| Field | Detail |
|---|---|
| **Location** | `scheduler._check_loop` — `log.info("[Scheduler] Checking active challenge...")` every 15s |
| **Why** | Noise on Render free logs; obscures real warnings; cost/retention. |
| **Recommendation** | Use `DEBUG` for routine ticks; `INFO` only on state transitions (wait → close → post). |

### 2.10 Question bank empty / AI insert validation

| Field | Detail |
|---|---|
| **Location** | `question_service.pick_next_question` raises `RuntimeError`; `ai_generator_service.generate_and_store_questions` inserts without dedup |
| **Why** | Empty bank crashes post path; AI may insert near-duplicates every midnight. |
| **Recommendation** | Soft-fail post with admin-visible log/alert embed; optional uniqueness on normalized `question_text`; cap `/bytedaily-generate` against daily quota. |

### 2.11 Partial message delete skips unpin

| Field | Detail |
|---|---|
| **Location** | `rolling_window.safe_delete_message` (post Option A) |
| **Why** | Deleting pinned messages usually works, but Discord may leave pin-related system messages; no unpin step anymore. |
| **Recommendation** | Accept as tradeoff, or best-effort `fetch`+`unpin` only when delete returns Forbidden related to pins (edge case). Document admin cleanup expectation. |

---

## 3. NICE-TO-HAVE (Luxury / Technical Polish)

### 3.1 Structured logging & correlation IDs

| Field | Detail |
|---|---|
| **Location** | `legacy/core/logger.py`; call sites across scheduler / cog / views |
| **Why** | String-only logs make it hard to filter one poll’s lifecycle across close → DM → leaderboard → post. |
| **Recommendation** | JSON or key=value logs with `poll_id`, `user_id`, `interaction_id`. Optional OpenTelemetry later. |

### 3.2 Execution timing metrics around rollover stages

| Field | Detail |
|---|---|
| **Location** | `scheduler._rollover`, `_close_poll`, `_post_question`, `_dm_personal_results`, `leaderboard_service.refresh_leaderboard_embed` |
| **Why** | Without timings, regressions (slow Supabase, Discord 429) are guesswork. |
| **Recommendation** | Log durations per stage (`close_db_ms`, `discord_delete_ms`, `post_ms`, `dm_ms`). Alert if close > N seconds. |

### 3.3 Deduplicate admin slash boilerplate

| Field | Detail |
|---|---|
| **Location** | `features/bytedaily/cog.py` — repeated defer + admin check + try/except followup |
| **Why** | Large cog, copy-paste error risk when adding commands. |
| **Recommendation** | Decorator `@ephemeral_admin_command` that defers, checks admin, maps exceptions to error embeds. |

### 3.4 Shared Discord message-ID delete utility

| Field | Detail |
|---|---|
| **Location** | `rolling_window.safe_delete_message` vs similar fetch/edit patterns in `poll_service._refresh_challenge_countdown` and leaderboard |
| **Why** | Parallel implementations of “touch message by ID safely”. |
| **Recommendation** | One `discord_messages.py` helper module for delete/edit/pin with standardized exceptions. |

### 3.5 Embed / UX polish

| Field | Detail |
|---|---|
| **Location** | `features/bytedaily/embeds.py`; bilingual mix in `cog.py` (Arabic descriptions, English embed titles in places) |
| **Why** | Inconsistent locale hurts polish; minor copy drift between buttons and slash replies. |
| **Recommendation** | Single locale policy (or i18n map); unify success/error embed builders already in `features/shared/embed_helpers.py`. |

### 3.6 Health endpoint enrichment (careful)

| Field | Detail |
|---|---|
| **Location** | `legacy/api/server.py` — `/api/health` |
| **Why** | Useful for ops (pool up, scheduler running, open poll id) but can leak internals if public. |
| **Recommendation** | Public: `status` + `bot_ready` only. Detailed diagnostics behind API key. |

### 3.7 Integration / smoke tests

| Field | Detail |
|---|---|
| **Location** | No automated test suite observed for ByteDaily repos/scheduler |
| **Why** | Regressions in defer-first, single-open-poll, and rolling-window deletes are currently manual. |
| **Recommendation** | Pytest + asyncpg test DB (or mocked `bd_db`) for `close_poll` idempotency, `safe_delete_message` null/NotFound, and “only one open poll” constraint. |

### 3.8 Type consistency / Optional cleanup

| Field | Detail |
|---|---|
| **Location** | Mixed `Optional` usage; scheduler `Dict[str, Any]` poll blobs |
| **Why** | Harder IDE navigation; typos in `poll["message_id"]` vs settings keys. |
| **Recommendation** | TypedDicts for poll/question/answer rows at the repository boundary. |

---

## Priority matrix (quick view)

| ID | Tier | Theme | Primary files |
|---|---|---|---|
| 1.1 | MUST | Security — default API key | `config.py`, `legacy/api/server.py` |
| 1.2 | MUST | Race — double open poll | `scheduler.py`, `poll_repo.py` |
| 1.3 | MUST | Perf — DMs block rollover | `scheduler.py` |
| 1.4 | MUST | Security/privacy — intents | `main.py` |
| 1.5 | MUST | Stability — defer NotFound | `views.py` |
| 1.6 | MUST | Rate limits — LB history purge | `leaderboard_service.py` |
| 1.7 | MUST | Stability — dual pools | `database.py`, `client.py` |
| 1.8 | MUST | Security — log/secret hygiene | `logger.py`, `.gitignore`, AI service |
| 2.x | BEST | Queries, guards, deps, tasks | repos, cog, requirements |
| 3.x | NICE | Metrics, DX, tests, i18n | cross-cutting |

---

## Explicit non-goals / out of scope for this audit

- No code patches, refactors, or dependency upgrades were applied.
- Runtime profiling and live Discord/Supabase metrics were not collected (static review only).
- Content quality of `legacy/DATA.py` exam questions was not reviewed beyond noting it is a large in-repo dataset.

---

## Suggested implementation order (when you choose to act)

1. **1.1 + 1.8** — secrets and startup guards (hours).  
2. **1.2** — lock + unique open-poll index (half day).  
3. **1.3 + 1.5** — decouple DMs from rollover; harden button defer (half day).  
4. **1.6 + 1.7** — leaderboard purge removal; pool consolidation (half–1 day).  
5. **1.4 + 2.x** — intents trim and best-practice sweep.  
6. **3.x** — polish as capacity allows.

---

*End of audit report.*
