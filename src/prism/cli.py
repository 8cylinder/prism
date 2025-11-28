import click
import sys
import os
import importlib.metadata
from pathlib import Path
from pprint import pprint as pp  # noqa
from .prism import Prism
from .prism import FileData


__version__ = importlib.metadata.version("prism")


def parse_stdin(raw: str, null_sep: bool) -> list[FileData]:
    split_char = "\x00" if null_sep else "\n"
    raw = raw.strip(split_char)  # find appends a null byte to the end of the string
    names = raw.split(split_char)
    parsed_names: list[FileData] = []
    for i in names:
        parsed_name = parse_filename(i)
        if parsed_name:
            parsed_names.append(parsed_name)
    return parsed_names


def parse_filename(raw: str) -> FileData | None:
    """Parse a stdin line into a list of file data.

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
    if filename.is_dir():
        click.echo(f'Skipping directory: "{filename}"', err=True)
        return None
    elif not filename.exists():
        raise click.BadParameter(f"Path '{file_data[0]}' does not exist.")

    data = FileData(filename, 0, "")
    print(file_data)

    # exit()
    if len(file_data) == 2:
        data.match_string = file_data[1]
    elif len(file_data) == 3:
        data.line_num = int(file_data[1])
        data.match_string = file_data[2]
    return data


CONTEXT_SETTINGS = {
    "help_option_names": ["-h", "--help"],
}


@click.command(context_settings=CONTEXT_SETTINGS)
# @click.argument('files', type=click.File(), nargs=-1)
@click.argument("search_results", nargs=-1)
@click.option(
    "--null/--no-null",
    "-n/ ",
    default=False,
    help="Whether or not the filenames are null terminated or space separated.",
)
@click.option("--debug-data", is_flag=True)
@click.version_option(__version__)
def prism(search_results: str, null: bool, debug_data: bool) -> None:
    """View files found with various means, find, rg, grep.

    \b
    Example usage
    -------------

    \b
    rg 'search string' | prism
    rg 'search string' -t py --only-matching | prism
    rg 'search string' -o | prism
    grep 'search string' -Hn * | prism
    find -iname "*py" -exec grep -Hn 'search string' {} \\; | prism
    find -iname "*py" -print0 | xargs --null grep --with-filename --line-number 'search string' | prism
    find -path "**prism/*py" -print0 | prism --null

    \b
    While dev
    ---------

    \b
    ... | uv run prism -h
    ... | uv run textual run --dev prism:prism -h
    """

    if search_results:
        # is tty true
        filenames = search_results
        filenames = '\n'.join(filenames)

    elif sys.stdin.isatty():
        print("No input in pipe.")
        sys.exit(1)
    else:
        # is tty false
        filenames = sys.stdin.read()
        # https://github.com/Textualize/textual/issues/3831#issuecomment-2090349094
        sys.__stdin__ = open("/dev/tty", "r")

    # print('is tty:', sys.stdin.isatty())
    # exit(0)
    # pp(os.ttyname(sys.stdout.fileno()))
    # exit()
    filenames = parse_stdin(filenames, null)

    if debug_data:
        pp(filenames)
    else:
        app = Prism(files=filenames)
        app.run()
