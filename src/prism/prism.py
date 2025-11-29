from pathlib import Path
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
from rich.text import Text

from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.reactive import var
from textual.widgets import Footer, Header, Static, ListItem, ListView

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
    column: int = 0  # Column position of match (0 if unknown)


class FileListItem(ListItem):
    def __init__(self, file_data: FileData) -> None:
        super().__init__()
        self.data = file_data

    def render(self) -> Text:
        """Render the file list item as rich Text."""
        # First line: filename and line number
        text = Text()
        text.append(self.data.file.name, style="bold")
        if self.data.line_num:
            text.append(f":{self.data.line_num}", style="green")

        # Second line: parent directory path (if exists)
        if len(self.data.file.parts) > 1:
            text.append("\n")
            parent_path = f"{self.data.file.parent}/"
            # Truncate path with middle ellipsis if needed
            available_width = self.size.width
            if len(parent_path) > available_width:
                # Calculate how much to show from start and end
                ellipsis = "…"
                chars_to_show = available_width - len(ellipsis)
                start_chars = chars_to_show // 2
                end_chars = chars_to_show - start_chars
                if start_chars > 0 and end_chars > 0:
                    parent_path = (
                        parent_path[:start_chars] + ellipsis + parent_path[-end_chars:]
                    )
                else:
                    parent_path = ellipsis
            text.append(parent_path, style="dim italic")

        return text


class Prism(App[None]):
    """View files found."""

    CSS_PATH = "css/prism.tcss"
    BINDINGS = [
        ("f", "toggle_files", "Toggle Files"),
        ("e", "edit_file", "Edit File"),
        ("n", "next_item", "Next"),
        ("j", "next_item", "Next"),
        ("p", "prev_item", "Previous"),
        ("k", "prev_item", "Previous"),
        ("w", "toggle_wrap", "Toggle Wrap"),
        ("q", "quit", "Quit"),
    ]
    ENABLE_COMMAND_PALETTE = False

    file_list_state: var[FileListState] = var("narrow")
    word_wrap: var[bool] = var(True)

    def __init__(self, files: list[FileData]) -> None:
        self.files = files
        super().__init__()

    def watch_file_list_state(self, new_state: FileListState) -> None:
        """Called when file_list_state is modified."""
        # Remove all state classes
        self.remove_class("-files-narrow", "-files-wide", "-files-hidden")

        # Add the current state class
        self.add_class(f"-files-{new_state}")

    def watch_word_wrap(self, new_wrap: bool) -> None:
        """Called when word_wrap is modified."""
        # Refresh the current view
        list_view = self.query_one(ListView)
        if list_view.highlighted_child and isinstance(
            list_view.highlighted_child, FileListItem
        ):
            self.on_list_view_highlighted(
                ListView.Highlighted(list_view, list_view.highlighted_child)
            )

    def compose(self) -> ComposeResult:
        """Compose our UI."""

        items = []
        for i, file_data in enumerate(self.files):
            item = FileListItem(file_data)
            item.add_class("odd" if i % 2 else "even")
            items.append(item)

        yield Header(show_clock=False)
        with Container():
            yield ListView(*items, id="file-list")
            with VerticalScroll(id="code-view"):
                yield Static(id="code", expand=True)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(ListView).focus()
        self.title = ""

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if not isinstance(event.item, FileListItem):
            return

        # Clear selection from all items and add to current item
        for item in self.query(FileListItem):
            item.remove_class("selected")
        event.item.add_class("selected")

        data = event.item.data
        line_num = data.line_num
        event.stop()
        code_view = self.query_one("#code", Static)
        try:
            syntax = Syntax.from_path(
                str(data.file),
                line_numbers=True,
                word_wrap=self.word_wrap,
                indent_guides=False,
                theme=DEFAULT_SYNTAX_THEME,
                highlight_lines={line_num},
            )
            line = syntax.code.splitlines()[line_num - 1]
            match = re.search(re.escape(data.match_string), line)
            if match:
                pos = match.span()
                # Store column position for editor (emacs uses 1-indexed columns)
                data.column = pos[0] + 1
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
            self.title = str(data.file)

    def action_toggle_files(self) -> None:
        """Called in response to key binding. Cycles through narrow -> wide -> hidden."""
        if self.file_list_state == "narrow":
            self.file_list_state = "wide"
        elif self.file_list_state == "wide":
            self.file_list_state = "hidden"
        else:  # hidden
            self.file_list_state = "narrow"

    def action_toggle_wrap(self) -> None:
        """Toggle word wrap in the code viewer."""
        self.word_wrap = not self.word_wrap

    def action_next_item(self) -> None:
        """Move to the next item in the list."""
        list_view = self.query_one(ListView)
        list_view.action_cursor_down()

    def action_prev_item(self) -> None:
        """Move to the previous item in the list."""
        list_view = self.query_one(ListView)
        list_view.action_cursor_up()

    def action_edit_file(self) -> None:
        """Edit the file."""
        list_view: ListView = self.query_one(ListView)
        item = list_view.highlighted_child
        if isinstance(item, FileListItem):
            editor = os.getenv("EDITOR", "nano")
            # Handle editors with arguments (e.g., "emacs -nw")
            editor_parts = shlex.split(editor)

            # Add line number and column support for emacs
            if "emacs" in editor_parts[0].lower() and item.data.line_num:
                if item.data.column:
                    # Jump to specific line and column: +linenum:column
                    editor_parts.append(f"+{item.data.line_num}:{item.data.column}")
                else:
                    # Jump to line only: +linenum
                    editor_parts.append(f"+{item.data.line_num}")

            editor_parts.append(str(item.data.file))

            with self.suspend():
                # Pass terminal handles explicitly so editor can interact with terminal
                subprocess.run(
                    editor_parts,
                    stdin=sys.__stdin__,
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                )
