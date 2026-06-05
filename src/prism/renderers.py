"""Renderer system for different file types."""

from pathlib import Path
from typing import Protocol, Literal
from textual.widget import Widget
from textual.widgets import Static, DataTable
from textual.containers import VerticalScroll
from textual._node_list import DuplicateIds
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.style import Style
from rich.json import JSON
import html2text
import re
import csv
import json

ViewMode = Literal["source", "markdown"]


class Renderer(Protocol):
    """Protocol for file renderers."""

    @staticmethod
    def can_render(file_path: Path, view_mode: ViewMode) -> bool:
        """Return True if this renderer can handle the file.

        Args:
            file_path: Path to the file to render
            view_mode: Current view mode ("source" or "markdown")

        Returns:
            True if this renderer should handle the file
        """
        ...

    @staticmethod
    def render(
        container: VerticalScroll,
        file_path: Path,
        line_num: int = 0,
        match_string: str = "",
        word_wrap: bool = False,
        theme: str = "github-dark",
        scroll_offset_ratio: int = 3,
        match_highlight_color: str = "bright_white",
        match_highlight_bgcolor: str = "orange4",
        other_match_highlight_color: str = "gray66",
        other_match_highlight_bgcolor: str = "gray23",
        other_matches: list[tuple[int, str]] | None = None,
    ) -> tuple[Widget, int]:
        """Render the file to the container.

        Args:
            container: VerticalScroll container to render into
            file_path: Path to the file to render
            line_num: Line number to highlight (0 if none)
            match_string: Text to highlight within lines
            word_wrap: Whether to wrap long lines
            theme: Syntax highlighting theme
            scroll_offset_ratio: Scroll position ratio for highlighted line
            match_highlight_color: Color for current match
            match_highlight_bgcolor: Background color for current match
            other_match_highlight_color: Color for other matches
            other_match_highlight_bgcolor: Background color for other matches
            other_matches: (line_num, match_string) pairs for other entries pointing to this file

        Returns:
            Tuple of (widget created, scroll position)
        """
        ...


class MarkdownRenderer:
    """Renderer for Markdown files (.md, .markdown)."""

    @staticmethod
    def can_render(file_path: Path, view_mode: ViewMode) -> bool:
        return view_mode == "markdown" and file_path.suffix.lower() in {
            ".md",
            ".markdown",
        }

    @staticmethod
    def render(
        container: VerticalScroll,
        file_path: Path,
        line_num: int = 0,
        match_string: str = "",
        word_wrap: bool = False,
        theme: str = "github-dark",
        scroll_offset_ratio: int = 3,
        match_highlight_color: str = "bright_white",
        match_highlight_bgcolor: str = "orange4",
        other_match_highlight_color: str = "gray66",
        other_match_highlight_bgcolor: str = "gray23",
        other_matches: list[tuple[int, str]] | None = None,
    ) -> tuple[Static, int]:
        """Render Markdown file as formatted markdown."""
        # Read file first (may raise OSError/UnicodeDecodeError)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        markdown = Markdown(content)

        # Check if widget already exists, if so just update it
        try:
            code_view = container.query_one("#code", Static)
            code_view.update(markdown)
        except Exception:
            # Widget doesn't exist or is wrong type - clear and create new one
            for widget in list(container.children):
                widget.remove()
            code_view = Static(id="code", expand=True)
            container.mount(code_view)
            code_view.update(markdown)
        return code_view, 0


class HTMLRenderer:
    """Renderer for HTML files (.html, .htm, .twig)."""

    @staticmethod
    def can_render(file_path: Path, view_mode: ViewMode) -> bool:
        return view_mode == "markdown" and file_path.suffix.lower() in {
            ".html",
            ".htm",
            ".twig",
        }

    @staticmethod
    def render(
        container: VerticalScroll,
        file_path: Path,
        line_num: int = 0,
        match_string: str = "",
        word_wrap: bool = False,
        theme: str = "github-dark",
        scroll_offset_ratio: int = 3,
        match_highlight_color: str = "bright_white",
        match_highlight_bgcolor: str = "orange4",
        other_match_highlight_color: str = "gray66",
        other_match_highlight_bgcolor: str = "gray23",
        other_matches: list[tuple[int, str]] | None = None,
    ) -> tuple[Static, int]:
        """Render HTML file by converting to Markdown."""
        # Read file first (may raise OSError/UnicodeDecodeError)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Convert HTML to Markdown
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        markdown_content = h.handle(content)
        markdown = Markdown(markdown_content)

        # Check if widget already exists, if so just update it
        try:
            code_view = container.query_one("#code", Static)
            code_view.update(markdown)
        except Exception:
            # Widget doesn't exist or is wrong type - clear and create new one
            for widget in list(container.children):
                widget.remove()
            code_view = Static(id="code", expand=True)
            container.mount(code_view)
            code_view.update(markdown)
        return code_view, 0


class JSONRenderer:
    """Renderer for JSON files (.json)."""

    @staticmethod
    def can_render(file_path: Path, view_mode: ViewMode) -> bool:
        return view_mode == "markdown" and file_path.suffix.lower() == ".json"

    @staticmethod
    def render(
        container: VerticalScroll,
        file_path: Path,
        line_num: int = 0,
        match_string: str = "",
        word_wrap: bool = False,
        theme: str = "github-dark",
        scroll_offset_ratio: int = 3,
        match_highlight_color: str = "bright_white",
        match_highlight_bgcolor: str = "orange4",
        other_match_highlight_color: str = "gray66",
        other_match_highlight_bgcolor: str = "gray23",
        other_matches: list[tuple[int, str]] | None = None,
    ) -> tuple[Static, int]:
        """Render JSON file as formatted, syntax-highlighted JSON."""
        from rich.text import Text

        try:
            # Read and parse JSON file
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Create rich JSON representation
            json_renderable = JSON.from_data(data)

            # Check if widget already exists, if so just update it
            try:
                code_view = container.query_one("#code", Static)
                code_view.update(json_renderable)
            except Exception:
                # Widget doesn't exist or is wrong type - clear and create new one
                for widget in list(container.children):
                    widget.remove()
                code_view = Static(id="code", expand=True)
                container.mount(code_view)
                code_view.update(json_renderable)

            return code_view, 0

        except json.JSONDecodeError as e:
            # JSON parsing error - show user-friendly message
            # Try to reuse existing Static widget with id='code' or create new one
            try:
                error_view = container.query_one("#code", Static)
            except Exception:
                # No Static widget exists - clean up and create new one
                for widget in list(container.children):
                    widget.remove()
                error_view = Static(id="code", expand=True)
                container.mount(error_view)

            message = Text()
            message.append("\n\n")
            message.append("  Invalid JSON file  \n", style="bold red")
            message.append("\n")
            message.append(f"  {file_path.name}", style="dim")
            message.append(" cannot be parsed as JSON.\n", style="dim")
            message.append(
                f"\n  Error at line {e.lineno}, column {e.colno}:\n", style="italic dim"
            )
            message.append(f"  {e.msg}\n", style="italic dim")
            error_view.update(message)

            return error_view, 0


class TableRenderer:
    """Renderer for CSV and TSV files (.csv, .tsv)."""

    @staticmethod
    def can_render(file_path: Path, view_mode: ViewMode) -> bool:
        return view_mode == "markdown" and file_path.suffix.lower() in {".csv", ".tsv"}

    @staticmethod
    def render(
        container: VerticalScroll,
        file_path: Path,
        line_num: int = 0,
        match_string: str = "",
        word_wrap: bool = False,
        theme: str = "github-dark",
        scroll_offset_ratio: int = 3,
        match_highlight_color: str = "bright_white",
        match_highlight_bgcolor: str = "orange4",
        other_match_highlight_color: str = "gray66",
        other_match_highlight_bgcolor: str = "gray23",
        other_matches: list[tuple[int, str]] | None = None,
    ) -> tuple[DataTable | Static, int]:
        """Render CSV/TSV file as a DataTable."""
        from rich.text import Text

        # Determine delimiter based on file extension
        delimiter = "\t" if file_path.suffix.lower() == ".tsv" else ","
        file_type = "TSV" if file_path.suffix.lower() == ".tsv" else "CSV"

        try:
            # Read file with appropriate delimiter, filtering out comment lines
            with open(file_path, "r", encoding="utf-8") as f:
                # Filter out lines starting with '#' (comments)
                lines = [line for line in f if not line.strip().startswith("#")]
                reader = csv.reader(lines, delimiter=delimiter)
                rows = list(reader)

            # Check if we can reuse existing DataTable, otherwise clear and create new
            try:
                table = container.query_one(DataTable)
                table.clear()
            except Exception:
                # Widget doesn't exist or container has wrong type - clear and create new
                for widget in list(container.children):
                    widget.remove()
                table = DataTable(zebra_stripes=True)
                container.mount(table)

            if rows:
                # First row is headers
                headers = rows[0]
                table.add_columns(*headers)

                # Add remaining rows
                for row in rows[1:]:
                    table.add_row(*row)

            return table, 0

        except (ValueError, csv.Error) as e:
            # CSV parsing error - show user-friendly message
            # Try to reuse existing Static widget with id='code' or create new one
            try:
                error_view = container.query_one("#code", Static)
            except Exception:
                # No Static widget exists - clean up and create new one
                for widget in list(container.children):
                    widget.remove()
                error_view = Static(id="code", expand=True)
                container.mount(error_view)

            message = Text()
            message.append("\n\n")
            message.append(f"  Invalid {file_type} file  \n", style="bold red")
            message.append("\n")
            message.append(f"  {file_path.name}", style="dim")
            message.append(
                f" cannot be displayed as a {file_type} table.\n", style="dim"
            )
            message.append(f"\n  Error: {str(e)}\n", style="italic dim")
            error_view.update(message)

            return error_view, 0


class SourceCodeRenderer:
    """Fallback renderer for source code files with syntax highlighting."""

    @staticmethod
    def can_render(file_path: Path, view_mode: ViewMode) -> bool:
        # Always returns True - this is the fallback renderer
        return True

    @staticmethod
    def render(
        container: VerticalScroll,
        file_path: Path,
        line_num: int = 0,
        match_string: str = "",
        word_wrap: bool = False,
        theme: str = "github-dark",
        scroll_offset_ratio: int = 3,
        match_highlight_color: str = "bright_white",
        match_highlight_bgcolor: str = "orange4",
        other_match_highlight_color: str = "gray66",
        other_match_highlight_bgcolor: str = "gray23",
        other_matches: list[tuple[int, str]] | None = None,
    ) -> tuple[Static, int]:
        """Render source code with syntax highlighting."""
        # Try to read the file first to detect binary files early
        # This will raise UnicodeDecodeError for binary files
        with open(file_path, "r", encoding="utf-8") as f:
            _ = f.read(1)  # Read just one character to trigger encoding check

        # Render as source code (this may raise FileNotFoundError)
        syntax = Syntax.from_path(
            str(file_path),
            line_numbers=True,
            word_wrap=word_wrap,
            indent_guides=False,
            theme=theme,
            highlight_lines={line_num},
        )

        # Check if widget already exists, if so just update it
        try:
            code_view = container.query_one("#code", Static)
        except Exception:
            # Widget doesn't exist or is wrong type - clear and create new one
            for widget in list(container.children):
                widget.remove()
            code_view = Static(id="code", expand=True)
            container.mount(code_view)

        lines = syntax.code.splitlines()

        # Highlight other file list entries with the same style as the active match
        if other_matches:
            other_style = Style(bgcolor=other_match_highlight_bgcolor)
            for other_line, other_match_str in other_matches:
                if 0 < other_line <= len(lines):
                    line_text = lines[other_line - 1]
                    if other_match_str:
                        m = re.search(re.escape(other_match_str), line_text)
                        if m:
                            pos = m.span()
                            syntax.stylize_range(
                                other_style, (other_line, pos[0]), (other_line, pos[1])
                            )
                            continue
                    # Fallback: no match string or not found — highlight whole line
                    syntax.stylize_range(
                        other_style, (other_line, 0), (other_line, len(line_text))
                    )

        # Highlight the match text on the current line with primary color
        if match_string and line_num > 0 and line_num <= len(lines):
            escaped_pattern = re.escape(match_string)
            line = lines[line_num - 1]
            current_match = re.search(escaped_pattern, line)
            if current_match:
                pos = current_match.span()
                highlight = Style(
                    color=match_highlight_color,
                    bgcolor=match_highlight_bgcolor,
                )
                syntax.stylize_range(highlight, (line_num, pos[0]), (line_num, pos[1]))

        code_view.update(syntax)

        # Calculate scroll position
        from textual.app import App

        app = container.app
        scroll_offset = app.size.height // scroll_offset_ratio
        scroll_y = int(line_num) - scroll_offset

        return code_view, scroll_y


# Renderer registry - order matters! First matching renderer wins.
# Put more specific renderers first, fallback renderer (SourceCodeRenderer) last.
RENDERERS: list[type[Renderer]] = [
    MarkdownRenderer,
    HTMLRenderer,
    JSONRenderer,  # JSON files
    TableRenderer,  # CSV and TSV files
    # Future renderers go here:
    SourceCodeRenderer,  # Always last - fallback
]
