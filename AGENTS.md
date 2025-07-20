# Agent Instructions

Lair is a command line tool for working with generative AI.

- The `chat` interface and sub-command provide an interface built with prompt-toolkit and rich.
- The `comfy` commands use ComfyScript to run workflows on ComfyUI.
- The `util` command provides a unix-style interface for running requests against LLMs.

## Rules

### Tests

- Always maintain the defined code coverage levels.
- Include regression tests for bug fixes when practical.
- Tests MUST pass before submitting a PR.
- Tests MUST be written against all edge conditions and a wide variety of bad inputs.
- Provide unit tests for functions with clear inputs and outputs.
- NEVER mark tests as skipped or failx. Instead, fix them. Problems can not be ignored.
- NEVER hide code from coverage with `# pragma: no cover` or disable tests. Instead, write tests.
- Tests should cover all invalid inputs. Tests should test out real-world complicated flows. Please focus heavily on test coverage.
- Organize tests by type. Unit tests live under `tests/unit` and integration tests under `tests/integration`.
- Test files must have clear and descriptive names. Avoid vague suffixes such as `_additional`, `_more`, or `_new`.
- Use meaningful file splits only when necessary and ensure names reflect the content.
- Pytest markers are used for categorization:
  - `unit`: unit tests
  - `integration`: integration tests using sqlite

### Style

- Python 3.10+ is used, and code does not need to support older versions.
- Prefer explicit imports and avoid wild-card imports when possible.
- Python files should wrap at 120 characters.  Markdown files should not have any forced wrapping.
- Variable names should be clear and unabbreviated.  For example, `filters` is preferred over `filt`, `subscriptions` over `sub`, and `index` over `idx`.
  - Exceptions may exist in a few places, such as when working with libraries that have widely established variable naming practices or when writing short lambda lines, as long as it is clear.
- Design code for modularity and reuse wherever it is likely to be useful. If code isn't written for it and needs to be for a change, update the code to follow best practices.
- Follow clean code and DRY (don't repeat yourself) best practices strictly.
- All code should be clean, modern, and maintainable.
- Configuration files use YAML.
- Do not exceed a McCabe `max_complexity` of 7.
- Code readability is extremely important.
- All Python docstrings must follow a structured format with sections like Args, Returns, and Raises, using a consistent style (e.g., Google or NumPy).

### General

- Never install new dependencies unless explicitly asked to do so.
- NEVER do anything to change the scope or strictness of any validation (ruff check, ruff format, mypy, etc) unless explicitly asked.
- NEVER USE noqa!
  - If you really have a great reason, you MUST put the reason in the comment.
  - This should be extremely rare.
- Lair has a configuration system that allows end users to configure and theme nearly everything.
  - Always add new configuration options rather than hardcoding settings.

## Processes

### Project Setup

Install the project's dependencies using Poetry:

```sh
eval $(poetry env activate)
poetry install --with dev
```

You have network permissions to install all dependencies. If installation fails try again and make sure you are doing it properly. If you are unable to install all dependencies, abort the task.

### Completing a Request

The `CHANGELOG.md` file should be appended with new entries for any new features or fixes. Fixes to issues created within a PR or a branch that were never released should not be mentioned. New entries should be added under the top `# WIP -` heading.

Before submitting any pull requests that modify Python code or documentation, you must run the following checks and ensure they succeed:

1. `python -m compileall -q lair`
2. `ruff check lair`
3. `ruff format lair`
4. `mypy lair`
5. `pytest`

All tests and validations must pass without issues. Never turn off any validations, tests, or coverage requirements.
