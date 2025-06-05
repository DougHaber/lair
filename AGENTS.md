# Agent Instructions

## Overview
This repository contains the `lair` Python package. Before submitting any pull
requests that modify Python code or documentation, you must run the following
checks and ensure they succeed:

1. `python -m compileall -q lair`
2. `pyflakes lair`

Every pull request must update `CHANGELOG.md` with a short summary of its
changes. New entries should be added under the top `# WIP -` heading.

The first command verifies that all Python files compile. The second performs a
static analysis pass for common issues. Warnings about unused imports from
`__init__` files may be ignored, but new warnings should be investigated.

## Style
- Use `logger.warning` instead of the deprecated `logger.warn`.
- Prefer explicit imports and avoid wild-card imports when possible.
