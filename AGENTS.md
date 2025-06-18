# Agent Instructions

## Overview
This repository contains the `lair` Python package. Before submitting any pull requests that modify Python code or documentation, you must run the following checks and ensure they succeed:

1. `python -m compileall -q lair`
2. `ruff check lair`
3. `ruff format lair`
4. `pytest`
5. Code coverage must meet the configured threshold (run via pytest with coverage)

Before running these checks for the first time, install the project's dependencies using Poetry:

```sh
eval $(poetry env activate)
poetry install --with dev
```

These commands create a virtual environment, install `lair` into the path, and fetch all development dependencies so the
tools above work correctly.

Every pull request must update `CHANGELOG.md` with a short summary of its changes. New entries should be added under the top `# WIP -` heading.

Python files should wrap at 120 characters.  Markdown files should not have any forced wrapping.

## Style
- Prefer explicit imports and avoid wild-card imports when possible.
