"""Command-line interface for prism."""

from __future__ import annotations

import importlib.metadata
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

import click
from rich.console import Console
from rich.markup import escape

from .completions import completions_callback
from .config import ConfigError, config_callback, load_config
from .prism import FileData, Prism

ColorMode = Literal["auto", "always", "never"]

__version__ = importlib.metadata.version("prism")

ERROR_PREFIX = "[red]error:[/red]"
WARNING_PREFIX = "[yellow]warning:[/yellow]"


class _HelpOptions:
    """Give every command the same ``-h``/``--help`` option names."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        context_settings = dict(kwargs.pop("context_settings", {}) or {})
        context_settings.setdefault("help_option_names", ["-h", "--help"])
        super().__init__(
            *args,
            context_settings=context_settings,  # ty: ignore[unknown-argument]
            **kwargs,
        )


class AppCommand(_HelpOptions, click.Command):
    """A Click command with prism's standard help options."""


def make_console(color: ColorMode, *, stderr: bool = False) -> Console:
    """Create a Rich console for the selected color mode."""
    if color == "never":
        return Console(
            stderr=stderr,
            color_system=None,
            force_terminal=False,
            no_color=True,
        )
    if color == "always":
        return Console(stderr=stderr, force_terminal=True, no_color=False)

    force_color = os.environ.get("FORCE_COLOR")
    if force_color not in (None, "", "0"):
        return Console(stderr=stderr, force_terminal=True, no_color=False)

    if os.environ.get("NO_COLOR", ""):
        return Console(
            stderr=stderr,
            color_system=None,
            force_terminal=False,
            no_color=True,
        )

    return Console(stderr=stderr)


def _set_click_color(
    ctx: click.Context, _param: click.Parameter, value: ColorMode
) -> ColorMode:
    if value == "always":
        ctx.color = True
    elif value == "never":
        ctx.color = False
    else:
        ctx.color = None
    return value


def parse_stdin(
    raw: str,
    null_sep: bool,
    warn: Callable[[str], None] | None = None,
) -> list[FileData]:
    """Parse piped input into file entries."""
    split_char = "\x00" if null_sep else "\n"
    raw = raw.strip(split_char)  # find appends a null byte to the end
    if not raw:
        return []
    names = raw.split(split_char)
    parsed_names: list[FileData] = []
    for name in names:
        parsed_name = parse_filename(name, warn=warn)
        if parsed_name is not None:
            parsed_names.append(parsed_name)
    return parsed_names


def parse_filename(
    raw: str, warn: Callable[[str], None] | None = None
) -> FileData | None:
    """Parse a stdin line into file data.

    Possible formats:

    find:
      /path/to/file
    rg:
      /path/to/file:match_string
      /path/to/file:line_number:match_string
    grep:
      /path/to/file:match_string
      /path/to/file:line_number:match_string
    """
    file_data: list[str] = raw.split(":", 2)
    filename = Path(file_data[0])
    if warn is None:
        warn = lambda message: click.echo(message, err=True)
    if filename.is_dir():
        warn(f'Skipping directory: "{filename}"')
        return None
    if filename.is_symlink() and not filename.exists():
        warn(f'Skipping broken symlink: "{filename}"')
        return None
    if not filename.exists():
        raise click.BadParameter(f"Path '{file_data[0]}' does not exist.")

    data = FileData(filename, 0, "")

    if len(file_data) == 2:
        data.match_string = file_data[1]
    elif len(file_data) == 3:
        try:
            data.line_num = int(file_data[1])
        except ValueError as exc:
            raise click.BadParameter(
                f"Invalid line number in '{raw}': '{file_data[1]}'"
            ) from exc
        data.match_string = file_data[2]
    return data


def _read_input(search_results: tuple[str, ...], error_console: Console) -> str:
    """Return piped input or the command-line search results."""
    if search_results:
        return "\n".join(search_results)

    if sys.stdin.isatty():
        error_console.print(f"{ERROR_PREFIX} No input in pipe.")
        raise click.exceptions.Exit(1)

    raw_input = sys.stdin.read()
    if not raw_input:
        error_console.print(f"{ERROR_PREFIX} No search results to show.")
        raise click.exceptions.Exit(1)

    # Reopen stdin from /dev/tty for Textual.
    # https://github.com/Textualize/textual/issues/3831#issuecomment-2090349094
    try:
        sys.__stdin__ = open("/dev/tty", "r")  # noqa: SIM115
    except OSError:
        pass

    return str(raw_input)


def _warn(config_warnings: tuple[str, ...], console: Console) -> None:
    for warning in config_warnings:
        console.print(f"{WARNING_PREFIX} {escape(warning)}")


@click.command(cls=AppCommand)
@click.argument("search_results", nargs=-1)
@click.option(
    "--null/--no-null",
    "-n",
    default=False,
    help="Whether the filenames are null terminated.",
)
@click.option(
    "--debug-data",
    is_flag=True,
    help="Print parsed file data and exit.",
)
@click.option(
    "--color",
    type=click.Choice(["auto", "always", "never"], case_sensitive=False),
    default="auto",
    show_default=True,
    callback=_set_click_color,
    help="Control colored output.",
)
@click.option(
    "--config",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=config_callback,
    help="Print the config file path and exit.",
)
@click.option(
    "--completions",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=completions_callback,
    help="Write bash completions and exit.",
)
@click.version_option(package_name="prism", prog_name="prism")
def prism(
    search_results: tuple[str, ...],
    null: bool,
    debug_data: bool,
    color: ColorMode,
) -> None:
    """View files found with various means, find, rg, grep.

    \b
    Example usage
    -------------

    \b
    rg 'search string' --line-number | prism
    rg 'search string' -n | prism
    rg 'search string' -t py --only-matching | prism
    rg 'search string' -o | prism
    grep 'search string' -Hn * | prism
    find -iname '*py' | prism
    find -path "**prism/*py" -print0 | prism --null
    find -iname "*py" -exec grep -Hn 'search string' {} \\; | prism
    find -iname "*py" -print0 | xargs --null grep --with-filename --line-number 'search string' | prism
    find -iname '*py' | xargs grep -on 'search string' | prism
    """
    stderr = make_console(color, stderr=True)

    try:
        loaded = load_config()
    except ConfigError as exc:
        stderr.print(f"{ERROR_PREFIX} {escape(str(exc))}")
        raise click.exceptions.Exit(1) from exc

    _warn(loaded.warnings, stderr)

    raw_input = _read_input(search_results, stderr)
    parsed_files = parse_stdin(
        raw_input,
        null,
        warn=lambda message: stderr.print(
            f"{WARNING_PREFIX} {escape(message)}"
        ),
    )

    if debug_data:
        for file_data in parsed_files:
            click.echo(str(file_data))
        return

    if not parsed_files:
        stderr.print(f"{ERROR_PREFIX} No files to show.")
        raise click.exceptions.Exit(1)

    app = Prism(files=parsed_files, config=loaded.config)
    app.run()


def main() -> None:
    """Run the prism command."""
    prism(prog_name="prism")


if __name__ == "__main__":
    main()
