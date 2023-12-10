
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
    names = [parse_filename(i) for i in names]
    return names


def parse_filename(name: str) -> list:
    file_data = name.split(':', 2)
    file_data[0] = Path(file_data[0])
    if not file_data[0].exists():
        raise click.BadParameter(f"Path '{file_data[0]}' does not exist.")
    return file_data


def init(files, null):
    filenames = []
    for f in files:
        if f.name == '<stdin>':
            filenames += parse_stdin(f, null)
        else:
            filenames.append([Path(f.name)])

    sys.stdin = open('/dev/tty', 'r')

    # log('xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx')
    # log(filenames)

    app = Prism(files=filenames)
    # app = Prism()
    app.run()


CONTEXT_SETTINGS = {
    'help_option_names': ['-h', '--help'],
}
@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('files', type=click.File(), nargs=-1)
@click.option('--null/--no-null', '-n/ ', default=False,
              help='Whether or not the filenames are null terminated or space separated.')
def prism(files: str, null: bool) -> None:
    """prism.

    \b
    rg 'search string' -t py --line-number
    rg 'search string' --line-number
    grep 'search string' -Hn *

    \b
    textual run prism.__main__ --help
    python -m prism --help
    """

    init(files, null)
