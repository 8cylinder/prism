"""Tests for CLI parsing functionality."""

from pathlib import Path
import pytest
from prism.cli import parse_filename


@pytest.fixture
def fixtures_dir():
    """Return the path to the fixtures directory."""
    return Path(__file__).parent / "fixtures"


class TestFilenameParsing:
    """Test the parse_filename function."""

    def test_parse_plain_path(self, fixtures_dir):
        """Test parsing a plain file path."""
        test_file = fixtures_dir / "test.py"
        result = parse_filename(str(test_file))
        assert result.file == test_file
        assert result.line_num == 0
        assert result.match_string == ""

    def test_parse_path_with_line_number(self, fixtures_dir):
        """Test parsing file:line:match format (line number requires 3 parts)."""
        test_file = fixtures_dir / "test.py"
        # Note: line number requires format file:line:match
        # Format file:42 is treated as file:match_string
        result = parse_filename(f"{test_file}:42:")
        assert result.file == test_file
        assert result.line_num == 42
        assert result.match_string == ""

    def test_parse_path_with_line_and_match(self, fixtures_dir):
        """Test parsing file:123:match_string format."""
        test_file = fixtures_dir / "test.py"
        result = parse_filename(f"{test_file}:42:hello world")
        assert result.file == test_file
        assert result.line_num == 42
        assert result.match_string == "hello world"

    def test_parse_path_with_match_only(self, fixtures_dir):
        """Test parsing file:match_string format (no line number)."""
        test_file = fixtures_dir / "test.py"
        result = parse_filename(f"{test_file}:search term")
        assert result.file == test_file
        assert result.line_num == 0
        assert result.match_string == "search term"

    def test_parse_relative_path(self):
        """Test parsing relative paths."""
        # Use a file that exists in the project
        result = parse_filename("src/prism/cli.py:10:test")
        assert result.file == Path("src/prism/cli.py")
        assert result.line_num == 10
        assert result.match_string == "test"

    def test_parse_path_with_colon_in_match(self, fixtures_dir):
        """Test parsing when match string contains colons."""
        test_file = fixtures_dir / "test.py"
        result = parse_filename(f"{test_file}:42:https://example.com")
        assert result.file == test_file
        assert result.line_num == 42
        assert result.match_string == "https://example.com"
