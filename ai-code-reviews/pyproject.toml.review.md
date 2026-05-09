# Review: pyproject.toml

Overall quality: Good

Refactoring effort: Low

## Findings

1. Console script points to a missing module
   - Line `63` declares `thaqib = "thaqib.cli:main"`, but no `src/thaqib/cli.py` was found in the tracked source list.
   - Suggestion: add the CLI module or remove the script entry.

2. Ruff config uses legacy top-level keys
   - Lines `68-72` define `select` and `ignore` under `[tool.ruff]`.
   - Modern Ruff prefers `[tool.ruff.lint]`.
   - Suggestion: migrate config to avoid warnings as Ruff versions advance.

3. Dependency versions are broad
   - Lines `26-45` use lower bounds only.
   - Maintainability impact: CV/ML stacks can break with major transitive changes.
   - Suggestion: use a lock file or constraints file for reproducible deployments.

4. No coverage thresholds
   - Lines `80-82` configure pytest but not coverage gates.
   - Suggestion: add `pytest-cov` config and minimum coverage for non-video API/service code.

## What Works

- The project uses a proper `src` layout and declares Python version/classifiers.
- Dev dependencies include pytest, Ruff, mypy, and pre-commit.
