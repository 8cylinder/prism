"""Renderer system for different file types."""

from pathlib import Path
from typing import Protocol, Literal
from textual.widgets import Static
from textual.containers import VerticalScroll
from textual._node_list import DuplicateIds
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.style import Style
import html2text
import re

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
    ) -> tuple[Static, int]:
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
    ) -> tuple[Static, int]:
        """Render Markdown file as formatted markdown."""
        # Read file first (may raise OSError/UnicodeDecodeError)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        markdown = Markdown(content)

        # Check if widget already exists, if so just update it
        try:
            code_view = container.query_one("#code", Static)
        except Exception:
            # Widget doesn't exist, create and mount it
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
        except Exception:
            # Widget doesn't exist, create and mount it
            code_view = Static(id="code", expand=True)
            container.mount(code_view)

        code_view.update(markdown)
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
            # Widget doesn't exist, create and mount it
            code_view = Static(id="code", expand=True)
            container.mount(code_view)

        # Find all matches in the file and highlight them
        if match_string:
            escaped_pattern = re.escape(match_string)
            lines = syntax.code.splitlines()

            # First, highlight all non-current matches with a different color
            other_match_style = Style(
                color=other_match_highlight_color,
                bgcolor=other_match_highlight_bgcolor,
            )
            for line_idx, line_text in enumerate(lines, start=1):
                for match in re.finditer(escaped_pattern, line_text):
                    # Skip the first match on the current line (will be highlighted with primary color)
                    if line_idx == line_num:
                        # Only skip if this is the first match on the line
                        # (to highlight the primary match)
                        first_match = re.search(escaped_pattern, line_text)
                        if first_match and match.span() == first_match.span():
                            continue
                    pos = match.span()
                    syntax.stylize_range(
                        other_match_style,
                        (line_idx, pos[0]),
                        (line_idx, pos[1]),
                    )

            # Then highlight the current match with primary color
            if line_num > 0 and line_num <= len(lines):
                line = lines[line_num - 1]
                current_match = re.search(escaped_pattern, line)
                if current_match:
                    pos = current_match.span()
                    highlight = Style(
                        color=match_highlight_color,
                        bgcolor=match_highlight_bgcolor,
                    )
                    syntax.stylize_range(
                        highlight, (line_num, pos[0]), (line_num, pos[1])
                    )

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
    # Future renderers go here:
    # CSVRenderer,
    # TSVRenderer,
    # JSONRenderer,
    SourceCodeRenderer,  # Always last - fallback
]
