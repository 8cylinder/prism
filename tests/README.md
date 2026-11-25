# Prism tests

Tests use pytest, pytest-asyncio, and pytest-cov. Branch coverage must stay at
or above 90%; the suite fails below that threshold.

## Test files

- `test_cli.py` — CLI options, input parsing, color handling, and errors.
- `test_config.py` — `config.toml`, legacy shortcuts, and `--config`.
- `test_completions.py` — generated bash completion behavior and installation.
- `test_app.py` — app startup, navigation, search, and key bindings.
- `test_app_extra.py` — additional action and watcher branches.
- `test_rendering.py` — rendering through the running Textual app.
- `test_renderers.py` — individual renderers and error paths.
- `test_git_hooks.py` — gitleaks pre-commit hook with a stub binary.
- `fixtures/` — fixture files used by parsing and rendering tests.

## Running tests

```bash
make test                 # all tests with branch coverage
uv run pytest -v          # verbose
uv run pytest tests/test_cli.py
uv run pytest tests/test_cli.py::TestFilenameParsing::test_parse_plain_path
```

Use `tmp_path` and `monkeypatch` for filesystem and environment changes.
Tests must not read or write the real user configuration directory, touch the
network, or require a real gitleaks binary.

## Adding tests

Add fixtures under `fixtures/` and coverage in the matching test module. When
adding a renderer, test both the fresh-widget and reused-widget paths, plus
parse errors.
