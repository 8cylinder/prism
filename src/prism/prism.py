import sys
import os
import re

from rich.syntax import Syntax
from rich.traceback import Traceback
from textual.strip import Strip
from rich.segment import Segment
from rich.style import Style

from textual.scroll_view import ScrollView
from textual.app import App, ComposeResult, RenderResult
from textual.containers import Container, VerticalScroll, Horizontal, ScrollableContainer
from textual.reactive import var
# from textual.widgets import DirectoryTree, Footer, Header, Static
from textual.widget import Widget
from textual.widgets import Footer, Header, Static, Label, ListItem, ListView
from pathlib import Path
import click


class FileListItem(ListItem):
    def __init__(self, file_item: list, classname: str) -> None:
        super().__init__()
        self.file: Path = file_item[0]
        self.line_num: int = int(file_item[1])
        self.match_string: str = file_item[2]
        # self.highlight_range = (self.line_num, 0), (self.line_num, 1000)
        self.classname: str = classname

    # def get_highlight_range(self):
    #     return (self.line_num, 0), (self.line_num, 1000)

    def compose(self) -> ComposeResult:
        # see https://textual.textualize.io/guide/widgets/#segment-and-style
        # line_number = f' [bright_black]{self.line_num}[/]' if self.line_num else ''

        parent = ''
        if len(self.file.parts) > 1:
            parent = f'[b blue]{self.file.parent}/[/]'
        yield Label(
            f'{parent}[b bright_white]{self.file.name}[/] [green]{self.line_num}[/]',
            classes=''
        )

        # with Container(classes='file-list-item'):
        #     yield Label(f'[b]{self.file.name}[/b]{line_number}', classes='fname')
        #     yield Label(f'{self.file.parent}/', classes='path', expand=True, shrink=True)


class Prism(App):
    """View files found."""

    CSS_PATH = "css/prism.tcss"
    BINDINGS = [
        ("f", "toggle_files", "Toggle Files"),
        ("q", "quit", "Quit"),
    ]
    ENABLE_COMMAND_PALETTE = False

    show_files = var(True)

    def __init__(self, files):
        self.files = files
        super().__init__()

    def watch_show_files(self, show_files: bool) -> None:
        """Called when show_files is modified."""
        self.set_class(show_files, "-show-files")

    def compose(self) -> ComposeResult:
        """Compose our UI."""

        self.log(self.files)
        items = []
        for i, ele in enumerate(self.files):
            classname = 'odd' if i % 2 else 'even'
            items.append(
                FileListItem(ele, classname)
            )

        yield Header()
        with Container():
            yield ListView(*items, id='file-list')
            with VerticalScroll(id="code-view"):
                yield Static(id="code", expand=True)
        yield Footer()

    def pretty_path(self, f):

        segments = [
            click.style(f'{f.parent}/', fg='yellow', dim=True),
            click.style(f.name, bold=True),
        ]
        return ''.join(segments)

    def on_mount(self) -> None:
        self.query_one(ListView).focus()
        self.title = ''

    def on_list_view_highlighted(
            self, event: ListView.Highlighted) -> None:
        line_num = event.item.line_num
        event.stop()
        code_view = self.query_one("#code", Static)
        try:
            syntax = Syntax.from_path(
                str(event.item.file),
                line_numbers=True,
                word_wrap=True,
                indent_guides=False,
                theme="github-dark",
                highlight_lines={line_num},
            )

            line = syntax.code.splitlines()[line_num - 1]
            match = re.search(event.item.match_string, line)
            pos = match.span()
            # self.log(event.item.match_string)
            # self.log(match.string)
            # self.log(line.replace(' ', 'x'))
            # self.log('-' * match.start())
            # self.log(match.start(), match.end(), match.span())

            highlight = Style(color='bright_white', bgcolor='green')
            syntax.stylize_range(highlight, (line_num, pos[0]), (line_num, pos[1]))

        except Exception:
            code_view.update(Traceback(theme="github-dark", width=None))
            self.title = "ERROR"
        else:
            code_view.update(syntax)
            scroll_offset = self.size.height // 3
            self.query_one("#code-view").scroll_to(
                y=int(event.item.line_num) - scroll_offset,
                animate=False,
            )
            self.title = self.pretty_path(event.item.file)  #str(event.item.file)

    def action_toggle_files(self) -> None:
        """Called in response to key binding."""
        self.show_files = not self.show_files
        self.log(self.show_files)
