# Review: .gitignore

Overall quality: Good

Refactoring effort: Low

## Findings

1. Ignored runtime artifacts are already tracked
   - Lines `121` and `123` ignore `alerts/` and `*/.vite/`.
   - `git ls-files` still shows hundreds of `alerts/...jpg` files and `frontend/.vite/deps/*`.
   - Suggestion: remove these files from Git index with `git rm --cached -r alerts frontend/.vite`, then commit the cleanup.

2. Archive output is not ignored
   - The repo contains an `archive/` directory, but `.gitignore` does not ignore it.
   - Suggestion: add `archive/` near line `121`.

3. Test bytecode is already ignored but tracked locally in listing
   - Lines `1-3` ignore `__pycache__`, but test listing showed `tests/__pycache__` files on disk.
   - Suggestion: ensure they are not tracked and clean local generated files when preparing commits.

## What Works

- The file correctly ignores `.env`, data, DBs, logs, model weights, video/audio outputs, node modules, and frontend dist.
