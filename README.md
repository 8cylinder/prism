# prism

View files found with command-line search tools in a split-pane terminal UI.

[![CI](https://github.com/8cylinder/prism/actions/workflows/ci.yml/badge.svg)](https://github.com/8cylinder/prism/actions/workflows/ci.yml)
[![License: GPL-3.0-only](https://img.shields.io/badge/license-GPL--3.0--only-blue.svg)](LICENSE)

Prism reads `find`, `rg`, and `grep` output, lists the matching files on the
left, and shows syntax-highlighted file contents on the right. Markdown, HTML,
JSON, CSV, TSV, and Org files can be rendered instead of shown as source.

## Requirements

- Python 3.13 or newer.
- Bash 4.4 or newer for `prism --completions`.
- bash-completion 2.18 or newer for automatic completion loading.
- gitleaks 8.19 or newer to commit to the repository. See the
  [gitleaks installation guide](https://github.com/gitleaks/gitleaks#installing).
- Linux or macOS.

## Installation

From PyPI, if published:

```console
$ uv tool install prism
```

From a source checkout:

```console
$ git clone https://github.com/8cylinder/prism
$ cd prism
$ make sync
$ make install
```

`make install` installs the command with `uv tool install --editable`, then
installs the bash completion script and the man page into the user's XDG
directories. It does not require `sudo`.

## Quick start

Pipe `rg` output into prism:

```console
$ rg 'search string' --line-number | prism
```

Open a set of files directly:

```console
$ find . -iname '*.py' | prism
```

Use null-terminated paths for filenames containing spaces:

```console
$ find . -name '*.py' -print0 | prism --null
```

## Command reference

```console
$ prism --help
$ prism -h
```

| Option | Description |
| --- | --- |
| `-n`, `--null` / `--no-null` | Treat input as null-terminated instead of newline-terminated. |
| `--debug-data` | Print the parsed file data and exit. |
| `--color [auto\|always\|never]` | Control colored command-line output. Defaults to `auto`; the TUI keeps its own colors. |
| `--config` | Print the configuration file path and exit. |
| `--completions` | Write a bash completion script and exit. |
| `--version` | Print the version and exit. |
| `-h`, `--help` | Show help and exit. |

Accepted input formats:

```text
/path/to/file
/path/to/file:match_string
/path/to/file:line_number:match_string
```

Prism opens the file view when it starts. Key bindings are shown in the
footer; `q` quits, `f` cycles the file list, `m` toggles rendered view, `w`
toggles word wrap, `/` searches, and `e` opens the highlighted file in
`$EDITOR`.

## Configuration

Run `prism --config` to print the platform-specific path:

```console
$ prism --config
/home/user/.config/prism/config.toml
```

If the file is missing, prism uses its built-in defaults. Create
`config.toml` to override key bindings:

```toml
[[shortcuts]]
key = "f"
action = "toggle_files"
description = "Toggle Files"

[[shortcuts]]
key = "m"
action = "toggle_view_mode"
description = "Render"
```

Each shortcut accepts `key`, `action`, and `description`, plus optional
`show`, `key_display`, and `priority` values. Unknown keys produce a warning
on stderr and are ignored.

Precedence is:

1. `config.toml`
2. the legacy `shortcuts.json` file (a deprecation warning is printed)
3. built-in defaults

An invalid TOML file is an error; prism names the path and exits nonzero.

## Bash completions

Generate the completion script:

```console
$ prism --completions
/home/user/.local/share/bash-completion/completions/prism.bash
To use it in this shell:
  source /home/user/.local/share/bash-completion/completions/prism.bash
```

The path is written to stdout; the `source` instruction goes to stderr, so
command substitution receives only the path.

The script is static. Re-run `prism --completions` after changing commands or
options. Bash 4.4 or newer is required, and bash-completion 2.18 or newer is
needed for automatic loading. Run `make install-completions` to install it.

On macOS, `/bin/bash` is version 3.2 and the default login shell is zsh.
Install a newer bash, for example with `brew install bash`; zsh is not
supported.

## Man page

After `make install`, view the manual with:

```console
$ man prism
```

`make man` builds the page at `docs/_build/man/prism.1` without installing it.
If the page is not found, add the install directory to `MANPATH`:

```console
$ export MANPATH="$HOME/.local/share/man:$MANPATH"
```

`uv tool install` from PyPI installs the command but not the man page; use
`make install-man` from a source checkout.

## Development

```console
$ make sync        # install dependencies
$ make hooks       # install the gitleaks pre-commit hook
$ make fmt         # format with ruff
$ make fmt-check   # check formatting
$ make lint        # lint and apply safe fixes
$ make lint-check  # lint without changes
$ make type        # type-check with ty
$ make test        # run tests with branch coverage
$ make check       # run every check without modifying files
$ make build       # build the wheel and sdist in dist/
```

`make hooks` is run once per clone and configures `core.hooksPath`. The hook
blocks commits containing secrets and requires gitleaks 8.19 or newer.
`git commit --no-verify` bypasses the hook; `make secrets` and the CI workflow
remain the enforceable gate.

Run a single test with:

```console
$ uv run pytest tests/test_cli.py::TestFilenameParsing::test_parse_plain_path
```

## License

Prism is licensed under GPL-3.0-only. See [LICENSE](LICENSE).

Copyright (C) 2026 Sheldon McGrandle.

## Links

- [Repository](https://github.com/8cylinder/prism)
- [Issues](https://github.com/8cylinder/prism/issues)
