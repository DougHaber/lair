# Agent Instructions

## Overview
This repository contains the `lair` Python package. Before submitting any pull requests that modify Python code or documentation, you must run the following checks and ensure they succeed:

1. `python -m compileall -q lair`
2. `ruff lair`
3. `pytest`
4. Code coverage must meet the configured threshold (run via pytest with coverage)

Before running these checks for the first time, install the project's dependencies using Poetry:

```sh
eval $(poetry env activate)
poetry install --with dev
```

These commands create a virtual environment, install `lair` into the path, and fetch all development dependencies so the
tools above work correctly.

Every pull request must update `CHANGELOG.md` with a short summary of its changes. New entries should be added under the top `# WIP -` heading.

The first command verifies that all Python files compile. The second performs a static analysis pass for common issues. Warnings about unused imports from `__init__` files may be ignored, but new warnings should be investigated. The third command runs the test suite with coverage reporting. All tests MUST pass and coverage must remain above the configured threshold.

Python files should wrap at 120 characters.  Markdown files should not have any forced wrapping.

## Style
- Use `logger.warning` instead of the deprecated `logger.warn`.
- Prefer explicit imports and avoid wild-card imports when possible.
