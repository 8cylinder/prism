
import click
import sys
import os
from pathlib import Path
from pprint import pprint as pp
from textual import log

from prism.prism import Prism
# from textual.app import App


def parse_stdin(names, null_sep: bool) -> list:
    names = names.read()
    split_char = '\x00' if null_sep else '\n'
    names = names.strip(split_char)  # find appends a null byte to the end of the string
    names = names.split(split_char)
    parsed_names = []
    for i in names:
        parsed_name = parse_filename(i)
        if parsed_name:
            parsed_names.append(parsed_name)
    return parsed_names


def parse_filename(name: str) -> list:
    file_data: list = name.split(':', 2)
    file = Path(file_data[0])
    if file.is_dir():
        return []
    file_data[0] = file
    try:
        file_data[1] = int(file_data[1])
    except IndexError:
        # if no line number is found, append 0 and an empty
        # string since this is probably data from find.
        file_data.append(0)
        file_data.append('')
    except ValueError:
        return []
    if not file_data[0].exists():
        raise click.BadParameter(f"Path '{file_data[0]}' does not exist.")
    return file_data


CONTEXT_SETTINGS = {
    'help_option_names': ['-h', '--help'],
}
@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('files', type=click.File(), nargs=-1)
@click.option('--null/--no-null', '-n/ ', default=False,
              help='Whether or not the filenames are null terminated or space separated.')
@click.option('--debug-data', is_flag=True)
def prism(files: str, null: bool, debug_data: bool) -> None:
    """prism.

    \b
    rg 'search string' -t py --line-number
    rg 'search string' --line-number
    grep 'search string' -Hn *

    \b
    textual run prism.__main__ --help
    python -m prism --help
    """

    filenames = []
    for f in files:
        if f.name == '<stdin>':
            filenames += parse_stdin(f, null)
        else:
            filenames.append([Path(f.name)])

    sys.stdin = open('/dev/tty', 'r')

    if not files:
        raise click.BadParameter('No files found. ')

    if debug_data:
        pp(filenames)
    else:
        app = Prism(files=filenames)
        app.run()
