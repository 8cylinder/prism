"""Tests for the Prism TUI application."""

from pathlib import Path
import pytest
from prism.prism import Prism, FileData, FileListItem


@pytest.fixture
def fixtures_dir():
    """Return the path to the fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_files(fixtures_dir):
    """Create sample FileData for testing with real files."""
    return [
        FileData(file=fixtures_dir / "test.py", line_num=3, match_string="def"),
        FileData(file=fixtures_dir / "test.md", line_num=1, match_string="Test"),
        FileData(file=fixtures_dir / "test.html", line_num=0, match_string=""),
    ]


class TestPrismApp:
    """Test the main Prism application."""

    @pytest.mark.asyncio
    async def test_app_starts(self, sample_files):
        """Test that the app starts successfully."""
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()  # Let app fully initialize
            assert app.is_running

    @pytest.mark.asyncio
    async def test_app_has_file_list(self, sample_files):
        """Test that the file list is populated."""
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()  # Let app fully initialize

            list_view = app.query_one("#file-list")
            assert list_view is not None

            # Check that list items were created
            items = app.query(FileListItem)
            assert len(items) == len(sample_files)

    @pytest.mark.asyncio
    async def test_file_list_state_toggle(self, sample_files):
        """Test toggling file list width states."""
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()  # Let app fully initialize

            # Start in narrow state
            assert app.file_list_state == "narrow"

            # Toggle to wide
            await pilot.press("f")
            await pilot.pause()
            assert app.file_list_state == "wide"

            # Toggle to hidden
            await pilot.press("f")
            await pilot.pause()
            assert app.file_list_state == "hidden"

            # Toggle back to narrow
            await pilot.press("f")
            await pilot.pause()
            assert app.file_list_state == "narrow"

    @pytest.mark.asyncio
    async def test_view_mode_toggle(self, sample_files):
        """Test toggling between source and markdown view modes."""
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()  # Let app fully initialize

            # Start in source mode
            assert app.view_mode == "source"

            # Toggle to markdown
            await pilot.press("m")
            await pilot.pause()
            assert app.view_mode == "markdown"

            # Toggle back to source
            await pilot.press("m")
            await pilot.pause()
            assert app.view_mode == "source"

    @pytest.mark.asyncio
    async def test_word_wrap_toggle(self, sample_files):
        """Test toggling word wrap."""
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()  # Let app fully initialize

            # Start with word wrap off
            assert app.word_wrap is False

            # Toggle word wrap on
            await pilot.press("w")
            await pilot.pause()
            assert app.word_wrap is True

            # Toggle word wrap off
            await pilot.press("w")
            await pilot.pause()
            assert app.word_wrap is False

    @pytest.mark.asyncio
    async def test_navigation_next_item(self, sample_files):
        """Test navigating to next item."""
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()  # Let app fully initialize

            list_view = app.query_one("#file-list")

            # Start at first item
            initial_index = list_view.index
            assert initial_index == 0

            # Navigate to next item
            await pilot.press("j")
            await pilot.pause()
            assert list_view.index == 1

            # Navigate to next item again
            await pilot.press("n")
            await pilot.pause()
            assert list_view.index == 2

    @pytest.mark.asyncio
    async def test_navigation_prev_item(self, sample_files):
        """Test navigating to previous item."""
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()  # Let app fully initialize

            list_view = app.query_one("#file-list")

            # Move to second item first
            await pilot.press("j")
            await pilot.pause()
            assert list_view.index == 1

            # Navigate to previous item
            await pilot.press("k")
            await pilot.pause()
            assert list_view.index == 0

    @pytest.mark.asyncio
    async def test_quit_app(self, sample_files):
        """Test quitting the app."""
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()  # Let app fully initialize
            assert app.is_running

            # Quit the app
            await pilot.press("q")
            await pilot.pause()
            # App should stop running

    @pytest.mark.asyncio
    async def test_binary_file_handling(self, fixtures_dir, tmp_path):
        """Test that binary files display a user-friendly message."""
        # Create a binary file with invalid UTF-8 bytes
        binary_file = tmp_path / "test.bin"
        binary_file.write_bytes(b"\xff\xfe\x00\x01\x02\x03\x04\x05")

        files = [FileData(file=binary_file, line_num=0, match_string="")]
        app = Prism(files)

        async with app.run_test() as pilot:
            await pilot.pause()  # Let app fully initialize

            # The app should show a user-friendly message, not crash
            assert app.is_running
            # Title should indicate binary file
            assert app.title == "Binary file"


class TestFileListItem:
    """Test the FileListItem widget."""

    def test_file_list_item_creation(self):
        """Test creating a FileListItem."""
        file_data = FileData(file=Path("test.py"), line_num=10, match_string="hello")
        item = FileListItem(file_data, is_last=False)

        assert item.data == file_data
        assert item.is_last is False

    def test_file_list_item_last(self):
        """Test creating a FileListItem marked as last."""
        file_data = FileData(file=Path("test.py"), line_num=10, match_string="hello")
        item = FileListItem(file_data, is_last=True)

        assert item.is_last is True


class TestFileData:
    """Test the FileData dataclass."""

    def test_file_data_creation(self):
        """Test creating FileData."""
        file_data = FileData(
            file=Path("test.py"), line_num=42, match_string="search term"
        )

        assert file_data.file == Path("test.py")
        assert file_data.line_num == 42
        assert file_data.match_string == "search term"
        assert file_data.column == 0  # default value

    def test_file_data_with_column(self):
        """Test creating FileData with column position."""
        file_data = FileData(
            file=Path("test.py"), line_num=42, match_string="search", column=10
        )

        assert file_data.column == 10
