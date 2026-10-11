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
from rich.text import Text
from rich.console import (
    Console,
    ConsoleOptions,
    RenderableType,
    RenderResult,
)
import html2text
import re
import csv
import json

ViewMode = Literal["source", "markdown"]


def _make_search_styles(
    match_color: str,
    match_bgcolor: str,
    current_color: str,
    current_bgcolor: str,
) -> tuple[Style, Style]:
    """Build the styles used for search matches and the current match."""
    match_style = Style(color=match_color, bgcolor=match_bgcolor)
    current_style = Style(color=current_color, bgcolor=current_bgcolor, bold=True)
    return match_style, current_style


class SearchHighlighter:
    """Wrap a rich renderable and highlight search matches in its output.

    Rendered documents (markdown, JSON, HTML, org) no longer map one-to-one
    to source lines, so instead of styling source ranges we style the
    rendered text itself. The wrapped renderable is converted to a ``Text``
    so character ranges can be located, then a style is applied on top of
    whatever styling the renderable already produced.
    """

    def __init__(
        self,
        renderable: RenderableType,
        query: str,
        match_style: Style,
        current_style: Style,
        current_index: int = -1,
    ) -> None:
        self._renderable = renderable
        self._query = query
        self._match_style = match_style
        self._current_style = current_style
        self._current_index = current_index
        # Zero-based rendered line of the current match, set during render.
        self.current_match_line: int | None = None

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        text = Text()
        for segment in console.render(self._renderable, options):
            text.append(segment.text, segment.style)

        self.current_match_line = None
        if not self._query:
            yield text
            return

        try:
            pattern = re.compile(re.escape(self._query), re.IGNORECASE)
        except re.error:
            yield text
            return

        plain = text.plain
        for index, match in enumerate(pattern.finditer(plain)):
            if match.start() == match.end():
                continue
            if index == self._current_index:
                style = self._current_style
                self.current_match_line = plain.count("\n", 0, match.start())
            else:
                style = self._match_style
            text.stylize(style, match.start(), match.end())

        yield text


def apply_search_highlight(
    renderable: RenderableType,
    search_query: str,
    search_current_index: int,
    search_match_color: str,
    search_match_bgcolor: str,
    search_current_color: str,
    search_current_bgcolor: str,
) -> RenderableType:
    """Wrap ``renderable`` so search matches are highlighted, if searching."""
    if not search_query:
        return renderable
    match_style, current_style = _make_search_styles(
        search_match_color,
        search_match_bgcolor,
        search_current_color,
        search_current_bgcolor,
    )
    return SearchHighlighter(
        renderable,
        search_query,
        match_style,
        current_style,
        search_current_index,
    )


def _set_highlighter(widget: Static, renderable: RenderableType) -> None:
    """Record the search highlighter on a widget so the app can scroll to it."""
    setattr(
        widget,
        "_search_highlighter",
        renderable if isinstance(renderable, SearchHighlighter) else None,
    )


def _highlight_cell(
    value: str,
    pattern: "re.Pattern[str] | None",
    match_style: Style,
    current_style: Style,
    current_index: int,
    counter: int,
) -> tuple[Text, int]:
    """Highlight search matches inside a single table cell.

    Returns the styled cell and the updated global match counter so the
    "current" match styling can be tracked across cells.
    """
    cell = Text(str(value))
    if pattern is None:
        return cell, counter
    for match in pattern.finditer(cell.plain):
        style = current_style if counter == current_index else match_style
        cell.stylize(style, match.start(), match.end())
        counter += 1
    return cell, counter


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
        search_matches: list[tuple[int, int, int]] | None = None,
        search_current_index: int = -1,
        search_match_color: str = "white",
        search_match_bgcolor: str = "dark_red",
        search_current_color: str = "white",
        search_current_bgcolor: str = "bright_red",
        search_query: str = "",
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
            search_matches: (line_num, start, end) tuples for search matches
            search_current_index: Index of the currently focused search match
            search_match_color: Text color for search matches
            search_match_bgcolor: Background color for search matches
            search_current_color: Text color for the current search match
            search_current_bgcolor: Background color for the current search match
            search_query: Raw search string, used by rendered view modes

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
        search_matches: list[tuple[int, int, int]] | None = None,
        search_current_index: int = -1,
        search_match_color: str = "white",
        search_match_bgcolor: str = "dark_red",
        search_current_color: str = "white",
        search_current_bgcolor: str = "bright_red",
        search_query: str = "",
    ) -> tuple[Static, int]:
        """Render Markdown file as formatted markdown."""
        # Read file first (may raise OSError/UnicodeDecodeError)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        markdown = apply_search_highlight(
            Markdown(content),
            search_query,
            search_current_index,
            search_match_color,
            search_match_bgcolor,
            search_current_color,
            search_current_bgcolor,
        )

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
        _set_highlighter(code_view, markdown)
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
        search_matches: list[tuple[int, int, int]] | None = None,
        search_current_index: int = -1,
        search_match_color: str = "white",
        search_match_bgcolor: str = "dark_red",
        search_current_color: str = "white",
        search_current_bgcolor: str = "bright_red",
        search_query: str = "",
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
        markdown = apply_search_highlight(
            Markdown(markdown_content),
            search_query,
            search_current_index,
            search_match_color,
            search_match_bgcolor,
            search_current_color,
            search_current_bgcolor,
        )

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
        _set_highlighter(code_view, markdown)
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
        search_matches: list[tuple[int, int, int]] | None = None,
        search_current_index: int = -1,
        search_match_color: str = "white",
        search_match_bgcolor: str = "dark_red",
        search_current_color: str = "white",
        search_current_bgcolor: str = "bright_red",
        search_query: str = "",
    ) -> tuple[Static, int]:
        """Render JSON file as formatted, syntax-highlighted JSON."""
        from rich.text import Text

        try:
            # Read and parse JSON file
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Create rich JSON representation
            json_renderable = apply_search_highlight(
                JSON.from_data(data),
                search_query,
                search_current_index,
                search_match_color,
                search_match_bgcolor,
                search_current_color,
                search_current_bgcolor,
            )

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

            _set_highlighter(code_view, json_renderable)
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
        search_matches: list[tuple[int, int, int]] | None = None,
        search_current_index: int = -1,
        search_match_color: str = "white",
        search_match_bgcolor: str = "dark_red",
        search_current_color: str = "white",
        search_current_bgcolor: str = "bright_red",
        search_query: str = "",
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
                match_style, current_style = _make_search_styles(
                    search_match_color,
                    search_match_bgcolor,
                    search_current_color,
                    search_current_bgcolor,
                )
                pattern = (
                    re.compile(re.escape(search_query), re.IGNORECASE)
                    if search_query
                    else None
                )
                match_counter = 0

                # First row is headers
                headers = rows[0]
                header_cells = []
                for value in headers:
                    cell, match_counter = _highlight_cell(
                        value,
                        pattern,
                        match_style,
                        current_style,
                        search_current_index,
                        match_counter,
                    )
                    header_cells.append(cell)
                table.add_columns(*header_cells)

                # Add remaining rows
                for row in rows[1:]:
                    cells = []
                    for value in row:
                        cell, match_counter = _highlight_cell(
                            value,
                            pattern,
                            match_style,
                            current_style,
                            search_current_index,
                            match_counter,
                        )
                        cells.append(cell)
                    table.add_row(*cells)

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


class OrgRenderer:
    """Renderer for Emacs Org files (.org) using Emacs batch export."""

    @staticmethod
    def can_render(file_path: Path, view_mode: ViewMode) -> bool:
        return view_mode == "markdown" and file_path.suffix.lower() == ".org"

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
        search_matches: list[tuple[int, int, int]] | None = None,
        search_current_index: int = -1,
        search_match_color: str = "white",
        search_match_bgcolor: str = "dark_red",
        search_current_color: str = "white",
        search_current_bgcolor: str = "bright_red",
        search_query: str = "",
    ) -> tuple[Static, int]:
        """Render Org file by exporting to Markdown via Emacs."""
        import subprocess
        import shutil
        from rich.text import Text

        abs_path = str(file_path.resolve())

        # Check if emacs is available
        if shutil.which("emacs") is None:
            return SourceCodeRenderer.render(
                container,
                file_path,
                line_num=line_num,
                match_string=match_string,
                word_wrap=word_wrap,
                theme=theme,
                scroll_offset_ratio=scroll_offset_ratio,
                match_highlight_color=match_highlight_color,
                match_highlight_bgcolor=match_highlight_bgcolor,
                other_match_highlight_color=other_match_highlight_color,
                other_match_highlight_bgcolor=other_match_highlight_bgcolor,
                other_matches=other_matches,
                search_query=search_query,
            )
        else:
            # Use Emacs batch mode to export org to markdown string
            elisp = (
                "(progn "
                "(require 'org) "
                "(require 'ox-md) "
                "(with-temp-buffer "
                f'(insert-file-contents "{abs_path}") '
                "(org-mode) "
                "(princ (org-export-string-as (buffer-string) 'md t))))"
            )
            result = subprocess.run(
                ["emacs", "--batch", "--eval", elisp],
                capture_output=True,
                timeout=15,
            )

            if result.returncode != 0:
                # Emacs export failed - show error
                try:
                    error_view = container.query_one("#code", Static)
                except Exception:
                    for widget in list(container.children):
                        widget.remove()
                    error_view = Static(id="code", expand=True)
                    container.mount(error_view)

                message = Text()
                message.append("\n\n")
                message.append("  Org export failed  \n", style="bold red")
                message.append("\n")
                message.append(f"  {file_path.name}", style="dim")
                message.append(" could not be exported via Emacs.\n", style="dim")
                stderr = result.stderr.decode("utf-8", errors="replace").strip()
                if stderr:
                    message.append(f"\n  {stderr}\n", style="italic dim")
                error_view.update(message)
                return error_view, 0

            content = result.stdout.decode("utf-8")

            # Strip anchor tags that Emacs adds before headings
            content = re.sub(r'<a id="[^"]*"></a>\n*', "", content)

            # Emacs exports org tables as HTML — convert them to markdown tables
            def _html_table_to_markdown(match: re.Match[str]) -> str:
                h = html2text.HTML2Text()
                h.body_width = 0
                return h.handle(match.group(0)).strip()

            content = re.sub(
                r"<table[^>]*>.*?</table>",
                _html_table_to_markdown,
                content,
                flags=re.DOTALL,
            )

            markdown = apply_search_highlight(
                Markdown(content),
                search_query,
                search_current_index,
                search_match_color,
                search_match_bgcolor,
                search_current_color,
                search_current_bgcolor,
            )

        # Display the rendered markdown
        try:
            code_view = container.query_one("#code", Static)
            code_view.update(markdown)
        except Exception:
            for widget in list(container.children):
                widget.remove()
            code_view = Static(id="code", expand=True)
            container.mount(code_view)
            code_view.update(markdown)
        _set_highlighter(code_view, markdown)
        return code_view, 0


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
        search_matches: list[tuple[int, int, int]] | None = None,
        search_current_index: int = -1,
        search_match_color: str = "white",
        search_match_bgcolor: str = "dark_red",
        search_current_color: str = "white",
        search_current_bgcolor: str = "bright_red",
        search_query: str = "",
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

        # Highlight all search matches, emphasizing the current one
        if search_matches:
            for index, (match_line, start, end) in enumerate(search_matches):
                if not (0 < match_line <= len(lines)):
                    continue
                if index == search_current_index:
                    search_style = Style(
                        color=search_current_color,
                        bgcolor=search_current_bgcolor,
                        bold=True,
                    )
                else:
                    search_style = Style(
                        color=search_match_color,
                        bgcolor=search_match_bgcolor,
                    )
                syntax.stylize_range(
                    search_style, (match_line, start), (match_line, end)
                )

        code_view.update(syntax)
        _set_highlighter(code_view, syntax)

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
    OrgRenderer,  # Emacs Org files
    SourceCodeRenderer,  # Always last - fallback
]
