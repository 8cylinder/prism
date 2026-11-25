# CLAUDE.md

This file provides guidance to coding agents working in this repository.

## Project overview

Prism is a TUI for viewing and navigating files found with CLI search tools
(`find`, `rg`, `grep`). It shows a file list on the left and
syntax-highlighted or rendered file contents on the right.

Key dependencies:

- `textual` for the TUI.
- `click` for the CLI.
- `rich` for console output and rendering.
- `platformdirs` for the user configuration path.

## Development commands

```bash
make sync        # install dependencies
make fmt         # format with ruff
make fmt-check   # check formatting
make lint        # lint and apply safe fixes
make lint-check  # lint without changes
make type        # type-check with ty
make test        # run tests with branch coverage
make check       # all checks without modifying files
make man         # build docs/_build/man/prism.1
make build       # build the wheel and sdist
```

Run a single test with:

```bash
uv run pytest tests/test_cli.py::TestFilenameParsing::test_parse_plain_path
```

`make hooks` installs the gitleaks pre-commit hook. It is run once per clone.
`make secrets` scans the full history and is also run in CI.

## Standards

- Format and lint with ruff (`line-length = 80`); do not add black or mypy.
- Type-check with ty. Use targeted `# ty: ignore[rule]` comments only; do not
  add blanket `# type: ignore` comments.
- Tests use pytest and pytest-asyncio. Branch coverage must stay at or above
  90%; `pytest` fails below that threshold.
- Use `src/` for application code and `tests/` for tests.
- Do not modify files outside this repository or write to the real user home
  directory in tests. Use `tmp_path` and `monkeypatch` with `XDG_CONFIG_HOME`,
  `XDG_DATA_HOME`, and `HOME`.

## Entry point and CLI

`src/prism/cli.py` defines the `prism` Click command, the `main()` entry point
used by `pyproject.toml`, input parsing, and global options:

- `--null/--no-null`
- `--debug-data`
- `--color [auto|always|never]`
- `--config`
- `--completions`
- `--version`
- `-h/--help`

Keep the CLI layer thin: parse and validate input in `cli.py`; put behavior in
the app and helper modules. Errors go to stderr. `--version`, `--config`, and
`--completions` must produce plain output with no ANSI codes.

## Configuration

`src/prism/config.py` loads `config.toml` from
`platformdirs.user_config_dir("prism")`. The file may contain a
`[[shortcuts]]` list. Precedence is `config.toml`, the legacy
`shortcuts.json` (warned about), then `DEFAULT_BINDINGS` in `prism.py`.
Unknown keys warn and are ignored; invalid TOML is a fatal error naming the
path.

`src/prism/completions.py` generates and installs a static bash completion
script. Bash 4.4 or newer is required. The output path goes to stdout; the
`source` hint and warnings go to stderr.

## Application

`src/prism/prism.py` contains the Textual app:

- `FileData` describes a file, line number, match string, and editor column.
- `FileListItem` renders one row of the file list.
- `Prism` composes the header, list, search input, code view, and footer.
- Key bindings: `f` cycles the file list, `e` edits, `n/j` and `p/k` move
  between results, `right/i` and `left/u` move between files, `w` toggles word
  wrap, `m` toggles rendered view, `/` searches, `q` quits.

`src/prism/renderers.py` holds the renderer registry. Specific renderers run
first; `SourceCodeRenderer` is the fallback. Markdown, HTML, JSON, CSV, TSV,
and Org files render when the view mode is `markdown`.

`src/prism/css/prism.tcss` holds all styling. Use Textual CSS theme variables
rather than hard-coded colors in Python.

## Tests

Tests are organized by area:

- `tests/test_cli.py` — CLI options, parsing, color, errors.
- `tests/test_config.py` — TOML and legacy config loading, `--config`.
- `tests/test_completions.py` — generated script behavior and installation.
- `tests/test_app.py` / `tests/test_app_extra.py` — TUI behavior and actions.
- `tests/test_rendering.py` / `tests/test_renderers.py` — rendering modes.
- `tests/test_git_hooks.py` — gitleaks pre-commit hook with a stub binary.
- `tests/fixtures/` — fixture files for rendering and parsing tests.

Add fixtures under `tests/fixtures/` when adding a new file type or renderer.
