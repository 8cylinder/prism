from pathlib import Path
import click
import dataclasses
import re
from typing import Literal
import os
import subprocess
import sys
import shlex

from rich.syntax import Syntax
from rich.traceback import Traceback
from rich.style import Style

from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll, Horizontal
from textual.reactive import var
from textual.widgets import Footer, Header, Static, Label, ListItem, ListView

# Constants
FileListState = Literal["narrow", "wide", "hidden"]
DEFAULT_SYNTAX_THEME = "github-dark"
DEFAULT_TRACEBACK_THEME = "github-dark"
SCROLL_OFFSET_RATIO = 3
MATCH_HIGHLIGHT_COLOR = "bright_white"
MATCH_HIGHLIGHT_BGCOLOR = "orange4"


@dataclasses.dataclass
class FileData:
    file: Path
    line_num: int
    match_string: str


class FileListItem(ListItem):
    data: FileData

    def __init__(self, file_item: FileData, classname: str) -> None:
        super().__init__()
        self.file: Path = file_item.file
        self.line_num: int = file_item.line_num
        self.match_string: str = file_item.match_string
        self.classname: str = classname
        self.data = file_item

    def compose(self) -> ComposeResult:
        with Horizontal():
            if len(self.file.parts) > 1:
                yield Label(f"{self.file.parent}/", classes="file-parent")
            yield Label(self.file.name, classes="file-name")
            if self.line_num:
                yield Label(f":{self.line_num}", classes="line-number")


class Prism(App[None]):
    """View files found."""

    CSS_PATH = "css/prism.tcss"
    BINDINGS = [
        ("l", "toggle_light", "Toggle light mode"),
        ("f", "toggle_files", "Toggle Files"),
        ("e", "edit_file", "Edit File"),
        ("q", "quit", "Quit"),
    ]
    ENABLE_COMMAND_PALETTE = False

    file_list_state: var[FileListState] = var("narrow")

    def __init__(self, files: list[FileData]) -> None:
        self.files = files
        super().__init__()

    def watch_file_list_state(self, new_state: FileListState) -> None:
        """Called when file_list_state is modified."""
        # Remove all state classes
        self.remove_class("-files-narrow", "-files-wide", "-files-hidden")

        # Add the current state class
        self.add_class(f"-files-{new_state}")

    def compose(self) -> ComposeResult:
        """Compose our UI."""

        items = []
        for i, ele in enumerate(self.files):
            classname = "odd" if i % 2 else "even"
            item = FileListItem(ele, classname)
            item.add_class(classname)
            items.append(item)

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
        if not isinstance(event.item, FileListItem):
            return

        data = event.item.data
        line_num = data.line_num
        event.stop()
        code_view = self.query_one("#code", Static)
        try:
            syntax = Syntax.from_path(
                str(data.file),
                line_numbers=True,
                word_wrap=True,
                indent_guides=False,
                theme=DEFAULT_SYNTAX_THEME,
                highlight_lines={line_num},
            )
            line = syntax.code.splitlines()[line_num - 1]
            match = re.search(re.escape(data.match_string), line)
            if match:
                pos = match.span()
                highlight = Style(
                    color=MATCH_HIGHLIGHT_COLOR, bgcolor=MATCH_HIGHLIGHT_BGCOLOR
                )
                syntax.stylize_range(highlight, (line_num, pos[0]), (line_num, pos[1]))

        except (OSError, UnicodeDecodeError, IndexError) as e:
            # OSError: file read errors
            # UnicodeDecodeError: binary files or encoding issues
            # IndexError: line_num out of range
            code_view.update(Traceback(theme=DEFAULT_TRACEBACK_THEME, width=None))
            self.title = f"ERROR: {type(e).__name__}"
        else:
            code_view.update(syntax)
            scroll_offset = self.size.height // SCROLL_OFFSET_RATIO
            self.query_one("#code-view").scroll_to(
                y=int(line_num) - scroll_offset,
                animate=False,
            )
            self.title = self.pretty_path(data.file)

    def action_toggle_files(self) -> None:
        """Called in response to key binding. Cycles through narrow -> wide -> hidden."""
        if self.file_list_state == "narrow":
            self.file_list_state = "wide"
        elif self.file_list_state == "wide":
            self.file_list_state = "hidden"
        else:  # hidden
            self.file_list_state = "narrow"

    def action_toggle_light(self) -> None:
        """An action to toggle dark mode."""
        self.theme = (
            "textual-dark" if self.theme == "textual-light" else "textual-light"
        )

    def action_edit_file(self) -> None:
        """Edit the file."""
        list_view: ListView = self.query_one(ListView)
        item = list_view.highlighted_child
        if isinstance(item, FileListItem):
            editor = os.getenv("EDITOR", "nano")
            # Handle editors with arguments (e.g., "emacs -nw")
            editor_parts = shlex.split(editor)

            # Add line number support for emacs
            if "emacs" in editor_parts[0].lower() and item.line_num:
                editor_parts.append(f"+{item.line_num}")

            editor_parts.append(str(item.file))

            with self.suspend():
                # Pass terminal handles explicitly so editor can interact with terminal
                subprocess.run(
                    editor_parts,
                    stdin=sys.__stdin__,
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                )
