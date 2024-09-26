
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
    """View files found with various means, find, rg, grep.

    \b
    Example usage
    -------------

    \b
    rg 'search string' | prism -
    rg 'search string' -t py --line-number | prism -
    grep 'search string' -Hn * | prism -
    find -iname "*py" -exec grep -Hn 'search string' {} \; | prism -
    find -iname "*py" -print0 | xargs --null grep --with-filename --line-number 'search string' | prism -
    find -path "**prism/*py" -print0 | prism --null -

    \b
    While dev
    ---------

    textual run prism.__main__ --help
    textual run --dev -c python -m prism.__main__ -h

    Run `docker compose build` and `docker compose run prism`.  This
    will ensure there is an eviroment to run and test prism.

    In docker prism can be run via `python -m prism --help`.

    \b
    ... | python -m prism --debug-data -
    ... | textual run --dev prism.__main__ --debug-data -
    """

    filenames = []
    #pp(files)
    for f in files:
        if f.name == '<stdin>':
            filenames += parse_stdin(f, null)
        else:
            filenames.append([Path(f.name), 1, ''])

    sys.stdin = open('/dev/tty', 'r')

    if not files:
        raise click.BadParameter('No files found. ')

    if debug_data:
        pp(filenames)
    else:
        app = Prism(files=filenames)
        app.run()
