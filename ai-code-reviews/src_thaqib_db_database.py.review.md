# Review: src/thaqib/db/database.py

Overall quality: Good

Refactoring effort: Medium

## Findings

1. Database engine is created at import time
   - Lines `12-18` load settings and create the engine during module import.
   - Test impact: `pytest -q` failed before collection because settings validation ran while importing `src.thaqib.main`.
   - Suggestion: defer engine creation behind a factory or ensure tests set environment before importing the app.

2. SQL echo follows debug directly
   - Line `16` uses `echo=settings.debug`.
   - Security impact: SQL echo can leak parameters into logs if debug is accidentally enabled.
   - Suggestion: use a separate `sql_echo` setting and force it off in production.

3. SQLite detection is a string contains check
   - Line `17` uses `"sqlite" in settings.database_url`.
   - Suggestion: parse the SQLAlchemy URL or check `settings.database_url.startswith("sqlite")`.

## What Works

- `get_db()` correctly closes sessions in a `finally` block.
- `SessionLocal` uses explicit `autocommit=False` and `autoflush=False`.
