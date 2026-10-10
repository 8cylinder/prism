"""Tests for the Prism TUI application."""

import json
from pathlib import Path
import pytest
from prism.prism import (
    Prism,
    FileData,
    FileListItem,
    load_keybindings,
    DEFAULT_BINDINGS,
)


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


class TestSearch:
    """Test the find / find next functionality in the text view."""

    @pytest.mark.asyncio
    async def test_search_shows_input_and_focuses(self, sample_files):
        """slash reveals the search input and focuses it."""
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()

            search_input = app.query_one("#search-input")
            assert search_input.display is False

            await pilot.press("slash")
            await pilot.pause()

            assert app.has_class("-searching")
            assert search_input.display is True
            assert app.focused is search_input

    @pytest.mark.asyncio
    async def test_typing_updates_matches(self, sample_files):
        """Typing a query highlights every match and selects the first."""
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()

            await pilot.press("slash")
            await pilot.pause()
            for char in "hello":
                await pilot.press(char)
            await pilot.pause()

            assert app._search_query == "hello"
            assert app._search_matches == [
                (4, 4, 9),
                (5, 11, 16),
                (6, 13, 18),
                (10, 10, 15),
            ]
            assert app._current_match_index == 0

    @pytest.mark.asyncio
    async def test_search_is_case_insensitive(self, sample_files):
        """Search matches are found regardless of case."""
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()

            await pilot.press("slash")
            for char in "HELLO":
                await pilot.press(char)
            await pilot.pause()

            assert app._search_query == "HELLO"
            assert len(app._search_matches) == 4

    @pytest.mark.asyncio
    async def test_find_next_cycles_matches(self, sample_files):
        """ctrl-n advances the current match and wraps around."""
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()

            await pilot.press("slash")
            for char in "hello":
                await pilot.press(char)
            await pilot.pause()
            assert app._current_match_index == 0

            await pilot.press("ctrl+n")
            await pilot.pause()
            assert app._current_match_index == 1

            await pilot.press("ctrl+n")
            await pilot.pause()
            assert app._current_match_index == 2

            await pilot.press("ctrl+n")
            await pilot.pause()
            assert app._current_match_index == 3

            await pilot.press("ctrl+n")
            await pilot.pause()
            assert app._current_match_index == 0

    @pytest.mark.asyncio
    async def test_find_prev_cycles_matches(self, sample_files):
        """ctrl-p moves backwards through matches and wraps around."""
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()

            await pilot.press("slash")
            for char in "hello":
                await pilot.press(char)
            await pilot.pause()
            assert app._current_match_index == 0

            await pilot.press("ctrl+p")
            await pilot.pause()
            assert app._current_match_index == 3

            await pilot.press("ctrl+p")
            await pilot.pause()
            assert app._current_match_index == 2

    @pytest.mark.asyncio
    async def test_escape_clears_matches(self, sample_files):
        """Escape clears matches and highlights but remembers the query."""
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()

            await pilot.press("slash")
            for char in "hello":
                await pilot.press(char)
            await pilot.pause()

            await pilot.press("escape")
            await pilot.pause()

            assert app._search_matches == []
            assert app._search_query == ""
            assert app._last_search == "hello"
            assert not app.has_class("-searching")

    @pytest.mark.asyncio
    async def test_search_reuses_last_string(self, sample_files):
        """slash after clearing defaults to the last used search string."""
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()

            await pilot.press("slash")
            for char in "hello":
                await pilot.press(char)
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()

            await pilot.press("slash")
            await pilot.pause()

            search_input = app.query_one("#search-input")
            assert search_input.value == "hello"
            assert app._search_query == "hello"
            assert len(app._search_matches) == 4

    @pytest.mark.asyncio
    async def test_backspace_updates_matches(self, sample_files):
        """Backspace removes a character and updates the matches."""
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()

            await pilot.press("slash")
            for char in "hello":
                await pilot.press(char)
            await pilot.pause()

            await pilot.press("backspace")
            await pilot.pause()

            assert app._search_query == "hell"

    @pytest.mark.asyncio
    async def test_enter_accepts_search(self, sample_files):
        """Enter hides the input but keeps the matches and returns focus."""
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()

            await pilot.press("slash")
            for char in "hello":
                await pilot.press(char)
            await pilot.pause()

            await pilot.press("enter")
            await pilot.pause()

            assert not app.has_class("-searching")
            assert app._search_query == "hello"
            assert len(app._search_matches) == 4
            assert app.focused is app.query_one("#file-list")


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


class TestKeybindings:
    """Test JSON keybindings loading and fallback logic."""

    def test_load_default_keybindings(self):
        """Test loading default keybindings from package JSON or defaults."""
        bindings = load_keybindings()
        assert len(bindings) > 0
        actions = [b.action for b in bindings]
        assert "toggle_files" in actions
        assert "edit_file" in actions

    def test_load_custom_json_keybindings(self, tmp_path):
        """Test loading keybindings from a custom JSON file."""
        custom_json = tmp_path / "shortcuts.json"
        custom_json.write_text(
            json.dumps(
                [
                    {
                        "key": "x",
                        "action": "toggle_files",
                        "description": "Custom Toggle",
                    },
                    {"key": "y", "action": "quit", "description": "Custom Quit"},
                ]
            )
        )
        bindings = load_keybindings(custom_json)
        assert len(bindings) == 2
        assert bindings[0].key == "x"
        assert bindings[0].action == "toggle_files"
        assert bindings[1].key == "y"
        assert bindings[1].action == "quit"

    def test_invalid_json_fallback(self, tmp_path):
        """Test falling back to default bindings when JSON is invalid."""
        invalid_json = tmp_path / "invalid.json"
        invalid_json.write_text("{ invalid json ... }")
        bindings = load_keybindings(invalid_json)
        assert bindings == DEFAULT_BINDINGS
