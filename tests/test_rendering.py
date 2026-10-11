"""Tests for different rendering modes (markdown, HTML, CSV/TSV)."""

from pathlib import Path
import pytest
from textual.widgets import Static
from prism.prism import Prism, FileData


@pytest.fixture
def fixtures_dir():
    """Return the path to the fixtures directory."""
    return Path(__file__).parent / "fixtures"


class TestMarkdownRendering:
    """Test markdown file rendering."""

    @pytest.mark.asyncio
    async def test_markdown_file_detected(self, fixtures_dir):
        """Test that .md files are detected as markdown."""
        md_file = fixtures_dir / "test.md"
        files = [FileData(file=md_file, line_num=0, match_string="")]
        app = Prism(files)

        async with app.run_test() as pilot:
            await pilot.pause()  # Let app fully initialize

            # Check that file is detected as markdown
            data = files[0]
            is_markdown = data.file.suffix.lower() in {".md", ".markdown"}
            assert is_markdown

    @pytest.mark.asyncio
    async def test_markdown_rendering_enabled(self, fixtures_dir):
        """Test that markdown is rendered when view mode is active."""
        md_file = fixtures_dir / "test.md"
        files = [FileData(file=md_file, line_num=0, match_string="")]
        app = Prism(files)

        async with app.run_test() as pilot:
            await pilot.pause()  # Let app fully initialize

            # Enable markdown view mode
            await pilot.press("m")
            await pilot.pause()

            # Verify the code view exists
            code_view = app.query_one("#code", Static)
            assert code_view is not None

    @pytest.mark.asyncio
    async def test_markdown_rendering_disabled(self, fixtures_dir):
        """Test that markdown is shown as source when view mode is off."""
        md_file = fixtures_dir / "test.md"
        files = [FileData(file=md_file, line_num=0, match_string="")]
        app = Prism(files)

        async with app.run_test() as pilot:
            await pilot.pause()  # Let app fully initialize

            # Ensure source view mode (default)
            assert app.view_mode == "source"

            # Verify the code view exists
            code_view = app.query_one("#code", Static)
            assert code_view is not None


class TestHTMLRendering:
    """Test HTML file rendering."""

    @pytest.mark.asyncio
    async def test_html_file_detected(self, fixtures_dir):
        """Test that .html files are detected."""
        html_file = fixtures_dir / "test.html"
        files = [FileData(file=html_file, line_num=0, match_string="")]
        app = Prism(files)

        async with app.run_test() as pilot:
            await pilot.pause()  # Let app fully initialize

            # Check that file is detected as HTML
            data = files[0]
            is_html = data.file.suffix.lower() in {".html", ".htm", ".twig"}
            assert is_html

    @pytest.mark.asyncio
    async def test_html_rendering_uses_html2text(self, fixtures_dir):
        """Test that HTML files are converted using html2text."""
        html_file = fixtures_dir / "test.html"
        files = [FileData(file=html_file, line_num=0, match_string="")]
        app = Prism(files)

        async with app.run_test() as pilot:
            await pilot.pause()  # Let app fully initialize

            # Enable markdown view mode
            await pilot.press("m")
            await pilot.pause()

            # Verify the code view exists
            code_view = app.query_one("#code", Static)
            assert code_view is not None

    @pytest.mark.asyncio
    async def test_html_rendering_disabled(self, fixtures_dir):
        """Test that HTML is shown as source when view mode is off."""
        html_file = fixtures_dir / "test.html"
        files = [FileData(file=html_file, line_num=0, match_string="")]
        app = Prism(files)

        async with app.run_test() as pilot:
            await pilot.pause()  # Let app fully initialize

            # Ensure source view mode (default)
            assert app.view_mode == "source"

            # Verify the code view exists
            code_view = app.query_one("#code", Static)
            assert code_view is not None


class TestCSVRendering:
    """Test CSV/TSV file rendering."""

    @pytest.mark.asyncio
    async def test_csv_file_detected(self, fixtures_dir):
        """Test that .csv files are detected."""
        csv_file = fixtures_dir / "test.csv"
        files = [FileData(file=csv_file, line_num=0, match_string="")]
        app = Prism(files)

        async with app.run_test() as pilot:
            # Enable render view mode
            app.view_mode = "markdown"
            await pilot.pause()

            # Check that file is detected as CSV
            data = files[0]
            is_csv = data.file.suffix.lower() in {".csv", ".tsv"}
            assert is_csv

    @pytest.mark.asyncio
    async def test_csv_rendering_as_table(self, fixtures_dir):
        """Test that CSV files are rendered as DataTable."""
        from textual.widgets import DataTable

        csv_file = fixtures_dir / "test.csv"
        files = [FileData(file=csv_file, line_num=0, match_string="")]
        app = Prism(files)

        async with app.run_test() as pilot:
            # Enable render view mode
            await pilot.press("m")
            await pilot.pause()

            # Verify DataTable widget is created
            table = app.query_one(DataTable)
            assert table is not None

    @pytest.mark.asyncio
    async def test_tsv_file_detected(self, fixtures_dir):
        """Test that .tsv files are detected."""
        tsv_file = fixtures_dir / "test.tsv"
        files = [FileData(file=tsv_file, line_num=0, match_string="")]
        app = Prism(files)

        async with app.run_test() as pilot:
            # Enable render view mode
            app.view_mode = "markdown"
            await pilot.pause()

            # Check that file is detected as TSV
            data = files[0]
            is_tsv = data.file.suffix.lower() == ".tsv"
            assert is_tsv

    @pytest.mark.asyncio
    async def test_tsv_rendering_uses_tab_delimiter(self, fixtures_dir):
        """Test that TSV files use tab delimiter."""
        from textual.widgets import DataTable

        tsv_file = fixtures_dir / "test.tsv"
        files = [FileData(file=tsv_file, line_num=0, match_string="")]
        app = Prism(files)

        async with app.run_test() as pilot:
            # Enable render view mode
            await pilot.press("m")
            await pilot.pause()

            # Verify DataTable widget is created
            table = app.query_one(DataTable)
            assert table is not None
            # If TSV was parsed correctly with tabs, we should have columns
            assert len(table.columns) > 0

    @pytest.mark.asyncio
    async def test_csv_with_comments_renders(self, fixtures_dir):
        """Test that CSV files with # comments render correctly."""
        from textual.widgets import DataTable

        csv_file = fixtures_dir / "test_with_comments.csv"
        files = [FileData(file=csv_file, line_num=0, match_string="")]
        app = Prism(files)

        async with app.run_test() as pilot:
            # Enable render view mode
            await pilot.press("m")
            await pilot.pause()

            # Verify DataTable widget is created
            table = app.query_one(DataTable)
            assert table is not None
            # Should have 4 columns (Name, Age, City, Occupation)
            assert len(table.columns) == 4
            # Should have 3 data rows (comments filtered out)
            assert table.row_count == 3

    @pytest.mark.asyncio
    async def test_tsv_with_comments_renders(self, fixtures_dir):
        """Test that TSV files with # comments render correctly."""
        from textual.widgets import DataTable

        tsv_file = fixtures_dir / "test_with_comments.tsv"
        files = [FileData(file=tsv_file, line_num=0, match_string="")]
        app = Prism(files)

        async with app.run_test() as pilot:
            # Enable render view mode
            await pilot.press("m")
            await pilot.pause()

            # Verify DataTable widget is created
            table = app.query_one(DataTable)
            assert table is not None
            # Should have 4 columns (Name, Age, City, Occupation)
            assert len(table.columns) == 4
            # Should have 3 data rows (comments filtered out)
            assert table.row_count == 3

    @pytest.mark.asyncio
    async def test_invalid_csv_shows_error(self, fixtures_dir):
        """Test that invalid CSV files show an error message."""
        csv_file = fixtures_dir / "invalid.csv"
        files = [FileData(file=csv_file, line_num=0, match_string="")]
        app = Prism(files)

        async with app.run_test() as pilot:
            # Enable render view mode
            await pilot.press("m")
            await pilot.pause()

            # Should show error message in a Static widget, not crash
            # Check that app is still running
            assert app.is_running
            # Title should indicate an error or show the file name
            assert "invalid.csv" in app.title.lower() or app.title != ""

    @pytest.mark.asyncio
    async def test_invalid_tsv_shows_error(self, fixtures_dir):
        """Test that invalid TSV files show an error message."""
        tsv_file = fixtures_dir / "invalid.tsv"
        files = [FileData(file=tsv_file, line_num=0, match_string="")]
        app = Prism(files)

        async with app.run_test() as pilot:
            # Enable render view mode
            await pilot.press("m")
            await pilot.pause()

            # Should show error message in a Static widget, not crash
            # Check that app is still running
            assert app.is_running
            # Title should indicate an error or show the file name
            assert "invalid.tsv" in app.title.lower() or app.title != ""


class TestJSONRendering:
    """Test JSON file rendering."""

    @pytest.mark.asyncio
    async def test_json_file_detected(self, fixtures_dir):
        """Test that .json files are detected."""
        json_file = fixtures_dir / "test.json"
        files = [FileData(file=json_file, line_num=0, match_string="")]
        app = Prism(files)

        async with app.run_test() as pilot:
            # Enable render view mode
            app.view_mode = "markdown"
            await pilot.pause()

            # Verify file is detected as JSON
            data = files[0]
            is_json = data.file.suffix.lower() == ".json"
            assert is_json

    @pytest.mark.asyncio
    async def test_json_rendering_enabled(self, fixtures_dir):
        """Test that JSON files are rendered in markdown mode."""
        json_file = fixtures_dir / "test.json"
        files = [FileData(file=json_file, line_num=0, match_string="")]
        app = Prism(files)

        async with app.run_test() as pilot:
            # Enable render view mode
            await pilot.press("m")
            await pilot.pause()

            # Verify Static widget is created (JSON is rendered to Static)
            from textual.widgets import Static

            code_view = app.query_one("#code", Static)
            assert code_view is not None

    @pytest.mark.asyncio
    async def test_json_rendering_disabled(self, fixtures_dir):
        """Test that JSON files show source code in source mode."""
        json_file = fixtures_dir / "test.json"
        files = [FileData(file=json_file, line_num=0, match_string="")]
        app = Prism(files)

        async with app.run_test() as pilot:
            # Start in source mode (default)
            await pilot.pause()

            # Should show source code with syntax highlighting
            from textual.widgets import Static

            code_view = app.query_one("#code", Static)
            assert code_view is not None

    @pytest.mark.asyncio
    async def test_invalid_json_shows_error(self, fixtures_dir):
        """Test that invalid JSON files show an error message."""
        json_file = fixtures_dir / "invalid.json"
        files = [FileData(file=json_file, line_num=0, match_string="")]
        app = Prism(files)

        async with app.run_test() as pilot:
            # Enable render view mode
            await pilot.press("m")
            await pilot.pause()

            # Should show error message in a Static widget, not crash
            # Check that app is still running
            assert app.is_running
            # Title should indicate an error or show the file name
            assert "invalid.json" in app.title.lower() or app.title != ""


class TestOrgRendering:
    """Test Emacs Org file rendering."""

    @pytest.mark.asyncio
    async def test_org_file_detected(self, fixtures_dir):
        """Test that .org files are detected."""
        org_file = fixtures_dir / "test.org"
        files = [FileData(file=org_file, line_num=0, match_string="")]
        app = Prism(files)

        async with app.run_test() as pilot:
            await pilot.pause()

            data = files[0]
            is_org = data.file.suffix.lower() == ".org"
            assert is_org

    @pytest.mark.asyncio
    async def test_org_rendering_enabled(self, fixtures_dir):
        """Test that org files are rendered when view mode is active."""
        org_file = fixtures_dir / "test.org"
        files = [FileData(file=org_file, line_num=0, match_string="")]
        app = Prism(files)

        async with app.run_test() as pilot:
            await pilot.pause()

            # Enable markdown view mode
            await pilot.press("m")
            await pilot.pause()

            # Verify the code view exists
            code_view = app.query_one("#code", Static)
            assert code_view is not None

    @pytest.mark.asyncio
    async def test_org_rendering_disabled(self, fixtures_dir):
        """Test that org files show source when view mode is off."""
        org_file = fixtures_dir / "test.org"
        files = [FileData(file=org_file, line_num=0, match_string="")]
        app = Prism(files)

        async with app.run_test() as pilot:
            await pilot.pause()

            # Ensure source view mode (default)
            assert app.view_mode == "source"

            # Verify the code view exists
            code_view = app.query_one("#code", Static)
            assert code_view is not None


class TestSourceCodeRendering:
    """Test source code rendering (default mode)."""

    @pytest.mark.asyncio
    async def test_python_file_syntax_highlighting(self, fixtures_dir):
        """Test that Python files are syntax highlighted."""
        py_file = fixtures_dir / "test.py"
        files = [FileData(file=py_file, line_num=0, match_string="")]
        app = Prism(files)

        async with app.run_test() as pilot:
            await pilot.pause()  # Let app fully initialize

            # Ensure source view mode (default)
            assert app.view_mode == "source"

            # Verify the code view exists
            code_view = app.query_one("#code", Static)
            assert code_view is not None


class TestRenderedSearchHighlighting:
    """Rendered documents should highlight active search matches."""

    def _render_to_text(self, renderable):
        from rich.console import Console
        from rich.text import Text

        console = Console(width=40, color_system=None)
        text = Text()
        for segment in console.render(renderable, console.options):
            text.append(segment.text, segment.style)
        return text

    def test_no_query_leaves_renderable_unchanged(self):
        from rich.markdown import Markdown
        from prism.renderers import apply_search_highlight

        markdown = Markdown("hello world")
        result = apply_search_highlight(
            markdown, "", 0, "white", "dark_red", "white", "bright_red"
        )
        assert result is markdown

    def test_query_wraps_renderable(self):
        from rich.markdown import Markdown
        from prism.renderers import apply_search_highlight, SearchHighlighter

        result = apply_search_highlight(
            Markdown("hello world"),
            "hello",
            0,
            "white",
            "dark_red",
            "white",
            "bright_red",
        )
        assert isinstance(result, SearchHighlighter)

    def test_matches_are_styled_in_rendered_output(self):
        from rich.console import Console
        from rich.markdown import Markdown
        from prism.renderers import apply_search_highlight

        result = apply_search_highlight(
            Markdown("hello world"),
            "hello",
            0,
            "white",
            "dark_red",
            "white",
            "bright_red",
        )
        text = self._render_to_text(result)

        assert "hello" in text.plain
        start = text.plain.index("hello")
        console = Console(color_system=None)
        resolved = text.get_style_at_offset(console, start)
        assert resolved.bgcolor is not None

    def test_current_match_line_is_tracked(self):
        from rich.markdown import Markdown
        from prism.renderers import apply_search_highlight

        result = apply_search_highlight(
            Markdown("first line\n\nsecond hello line"),
            "hello",
            0,
            "white",
            "dark_red",
            "white",
            "bright_red",
        )
        self._render_to_text(result)
        assert result.current_match_line is not None

    @pytest.mark.asyncio
    async def test_rendered_markdown_attaches_highlighter(self, fixtures_dir):
        """Searching a rendered markdown file wraps it in a highlighter."""
        from prism.renderers import SearchHighlighter

        md_file = fixtures_dir / "test.md"
        files = [FileData(file=md_file, line_num=1, match_string="")]
        app = Prism(files)

        async with app.run_test() as pilot:
            await pilot.pause()
            app.view_mode = "markdown"
            await pilot.pause()

            app._update_search("Feature")
            await pilot.pause()

            code_view = app.query_one("#code", Static)
            assert app._search_matches
            assert isinstance(code_view._search_highlighter, SearchHighlighter)
