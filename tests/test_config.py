"""Tests for prism's configuration handling."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from prism.cli import prism
from prism.config import (
    AppConfig,
    ConfigError,
    Shortcut,
    config_path,
    legacy_shortcuts_path,
    load_config,
)


@pytest.fixture
def config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point platformdirs at a temporary configuration directory."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def write_config(home: Path, content: str) -> Path:
    path = home / "prism" / "config.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


class TestConfigPaths:
    def test_config_path_uses_xdg(self, config_home: Path) -> None:
        assert config_path() == config_home / "prism" / "config.toml"

    def test_legacy_path(self, config_home: Path) -> None:
        assert (
            legacy_shortcuts_path() == config_home / "prism" / "shortcuts.json"
        )


class TestLoadConfig:
    def test_missing_config_uses_defaults(self, config_home: Path) -> None:
        loaded = load_config()
        assert loaded.config == AppConfig()
        assert loaded.config.shortcuts is None
        assert loaded.warnings == ()

    def test_valid_config(self, config_home: Path) -> None:
        write_config(
            config_home,
            """
[[shortcuts]]
key = "x"
action = "toggle_files"
description = "Toggle Files"

[[shortcuts]]
key = "y"
action = "quit"
description = "Quit"
show = false
key_display = "Y"
priority = true
""",
        )
        loaded = load_config()
        assert loaded.warnings == ()
        assert loaded.config.shortcuts == (
            Shortcut("x", "toggle_files", "Toggle Files"),
            Shortcut(
                "y",
                "quit",
                "Quit",
                show=False,
                key_display="Y",
                priority=True,
            ),
        )

    def test_unknown_key_warns(self, config_home: Path) -> None:
        write_config(config_home, "mystery = true\n")
        loaded = load_config()
        assert loaded.config == AppConfig()
        assert len(loaded.warnings) == 1
        assert "mystery" in loaded.warnings[0]

    def test_invalid_toml_names_path(self, config_home: Path) -> None:
        path = write_config(config_home, "not valid = [\n")
        with pytest.raises(ConfigError, match=str(path)):
            load_config()

    @pytest.mark.parametrize(
        "content",
        [
            "shortcuts = 3\n",
            "shortcuts = [3]\n",
            "[[shortcuts]]\nkey = 'x'\naction = 'quit'\n",
            "[[shortcuts]]\nkey = 3\naction = 'quit'\ndescription = 'd'\n",
            "[[shortcuts]]\nkey = 'x'\naction = 'quit'\ndescription = ''\n",
            "[[shortcuts]]\nkey = 'x'\naction = 'quit'\ndescription = 'd'\nshow = 1\n",
            "[[shortcuts]]\nkey = 'x'\naction = 'quit'\ndescription = 'd'\npriority = 1\n",
            "[[shortcuts]]\nkey = 'x'\naction = 'quit'\ndescription = 'd'\nkey_display = 1\n",
        ],
    )
    def test_invalid_shortcuts(self, config_home: Path, content: str) -> None:
        write_config(config_home, content)
        with pytest.raises(ConfigError):
            load_config()

    def test_unknown_shortcut_field_warns(self, config_home: Path) -> None:
        write_config(
            config_home,
            "[[shortcuts]]\n"
            "key = 'x'\n"
            "action = 'quit'\n"
            "description = 'd'\n"
            "extra = 1\n",
        )
        loaded = load_config()
        assert loaded.config.shortcuts == (Shortcut("x", "quit", "d"),)
        assert len(loaded.warnings) == 1
        assert "extra" in loaded.warnings[0]

    def test_legacy_shortcuts_warns(self, config_home: Path) -> None:
        path = config_home / "prism" / "shortcuts.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            '[{"key": "x", "action": "quit", "description": "Quit"}]'
        )
        loaded = load_config()
        assert loaded.config.shortcuts == (Shortcut("x", "quit", "Quit"),)
        assert len(loaded.warnings) == 1
        assert "legacy shortcuts file" in loaded.warnings[0]

    def test_toml_takes_precedence_over_legacy(self, config_home: Path) -> None:
        write_config(
            config_home,
            "[[shortcuts]]\nkey = 't'\naction = 'quit'\ndescription = 'Toml'\n",
        )
        legacy = config_home / "prism" / "shortcuts.json"
        legacy.write_text(
            '[{"key": "j", "action": "quit", "description": "Json"}]'
        )
        loaded = load_config()
        assert loaded.config.shortcuts == (Shortcut("t", "quit", "Toml"),)

    def test_invalid_legacy_json_names_path(self, config_home: Path) -> None:
        path = config_home / "prism" / "shortcuts.json"
        path.parent.mkdir(parents=True)
        path.write_text("{ invalid")
        with pytest.raises(ConfigError, match=str(path)):
            load_config()


class TestConfigOption:
    def test_config_prints_path_only(
        self, config_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("COLUMNS", raising=False)
        result = CliRunner().invoke(prism, ["--config"])
        assert result.exit_code == 0
        assert result.output.strip() == str(
            config_home / "prism" / "config.toml"
        )
        assert "\x1b[" not in result.output
        assert not (config_home / "prism").exists()

    def test_config_works_without_other_options(
        self, config_home: Path
    ) -> None:
        result = CliRunner().invoke(prism, ["--config"])
        assert result.exit_code == 0

    def test_invalid_config_exits_nonzero(self, config_home: Path) -> None:
        path = write_config(config_home, "not valid = [\n")
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(prism, ["some-file"], env={"COLUMNS": "500"})
        assert result.exit_code == 1
        assert str(path) in result.stderr
        assert "Expected" in result.stderr
        assert "error:" in result.stderr
