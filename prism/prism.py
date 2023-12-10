import sys
import os

from rich.syntax import Syntax
from rich.traceback import Traceback

from textual.scroll_view import ScrollView
from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll, Horizontal
from textual.reactive import var
# from textual.widgets import DirectoryTree, Footer, Header, Static
from textual.widgets import Footer, Header, Static, Label, ListItem, ListView
from pathlib import Path


class FileListItem(ListItem):
    def __init__(self, file_item: list, classname: str) -> None:
        super().__init__()
        self.file = file_item[0]
        self.line_num = int(file_item[1])
        self.classname = classname

    def compose(self) -> ComposeResult:
        # see https://textual.textualize.io/guide/widgets/#segment-and-style
        yield Label(f'{self.file.name}:{self.line_num}', classes='fname')
        yield Label(f'{self.file.parent}/', classes='path')


class CodeView(ScrollView):
    def __init__(self) -> None:
        ...


class Prism(App):
    """View files found."""

    CSS_PATH = "css/prism.tcss"
    BINDINGS = [
        ("f", "toggle_files", "Toggle Files"),
        ("q", "quit", "Quit"),
    ]

    show_files = var(True)
    # show_files = var(False)

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
                # FileListItem()
            )

        yield Header()
        with Container():
            yield ListView(*items, id='file-list')
            with VerticalScroll(id="code-view"):
                yield Static(id="code", expand=True)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(ListView).focus()

    def on_list_view_highlighted(
            self, event: ListView.Highlighted) -> None:
        line_num = {event.item.line_num}
        event.stop()
        code_view = self.query_one("#code", Static)
        try:
            syntax = Syntax.from_path(
                str(event.item.file),
                line_numbers=True,
                word_wrap=False,
                indent_guides=True,
                theme="github-dark",
                highlight_lines=line_num,
            )
        except Exception:
            code_view.update(Traceback(theme="github-dark", width=None))
            self.sub_title = "ERROR"
        else:
            code_view.update(syntax)
            # self.query_one("#code-view").scroll_home(animate=False)
            self.query_one("#code-view").scroll_to(
                y=int(event.item.line_num) - 10,
                animate=False,
            )
            self.sub_title = str(event.item.file)

    def action_toggle_files(self) -> None:
        """Called in response to key binding."""
        self.show_files = not self.show_files
        self.log(self.show_files)
