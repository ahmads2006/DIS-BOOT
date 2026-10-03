"""
Bridge — Legacy Adapter.

This is the ONLY allowed contact point between ByteDaily (features/) and
legacy code (legacy/). ByteDaily code must NEVER import from legacy/ directly.
Instead, it imports from this module.

Current exports:
  - log : the shared logger instance (from legacy.core.logger)
           ByteDaily uses this so all output goes to the same bot.log file
           and console handler that legacy already configured.

Rules:
  - This file may import from legacy/ and from config.py
  - This file MUST NOT import from features/
  - Database config (DATABASE_URL) is imported directly from config.py
    by features/bytedaily/database/client.py — it does NOT go through here
  - Keep this file thin — re-export only, no business logic
  - Document every export with a comment explaining why it's needed
"""

# Re-export the logger so ByteDaily can log without importing legacy directly.
# Rationale: legacy/core/logger.py sets up the singleton with console + file
# handlers. Re-using the same logger instance ensures unified output in both
# the console and bot.log.
from legacy.core.logger import log  # noqa: F401

# TODO: Add future exports here as ByteDaily implementation needs them, with comments
