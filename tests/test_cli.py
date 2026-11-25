"""Tests for CLI parsing functionality."""

from pathlib import Path
from typing import ClassVar

import click
import pytest
from click.testing import CliRunner

from prism.cli import (
    _read_input,
    main,
    make_console,
    parse_filename,
    parse_stdin,
    prism,
)
from prism.config import AppConfig
from prism.prism import FileData


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the fixtures directory."""
    return Path(__file__).parent / "fixtures"


class TestFilenameParsing:
    """Test the parse_filename function."""

    def test_parse_plain_path(self, fixtures_dir: Path) -> None:
        """Test parsing a plain file path."""
        test_file = fixtures_dir / "test.py"
        result = parse_filename(str(test_file))
        assert result is not None
        assert result.file == test_file
        assert result.line_num == 0
        assert result.match_string == ""

    def test_parse_path_with_line_number(self, fixtures_dir: Path) -> None:
        """Test parsing file:line:match format (line number requires 3 parts)."""
        test_file = fixtures_dir / "test.py"
        # Note: line number requires format file:line:match
        # Format file:42 is treated as file:match_string
        result = parse_filename(f"{test_file}:42:")
        assert result is not None
        assert result.file == test_file
        assert result.line_num == 42
        assert result.match_string == ""

    def test_parse_path_with_line_and_match(self, fixtures_dir: Path) -> None:
        """Test parsing file:123:match_string format."""
        test_file = fixtures_dir / "test.py"
        result = parse_filename(f"{test_file}:42:hello world")
        assert result is not None
        assert result.file == test_file
        assert result.line_num == 42
        assert result.match_string == "hello world"

    def test_parse_path_with_match_only(self, fixtures_dir: Path) -> None:
        """Test parsing file:match_string format (no line number)."""
        test_file = fixtures_dir / "test.py"
        result = parse_filename(f"{test_file}:search term")
        assert result is not None
        assert result.file == test_file
        assert result.line_num == 0
        assert result.match_string == "search term"

    def test_parse_relative_path(self) -> None:
        """Test parsing relative paths."""
        # Use a file that exists in the project
        result = parse_filename("src/prism/cli.py:10:test")
        assert result is not None
        assert result.file == Path("src/prism/cli.py")
        assert result.line_num == 10
        assert result.match_string == "test"

    def test_parse_path_with_colon_in_match(self, fixtures_dir: Path) -> None:
        """Test parsing when match string contains colons."""
        test_file = fixtures_dir / "test.py"
        result = parse_filename(f"{test_file}:42:https://example.com")
        assert result is not None
        assert result.file == test_file
        assert result.line_num == 42
        assert result.match_string == "https://example.com"


class TestParseStdin:
    def test_empty_input(self) -> None:
        assert parse_stdin("", null_sep=False) == []

    def test_newline_input(self, fixtures_dir: Path) -> None:
        raw = f"{fixtures_dir / 'test.py'}\n{fixtures_dir / 'test.md'}"
        parsed = parse_stdin(raw, null_sep=False)
        assert len(parsed) == 2

    def test_null_input(self, fixtures_dir: Path) -> None:
        raw = f"{fixtures_dir / 'test.py'}\0{fixtures_dir / 'test.md'}\0"
        parsed = parse_stdin(raw, null_sep=True)
        assert len(parsed) == 2

    def test_warning_callback(self, tmp_path: Path) -> None:
        warnings: list[str] = []
        assert parse_filename(str(tmp_path), warn=warnings.append) is None
        assert warnings
        assert "Skipping directory" in warnings[0]


class TestParseFilenameErrors:
    def test_directory_skipped(self, tmp_path: Path) -> None:
        assert parse_filename(str(tmp_path)) is None

    def test_broken_symlink_skipped(self, tmp_path: Path) -> None:
        link = tmp_path / "broken"
        link.symlink_to(tmp_path / "missing")
        assert parse_filename(str(link)) is None

    def test_missing_path_raises(self, tmp_path: Path) -> None:
        with pytest.raises(click.BadParameter):
            parse_filename(str(tmp_path / "missing.py"))

    def test_invalid_line_number_raises(self, fixtures_dir: Path) -> None:
        with pytest.raises(click.BadParameter):
            parse_filename(f"{fixtures_dir / 'test.py'}:abc:match")


class FakePrism:
    started: ClassVar[list[dict[str, object]]] = []

    def __init__(self, files: list[FileData], config: AppConfig) -> None:
        self.files = files
        self.config = config
        self.ran = False

    def run(self) -> None:
        self.ran = True
        FakePrism.started.append({"files": self.files, "config": self.config})


@pytest.fixture
def fake_app(monkeypatch: pytest.MonkeyPatch) -> type[FakePrism]:
    FakePrism.started = []
    monkeypatch.setattr("prism.cli.Prism", FakePrism)
    return FakePrism


@pytest.fixture
def xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


class TestCliBehavior:
    def test_help(self) -> None:
        result = CliRunner().invoke(prism, ["-h"])
        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "\x1b[" not in result.output

    def test_long_help(self) -> None:
        result = CliRunner().invoke(prism, ["--help"])
        assert result.exit_code == 0
        assert "--completions" in result.output

    def test_version_matches_pyproject(self) -> None:
        import tomllib

        with open("pyproject.toml", "rb") as stream:
            version = tomllib.load(stream)["project"]["version"]
        result = CliRunner().invoke(prism, ["--version"])
        assert result.exit_code == 0
        assert result.output.strip() == f"prism, version {version}"
        assert "\x1b[" not in result.output

    def test_debug_data(self, fixtures_dir: Path, xdg: Path) -> None:
        result = CliRunner().invoke(
            prism,
            ["--debug-data", f"{fixtures_dir / 'test.py'}:42:hello"],
        )
        assert result.exit_code == 0
        assert "line_num=42" in result.output

    def test_debug_data_skips_directory(
        self, tmp_path: Path, xdg: Path
    ) -> None:
        result = CliRunner().invoke(prism, ["--debug-data", str(tmp_path)])
        assert result.exit_code == 0
        assert "Skipping directory" in result.stderr

    def test_broken_symlink_message(self, tmp_path: Path, xdg: Path) -> None:
        link = tmp_path / "broken"
        link.symlink_to(tmp_path / "missing")
        result = CliRunner().invoke(prism, ["--debug-data", str(link)])
        assert result.exit_code == 0
        assert "Skipping broken symlink" in result.stderr

    def test_missing_path_exit_code(self, tmp_path: Path, xdg: Path) -> None:
        result = CliRunner().invoke(prism, [str(tmp_path / "missing.py")])
        assert result.exit_code == 2
        assert "does not exist" in result.stderr

    def test_invalid_line_number_exit_code(
        self, fixtures_dir: Path, xdg: Path
    ) -> None:
        result = CliRunner().invoke(
            prism, [f"{fixtures_dir / 'test.py'}:abc:match"]
        )
        assert result.exit_code == 2
        assert "Invalid line number" in result.stderr

    def test_empty_input_error(self, xdg: Path) -> None:
        result = CliRunner().invoke(prism, [], input="")
        assert result.exit_code == 1
        assert "No search results to show." in result.stderr

    def test_no_input_in_pipe_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class Tty:
            def isatty(self) -> bool:
                return True

        monkeypatch.setattr("prism.cli.sys.stdin", Tty())
        with pytest.raises(click.exceptions.Exit) as excinfo:
            _read_input((), make_console("never", stderr=True))
        assert excinfo.value.exit_code == 1

    def test_runs_app_with_args(self, fake_app: type[FakePrism]) -> None:
        result = CliRunner().invoke(prism, ["tests/fixtures/test.py"])
        assert result.exit_code == 0
        assert fake_app.started
        assert fake_app.started[0]["files"]

    def test_runs_app_with_piped_input(self, fake_app: type[FakePrism]) -> None:
        result = CliRunner().invoke(prism, [], input="tests/fixtures/test.py\n")
        assert result.exit_code == 0
        assert fake_app.started

    def test_config_warning_is_printed(
        self, xdg: Path, fake_app: type[FakePrism]
    ) -> None:
        config = xdg / "config" / "prism" / "config.toml"
        config.parent.mkdir(parents=True)
        config.write_text("unknown = true\n")
        result = CliRunner().invoke(prism, ["tests/fixtures/test.py"])
        assert result.exit_code == 0
        assert "warning:" in result.stderr
        assert "unknown" in result.stderr

    def test_legacy_config_warning(
        self, xdg: Path, fake_app: type[FakePrism]
    ) -> None:
        legacy = xdg / "config" / "prism" / "shortcuts.json"
        legacy.parent.mkdir(parents=True)
        legacy.write_text(
            '[{"key": "x", "action": "quit", "description": "Quit"}]'
        )
        result = CliRunner().invoke(prism, ["tests/fixtures/test.py"])
        assert result.exit_code == 0
        assert "legacy shortcuts file" in result.stderr


class TestColor:
    def test_always_emits_ansi(self, xdg: Path) -> None:
        result = CliRunner().invoke(prism, ["--color", "always"], input="")
        assert result.exit_code == 1
        assert "\x1b[" in result.stderr

    def test_never_emits_no_ansi(self, xdg: Path) -> None:
        result = CliRunner().invoke(prism, ["--color", "never"], input="")
        assert result.exit_code == 1
        assert "\x1b[" not in result.stderr

    def test_auto_emits_no_ansi_when_captured(self, xdg: Path) -> None:
        result = CliRunner().invoke(prism, ["--color", "auto"], input="")
        assert result.exit_code == 1
        assert "\x1b[" not in result.stderr

    def test_make_console_modes(self) -> None:
        assert make_console("always").is_terminal is True
        assert make_console("never").color_system is None
        assert make_console("never", stderr=True).stderr is True

    def test_no_color(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FORCE_COLOR", raising=False)
        monkeypatch.setenv("NO_COLOR", "1")
        assert make_console("auto").color_system is None

    def test_force_color(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.setenv("FORCE_COLOR", "1")
        console = make_console("auto")
        assert console.is_terminal is True
        assert console.color_system is not None

    def test_force_color_wins_over_no_color(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NO_COLOR", "1")
        monkeypatch.setenv("FORCE_COLOR", "1")
        console = make_console("auto")
        assert console.is_terminal is True
        assert console.color_system is not None

    def test_always_overrides_no_color(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NO_COLOR", "1")
        assert make_console("always").no_color is False

    def test_term_dumb_disables_color(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("FORCE_COLOR", raising=False)
        monkeypatch.delenv("NO_COLOR", raising=False)
        monkeypatch.setenv("TERM", "dumb")
        assert make_console("auto").color_system is None

    def test_markup_is_escaped(
        self, tmp_path: Path, xdg: Path, fake_app: type[FakePrism]
    ) -> None:
        directory = tmp_path / "[red]not markup"
        directory.mkdir()
        result = CliRunner().invoke(prism, ["--debug-data", str(directory)])
        assert result.exit_code == 0
        assert "[red]not markup" in result.stderr
        assert "\x1b[31m" not in result.stderr


class TestCompletionsOption:
    def test_completions_writes_file(self, tmp_path: Path, xdg: Path) -> None:
        destination = tmp_path / "completions"
        result = CliRunner().invoke(
            prism,
            ["--completions"],
            env={"BASH_COMPLETION_USER_DIR": str(destination)},
        )
        assert result.exit_code == 0
        path = destination / "bash-completion" / "completions" / "prism.bash"
        assert result.stdout.strip() == str(path)
        assert path.is_file()
        assert "source " + str(path) in result.stderr
        assert "\x1b[" not in result.stdout


class TestMain:
    def test_main_invokes_command(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []

        def fake_prism(*, prog_name: str) -> None:
            calls.append(prog_name)

        monkeypatch.setattr("prism.cli.prism", fake_prism)
        main()
        assert calls == ["prism"]
