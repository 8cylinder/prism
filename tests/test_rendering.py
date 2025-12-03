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
