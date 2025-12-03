from pathlib import Path
import dataclasses
import re
from typing import Literal
import os
import subprocess
import sys
import shlex

from rich.traceback import Traceback
from rich.text import Text

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.reactive import var
from textual.widgets import Footer, Header, Static, ListItem, ListView

from prism.renderers import RENDERERS

# Constants
FileListState = Literal["narrow", "wide", "hidden"]
ViewMode = Literal["source", "markdown"]
DEFAULT_SYNTAX_THEME = "github-dark"
DEFAULT_TRACEBACK_THEME = "github-dark"
SCROLL_OFFSET_RATIO = 3
MATCH_HIGHLIGHT_COLOR = "bright_white"
MATCH_HIGHLIGHT_BGCOLOR = "orange4"
OTHER_MATCH_HIGHLIGHT_COLOR = "gray66"
OTHER_MATCH_HIGHLIGHT_BGCOLOR = "gray23"
VERTICAL_BAR_COLOR = "#304759"


def snip(string: str, length: int) -> str:
    """Shorten a string to the specified length with ellipsis.

    If the string is longer than length, inserts the unicode ellipsis character
    (…) at 1/3 from the start and truncates from both sides.
    """
    if len(string) <= length:
        return string
    ellipsis = "…"
    chars_to_show = length - len(ellipsis)
    start_chars = chars_to_show // 3
    end_chars = chars_to_show - start_chars
    if start_chars > 0 and end_chars > 0:
        return string[:start_chars] + ellipsis + string[-end_chars:]
    return ellipsis


@dataclasses.dataclass
class FileData:
    file: Path
    line_num: int
    match_string: str
    column: int = 0  # Column position of match (0 if unknown)


class FileListItem(ListItem):
    def __init__(self, file_data: FileData, is_last: bool = False) -> None:
        super().__init__()
        self.data = file_data
        self.is_last = is_last

    def render(self) -> Text:
        """Render the file list item as rich Text."""
        # First line: prefix + filename and line number
        text = Text()

        # Always use full vertical bar for filename
        prefix = "┃ "
        text.append(prefix, style=VERTICAL_BAR_COLOR)

        # Account for prefix and line number suffix when snipping filename
        line_num_str = f":{self.data.line_num}" if self.data.line_num else ""
        available_width = self.size.width - len(prefix) - len(line_num_str)
        filename = snip(self.data.file.name, available_width)
        text.append(filename, style="")
        if self.data.line_num:
            text.append(line_num_str, style="green")

        # Second line: parent directory path (if exists)
        if len(self.data.file.parts) > 1:
            text.append("\n")
            # Use short vertical bar for path on last item, full bar otherwise
            path_prefix = "╹ " if self.is_last else "┃ "
            text.append(path_prefix, style=VERTICAL_BAR_COLOR)
            parent_path = f"{self.data.file.parent}/"
            parent_path = snip(parent_path, self.size.width - len(path_prefix))
            text.append(parent_path, style="dim italic")

        return text


class Prism(App[None]):
    """View files found."""

    CSS_PATH = "css/prism.tcss"
    BINDINGS = [
        Binding("f", "toggle_files", "Toggle Files"),
        Binding("e", "edit_file", "Edit File"),
        Binding("n,j", "next_item", "Next Match", key_display="↓|n|j"),
        Binding("p,k", "prev_item", "Previous Match", key_display="↑|p|k"),
        Binding("right,i", "next_file", "Next File", show=True, key_display="→|i"),
        Binding("left,u", "prev_file", "Previous File", key_display="←|u"),
        Binding("w", "toggle_wrap", "Wrap"),
        Binding("m", "toggle_view_mode", "Render"),
        Binding("q", "quit", "Quit"),
    ]
    ENABLE_COMMAND_PALETTE = False

    file_list_state: var[FileListState] = var("narrow")
    word_wrap: var[bool] = var(False)
    view_mode: var[ViewMode] = var("source")

    def __init__(self, files: list[FileData]) -> None:
        self.files = files
        self._rendering = False  # Flag to prevent re-entrant rendering
        self._code_widget_counter = 0  # Counter for unique widget IDs
        super().__init__()

    def watch_file_list_state(self, new_state: FileListState) -> None:
        """Called when file_list_state is modified."""
        # Remove all state classes
        self.remove_class("-files-narrow", "-files-wide", "-files-hidden")

        # Add the current state class
        self.add_class(f"-files-{new_state}")

    def watch_word_wrap(self, new_wrap: bool) -> None:
        """Called when word_wrap is modified."""
        # Don't trigger during initial render
        if getattr(self, "_rendering", False):
            return

        # Refresh the current view (only if fully initialized)
        try:
            code_view_container = self.query_one("#code-view", VerticalScroll)
            if not code_view_container.is_mounted:
                return
        except Exception:
            return  # Not ready yet

        list_view = self.query_one(ListView)
        if list_view.highlighted_child and isinstance(
            list_view.highlighted_child, FileListItem
        ):
            self.on_list_view_highlighted(
                ListView.Highlighted(list_view, list_view.highlighted_child)
            )

    def watch_view_mode(self, new_mode: ViewMode) -> None:
        """Called when view_mode is modified."""
        # Don't trigger during initial render
        if getattr(self, "_rendering", False):
            return

        # Refresh the current view (only if fully initialized)
        try:
            code_view_container = self.query_one("#code-view", VerticalScroll)
            if not code_view_container.is_mounted:
                return
        except Exception:
            return  # Not ready yet

        list_view = self.query_one(ListView)
        if list_view.highlighted_child and isinstance(
            list_view.highlighted_child, FileListItem
        ):
            self.on_list_view_highlighted(
                ListView.Highlighted(list_view, list_view.highlighted_child)
            )

    def compose(self) -> ComposeResult:
        """Compose our UI."""

        # Count occurrences per file to determine if an item is the last
        from collections import Counter

        file_counts = Counter(file_data.file for file_data in self.files)

        items = []
        current_path = None
        color_class = "even"
        file_occurrence: dict[Path, int] = {}

        for file_data in self.files:
            # Alternate color when the file path changes
            if file_data.file != current_path:
                current_path = file_data.file
                color_class = "odd" if color_class == "even" else "even"
                file_occurrence[file_data.file] = 0

            file_occurrence[file_data.file] += 1
            total_count = file_counts[file_data.file]
            current_count = file_occurrence[file_data.file]

            # Determine if this is the last occurrence of this file
            is_last = current_count == total_count

            item = FileListItem(file_data, is_last)
            item.add_class(color_class)
            items.append(item)

        yield Header(show_clock=False)
        with Container():
            yield ListView(*items, id="file-list")
            yield VerticalScroll(id="code-view")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(ListView).focus()
        self.title = ""

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if not isinstance(event.item, FileListItem):
            return

        # Prevent re-entrant calls during rendering (atomic check-and-set)
        if getattr(self, "_rendering", False):
            return
        self._rendering = True

        try:
            # Clear selection from all items and add to current item
            for item in self.query(FileListItem):
                item.remove_class("selected")
            event.item.add_class("selected")

            data = event.item.data
            event.stop()

            # Get values from reactive variables BEFORE clearing widgets
            # This prevents triggering watchers during widget manipulation
            current_view_mode = self.view_mode
            current_word_wrap = self.word_wrap

            # Get the code-view container
            code_view_container = self.query_one("#code-view", VerticalScroll)

            try:
                # Find the first renderer that can handle this file
                for renderer in RENDERERS:
                    if renderer.can_render(data.file, current_view_mode):
                        # Render the file
                        code_view, scroll_y = renderer.render(
                            container=code_view_container,
                            file_path=data.file,
                            line_num=data.line_num,
                            match_string=data.match_string,
                            word_wrap=current_word_wrap,
                            theme=DEFAULT_SYNTAX_THEME,
                            scroll_offset_ratio=SCROLL_OFFSET_RATIO,
                            match_highlight_color=MATCH_HIGHLIGHT_COLOR,
                            match_highlight_bgcolor=MATCH_HIGHLIGHT_BGCOLOR,
                            other_match_highlight_color=OTHER_MATCH_HIGHLIGHT_COLOR,
                            other_match_highlight_bgcolor=OTHER_MATCH_HIGHLIGHT_BGCOLOR,
                        )

                        # Calculate column position for editor if we have a match
                        if data.match_string and data.line_num > 0:
                            with open(data.file, "r", encoding="utf-8") as f:
                                lines = f.readlines()
                                if data.line_num <= len(lines):
                                    line = lines[data.line_num - 1]
                                    escaped_pattern = re.escape(data.match_string)
                                    match = re.search(escaped_pattern, line)
                                    if match:
                                        # Store column position for editor (emacs uses 1-indexed columns)
                                        data.column = match.span()[0] + 1

                        # Scroll to the appropriate position
                        if scroll_y > 0:
                            code_view_container.scroll_to(y=scroll_y, animate=False)

                        break  # Stop after first matching renderer

            except (OSError, UnicodeDecodeError, IndexError) as e:
                # OSError: file read errors
                # UnicodeDecodeError: binary files or encoding issues
                # IndexError: line_num out of range
                code_view = Static(id="code", expand=True)
                code_view_container.mount(code_view)
                code_view.update(Traceback(theme=DEFAULT_TRACEBACK_THEME, width=None))
                # Store error for title update after _rendering flag is cleared
                self._error_title: str | None = f"ERROR: {type(e).__name__}"
            else:
                self._error_title = None
        finally:
            self._rendering = False
            # Set title after rendering flag is cleared to avoid triggering watchers
            if hasattr(self, "_error_title") and self._error_title:
                self.title = self._error_title
            else:
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

    def action_toggle_view_mode(self) -> None:
        """Toggle between source and markdown view."""
        self.view_mode = "markdown" if self.view_mode == "source" else "source"

    def action_next_item(self) -> None:
        """Move to the next item in the list."""
        list_view = self.query_one(ListView)
        list_view.action_cursor_down()

    def action_prev_item(self) -> None:
        """Move to the previous item in the list."""
        list_view = self.query_one(ListView)
        list_view.action_cursor_up()

    def action_next_file(self) -> None:
        """Move to the next file in the list."""
        list_view = self.query_one(ListView)
        highlighted_item = list_view.highlighted_child
        if not isinstance(highlighted_item, FileListItem):
            return

        current_file = highlighted_item.data.file
        # Find the index of the first item with a different file after current
        current_index = list_view.index
        if current_index is None:
            return
        children = [
            child for child in list_view.children if isinstance(child, FileListItem)
        ]
        for i, child in enumerate(children):
            if i > current_index and child.data.file != current_file:
                list_view.index = i
                return

    def action_prev_file(self) -> None:
        """Move to the previous file in the list."""
        list_view = self.query_one(ListView)
        highlighted_item = list_view.highlighted_child
        if not isinstance(highlighted_item, FileListItem):
            return

        current_file = highlighted_item.data.file
        current_index = list_view.index
        if current_index is None:
            return
        # Find the index of the last item with a different file before current
        children = [
            child for child in list_view.children if isinstance(child, FileListItem)
        ]
        last_different_index = None
        for i, child in enumerate(children):
            if i >= current_index:
                break
            if child.data.file != current_file:
                last_different_index = i
        if last_different_index is not None:
            list_view.index = last_different_index

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
