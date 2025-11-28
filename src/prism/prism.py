from pathlib import Path
import click
import dataclasses
import re
from typing import Any
import os
import subprocess
import sys

from rich.syntax import Syntax
from rich.traceback import Traceback
from rich.style import Style

from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.reactive import var

# from textual.widgets import DirectoryTree, Footer, Header, Static
from textual.widgets import Footer, Header, Static, Label, ListItem, ListView


@dataclasses.dataclass
class FileData:
    file: Path
    line_num: int
    match_string: str


class FileListItem(ListItem):
    # classes: str = "testid"
    data: FileData

    def __init__(self, file_item: FileData, classname: str) -> None:
        super().__init__()
        self.file: Path = file_item.file
        self.line_num: int = file_item.line_num
        self.match_string: str = file_item.match_string
        # self.highlight_range = (self.line_num, 0), (self.line_num, 1000)
        self.classname: str = classname
        self.data = file_item

    # def get_highlight_range(self):
    #     return (self.line_num, 0), (self.line_num, 1000)

    def compose(self) -> ComposeResult:
        # see https://textual.textualize.io/guide/widgets/#segment-and-style
        # line_number = f' [bright_black]{self.line_num}[/]' if self.line_num else ''

        parent = ""
        if len(self.file.parts) > 1:
            parent = f"[b blue]{self.file.parent}/[/]"
        yield Label(
            f"{parent}[b bright_white]{self.file.name}[/] [green]{self.line_num}[/]",
            classes="",
        )

        # with Container(classes='file-list-item'):
        #     yield Label(f'[b]{self.file.name}[/b]{line_number}', classes='fname')
        #     yield Label(f'{self.file.parent}/', classes='path', expand=True, shrink=True)


class Prism(App[Any]):
    """View files found."""

    CSS_PATH = "css/prism.tcss"
    BINDINGS = [
        ("l", "toggle_light", "Toggle light mode"),
        ("f", "toggle_files", "Toggle Files"),
        ('e', 'edit_file', 'Edit File'),
        ("q", "quit", "Quit"),
    ]
    ENABLE_COMMAND_PALETTE = False

    show_files = var(True)

    def __init__(self, files: list[FileData]) -> None:
        self.files = files
        super().__init__()

    def watch_show_files(self, show_files: bool) -> None:
        """Called when show_files is modified."""
        self.set_class(show_files, "-show-files")

    def compose(self) -> ComposeResult:
        """Compose our UI."""

        items = []
        for i, ele in enumerate(self.files):
            classname = "odd" if i % 2 else "even"
            items.append(FileListItem(ele, classname))

        yield Header()
        with Container():
            yield ListView(*items, id="file-list")
            with VerticalScroll(id="code-view"):
                yield Static(id="code", expand=True)
        yield Footer()

    def pretty_path(self, f: Path) -> str:
        segments = [
            click.style(f"{f.parent}/", fg="yellow", dim=True),
            click.style(f.name, bold=True),
        ]
        return "".join(segments)

    def on_mount(self) -> None:
        self.query_one(ListView).focus()
        self.title = ""

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        # print(event.item.__dict__)
        data = event.item.data
        line_num = data.line_num  # event.item.line_num
        event.stop()
        code_view = self.query_one("#code", Static)
        try:
            syntax = Syntax.from_path(
                str(data.file),
                line_numbers=True,
                word_wrap=True,
                indent_guides=False,
                theme="github-dark",
                highlight_lines={line_num},
            )
            line = syntax.code.splitlines()[line_num - 1]
            match = re.search(re.escape(data.match_string), line)
            if match:
                pos = match.span()
                highlight = Style(color="bright_white", bgcolor="orange4")
                syntax.stylize_range(highlight, (line_num, pos[0]), (line_num, pos[1]))

        except Exception:
            code_view.update(Traceback(theme="github-dark", width=None))
            self.title = "ERROR"
        else:
            code_view.update(syntax)
            scroll_offset = self.size.height // 3
            self.query_one("#code-view").scroll_to(
                y=int(line_num) - scroll_offset,
                animate=False,
            )
            self.title = self.pretty_path(data.file)  # str(event.item.file)

    def action_toggle_files(self) -> None:
        """Called in response to key binding."""
        self.show_files = not self.show_files
        self.log(self.show_files)

    def action_toggle_light(self) -> None:
        """An action to toggle dark mode."""
        self.theme = (
            "textual-dark" if self.theme == "textual-light" else "textual-light"
        )

    def action_edit_file(self) -> None:
        """Edit the file."""
        list_view: ListView = self.query_one(ListView)
        item = list_view.highlighted_child
        if item:
            # print('>>>', item.file)
            # pipe: /dev/tty, args: <stdin>


            self.log('>>>', sys.__stdin__.name)
            with self.suspend():
                os.system(f"emacs -nw -q {item.file}")
                # os.system(f"nano {item.file}")
            # print(item.__dict__)
            # print(item.file)
            # editor = os.getenv("EDITOR", "nano")
            # subprocess.run(['nano', item.file])
            # self.system(f"less {item.file}")
