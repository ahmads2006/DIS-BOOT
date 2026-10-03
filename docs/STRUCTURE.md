# Boot — Project Structure Reference

> Last updated: 2026-10-03

---

## Directory Layout

```text
Boot/
├── main.py                    Entry point. Creates DeveloperBot, loads all cogs,
│                               syncs slash commands, registers persistent views,
│                               starts API server.
├── config.py                  Loads .env, exports all settings as module constants.
│                               Shared by both legacy and new code.
├── .env                       Secrets (not in git). DISCORD_TOKEN, DATABASE_URL, etc.
│
├── legacy/                    ── FROZEN legacy code (exam system, onboarding) ──
│   ├── __init__.py
│   ├── DATA.py                Static exam question bank
│   ├── core/
│   │   ├── __init__.py
│   │   ├── logger.py          Singleton `log` logger (console + bot.log)
│   │   ├── state.py           In-memory dicts: active_exams, onboarding_sent_to
│   │   ├── cooldowns.py       Re-exports COOLDOWN_SECONDS
│   │   ├── database.py        Legacy asyncpg pool (DatabaseLayer, singleton `db`)
│   │   └── exam_engine.py     All exam business logic
│   ├── cogs/
│   │   ├── __init__.py
│   │   ├── admin.py           /reset-cooldown, /exam-history, /active-exams, /setup-exam-panel
│   │   ├── exam.py            /exam, /cancel-exam
│   │   ├── onboarding.py      Auto-DM on member join/role grant
│   │   └── stats.py           /stats (global exam statistics)
│   ├── views/
│   │   ├── __init__.py
│   │   ├── exam_views.py      ExamSelectView, QuestionView, ExamPanelLaunchView (persistent)
│   │   ├── onboarding_views.py  Language/Level/Specialization select views
│   │   ├── exam_select.py     Backward-compat bridge
│   │   ├── onboarding_view.py Backward-compat bridge
│   │   └── question_view.py   Backward-compat bridge
│   └── api/
│       ├── __init__.py
│       ├── server.py          AsyncAPIServer (aiohttp): /health, /api/start-exam
│       └── api.py             Backward-compat bridge
│
├── features/                  ── New feature modules ──
│   ├── __init__.py
│   ├── bytedaily/             ByteDaily: periodic programming questions
│   │   ├── __init__.py
│   │   ├── cog.py             Discord Cog: /leaderboard, starts scheduler
│   │   ├── scheduler.py       Background loop: post → close → delete → repeat
│   │   ├── views.py           Answer buttons (A–D), "Show my result" button
│   │   ├── constants.py       Timing, colors, custom IDs, point values
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── question_service.py   Pick next question, avoid recent repeats
│   │   │   ├── poll_service.py       Create/close/delete polls, award points
│   │   │   └── stats_service.py      Leaderboard queries, user stats
│   │   └── database/
│   │       ├── __init__.py
│   │       ├── client.py             Independent asyncpg pool (bd_db singleton)
│   │       ├── migrations/
│   │       │   └── 001_create_bd_tables.sql   Full DDL (run in Supabase SQL Editor)
│   │       └── repositories/
│   │           ├── __init__.py
│   │           ├── question_repo.py  CRUD for bd_questions
│   │           ├── poll_repo.py      CRUD for bd_polls
│   │           ├── answer_repo.py    CRUD for bd_answers
│   │           └── user_repo.py      CRUD for bd_users + RPC call
│   └── shared/
│       ├── __init__.py
│       └── embed_helpers.py   Reusable embed factory functions
│
├── bridge/                    ── Isolation layer ──
│   ├── __init__.py
│   └── legacy_adapter.py     ONLY contact point: features/ → legacy/
│
└── docs/
    └── STRUCTURE.md           This file
```

---

## Architecture Rules

### 1. Legacy Isolation

- Everything under `legacy/` is **frozen**. No behavior changes, no refactoring, no deletions.
- New code (`features/`, `bridge/`) must **never** import from `legacy/` directly.
- All contact from new code to legacy goes exclusively through `bridge/legacy_adapter.py`.

### 2. Database Separation

| Pool | File | Singleton | Tables |
|---|---|---|---|
| Legacy | `legacy/core/database.py` | `db` | `cooldowns`, `exam_history` |
| ByteDaily | `features/bytedaily/database/client.py` | `bd_db` | `bd_questions`, `bd_polls`, `bd_answers`, `bd_users` |

- Both pools connect to the same PostgreSQL database but are **independent objects**.
- ByteDaily tables are all prefixed `bd_` to prevent collision.
- ByteDaily has **no in-memory fallback** — the DB is required.

### 3. Feature Module Pattern

New features follow this structure inside `features/`:

```
features/<feature_name>/
├── cog.py              Discord extension entry point (load_extension target)
├── scheduler.py        Background task loops (if needed)
├── views.py            Discord UI components (Views, Buttons, Selects)
├── constants.py        All magic numbers and identifiers for this feature
├── services/           Business logic — NO Discord imports allowed here
│   └── *.py
└── database/
    ├── client.py       Independent connection pool
    ├── migrations/     SQL DDL files for this feature's tables
    └── repositories/   One file per table, pure SQL via asyncpg
        └── *.py
```

### 4. Config Access

- `config.py` stays at root, importable by all code (`from config import ...`).
- No feature creates its own `.env` loader — use `config.py`.
- Feature-specific env vars (e.g. `BD_CHANNEL_ID`) should be added to `config.py` or read via `os.getenv()` in `constants.py`.

### 5. Startup Order (`setup_hook` in `main.py`)

```
Step 1   Legacy DB init          await db.initialize()
Step 2   Legacy cog: onboarding  load_extension('legacy.cogs.onboarding')
Step 3   Legacy cog: exam        load_extension('legacy.cogs.exam')
Step 4   Legacy cog: admin       load_extension('legacy.cogs.admin')
Step 5   Legacy cog: stats       load_extension('legacy.cogs.stats')
Step 6   ByteDaily cog           load_extension('features.bytedaily.cog')
         └─ BD DB init + scheduler start happen inside cog_load()
Step 7   Slash command sync      tree.sync()  ← AFTER all extensions loaded
Step 8   Legacy persistent view  add_view(ExamPanelLaunchView)
Step 9   BD persistent views     add_view(ByteDailyAnswerView/ResultView) [for active polls]
Step 10  API server              AsyncAPIServer(self).start()
```

> [!IMPORTANT]
> The slash command sync (step 7) **must** come after all `load_extension` calls (steps 2–6).
> Loading a cog registers its slash commands with the tree; syncing before loading means those commands will never be registered.

### 6. Naming Conventions

| Thing | Convention |
|---|---|
| Feature name | **ByteDaily** (capital B, capital D, one word) |
| DB table prefix | `bd_` |
| Custom ID prefix | `bd_` |
| DB client singleton | `bd_db` |
| Cog class | `ByteDailyCog` |
| Scheduler class | `ByteDailyScheduler` |

---

## MVP Scope (Phase 1)

- ✅ Post question → answer buttons (A–D, one per user, no changes, ephemeral confirm)
- ✅ After 6 hours: close poll, award points + update streaks, post public stats summary
- ✅ "Show my result" button on the original question (ephemeral: choice, correct answer, explanation)
- ✅ After 4 more hours: delete both messages, post next question immediately
- ✅ `/leaderboard` slash command (top 10 by points)
- ❌ Automatic role grants — **deferred to future phase**
