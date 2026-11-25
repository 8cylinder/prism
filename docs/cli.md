# Command reference

```{eval-rst}
.. click:: prism.cli:prism
   :prog: prism
   :nested: full
```

## DESCRIPTION

prism displays search results from command-line tools. It accepts plain file
paths, `rg`/`grep` output with a match string, and `rg`/`grep` output with a
line number and match string. Input is normally piped on standard input; paths
may also be passed as arguments.

Results appear in a file list on the left and a syntax-highlighted view on the
right. Markdown, HTML, JSON, CSV, TSV, and Org files can be rendered instead of
shown as source.

## FILES

`$XDG_CONFIG_HOME/prism/config.toml`
: User configuration. On macOS this is
  `~/Library/Application Support/prism/config.toml`. Run `prism --config` to
  print the exact path for the current platform.

`$XDG_CONFIG_HOME/prism/shortcuts.json`
: Deprecated shortcut configuration. prism still reads it and warns on stderr;
  move the entries to `config.toml`.

`$XDG_DATA_HOME/bash-completion/completions/prism.bash`
: Completion script written by `prism --completions`. When
  `BASH_COMPLETION_USER_DIR` is set, its first non-empty entry is used
  instead of `$XDG_DATA_HOME`.

## ENVIRONMENT

`EDITOR`
: Editor used by the `e` key binding. Defaults to `nano`.

`NO_COLOR`, `FORCE_COLOR`, `TERM`
: Control colored command-line output when `--color=auto` is used.

`BASH_COMPLETION_USER_DIR`
: First search location for `prism --completions`.

`XDG_DATA_HOME`
: Used for completions when `BASH_COMPLETION_USER_DIR` is unset.

Bash completions require Bash 4.4 or newer. Automatic loading requires
bash-completion 2.18 or newer.

## SEE ALSO

prism source code and issue tracker:
<https://github.com/8cylinder/prism>
