"""Tests for static bash completion generation and installation."""

from __future__ import annotations

import os
import shlex
import shutil
import stat
import subprocess
from pathlib import Path

import click
import pytest

from prism.completions import (
    _bash_version,
    _help_option_names,
    _value_spec,
    completion_dir,
    generate_bash,
    install_bash_completion,
)


@click.group()
def demo() -> None:
    """Demo command group."""


@demo.command()
@click.option("--mode", type=click.Choice(["fast", "slow"]))
@click.option("--out", type=click.Path(file_okay=False))
@click.option("--src", type=click.Path())
@click.option("--input", type=click.File())
@click.option("--when", type=click.DateTime())
@click.option("--count", type=int)
@click.option("--pair", type=click.Tuple([str, int]))
@click.option(
    "--pick",
    type=click.Tuple([click.Choice(["one"]), click.Choice(["two"])]),
)
@click.option("--many", multiple=True)
@click.option("-v", "--verbose", count=True)
@click.option("--hidden-opt", hidden=True)
@click.argument("target", type=click.Path())
def run(
    mode: str | None,
    out: str | None,
    src: str | None,
    input: object,
    when: object,
    count: int | None,
    pair: tuple[str, int] | None,
    pick: tuple[str, str] | None,
    many: tuple[str, ...],
    verbose: int,
    hidden_opt: str | None,
    target: str,
) -> None:
    """Run the demo."""


@demo.command(hidden=True)
def secret() -> None:
    """Hidden command."""


@pytest.fixture
def script(tmp_path: Path) -> Path:
    path = tmp_path / "demo.bash"
    path.write_text(generate_bash(demo, "demo", "1.0.0"))
    return path


def run_completion(
    script_path: Path, words: list[str], cword: int
) -> list[str]:
    quoted = " ".join(shlex.quote(word) for word in words)
    command = (
        f"source {shlex.quote(str(script_path))}\n"
        f"COMP_WORDS=( {quoted} )\n"
        f"COMP_CWORD={cword}\n"
        "COMPREPLY=()\n"
        "_demo_complete\n"
        'printf "%s\\n" "${COMPREPLY[@]}"\n'
    )
    result = subprocess.run(
        ["bash", "-c", command],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    output = result.stdout.rstrip("\n")
    return output.splitlines() if output else []


pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None, reason="bash is required"
)


class TestGenerate:
    def test_script_parses(self, script: Path) -> None:
        result = subprocess.run(
            ["bash", "-n", str(script)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

    def test_header_and_registration(self, script: Path) -> None:
        content = script.read_text()
        assert "# bash completion for demo 1.0.0" in content
        assert "do not edit" not in content
        assert "generated and will be overwritten" in content
        assert "complete -o nosort" in content
        assert "_demo_complete" in content

    def test_hidden_items_are_not_suggested(self, script: Path) -> None:
        content = script.read_text()
        assert "secret" not in content
        assert "--hidden-opt" not in content

    def test_subcommands(self, script: Path) -> None:
        assert "run" in run_completion(script, ["demo", ""], 1)

    def test_options(self, script: Path) -> None:
        completions = run_completion(script, ["demo", "run", "-"], 2)
        assert "--mode" in completions
        assert "-v" in completions
        assert "--help" in completions
        assert "--hidden-opt" not in completions

    def test_choice_values(self, script: Path) -> None:
        completions = run_completion(script, ["demo", "run", "--mode", ""], 3)
        assert completions == ["fast", "slow"]

    def test_choice_equals_value(self, script: Path) -> None:
        completions = run_completion(script, ["demo", "run", "--mode=f"], 2)
        assert completions == ["--mode=fast"]

    def test_directory_values(self, script: Path, tmp_path: Path) -> None:
        (tmp_path / "alpha").mkdir()
        (tmp_path / "beta.txt").write_text("x")
        completions = run_completion(
            script,
            ["demo", "run", "--out", str(tmp_path) + "/"],
            3,
        )
        assert any(item.rstrip("/").endswith("alpha") for item in completions)
        assert not any(item.endswith("beta.txt") for item in completions)

    def test_file_values(self, script: Path, tmp_path: Path) -> None:
        (tmp_path / "beta.txt").write_text("x")
        completions = run_completion(
            script,
            ["demo", "run", "--src", str(tmp_path) + "/"],
            3,
        )
        assert any(item.endswith("beta.txt") for item in completions)

    def test_no_option_completion_after_double_dash(self, script: Path) -> None:
        completions = run_completion(script, ["demo", "run", "--", "--m"], 3)
        assert completions == []

    def test_unknown_option_value_has_no_fallback(self, script: Path) -> None:
        completions = run_completion(script, ["demo", "run", "--when", ""], 3)
        assert completions == []

    def test_multiple_and_count_do_not_crash(self, script: Path) -> None:
        run_completion(script, ["demo", "run", "-v", ""], 3)
        run_completion(script, ["demo", "run", "--many", "x", ""], 4)


class TestValueSpecs:
    def test_choice(self) -> None:
        spec = _value_spec(click.Choice(["a", "b"]))
        assert spec.kind == "choices"
        assert spec.choices == ("a", "b")

    def test_empty_choice(self) -> None:
        spec = _value_spec(click.Choice([]))
        assert spec.kind == "choices"
        assert spec.choices == ()

    def test_file_and_directory_paths(self) -> None:
        assert _value_spec(click.Path()).kind == "files"
        assert _value_spec(click.Path(file_okay=False)).kind == "dirs"

    def test_click_file(self) -> None:
        assert _value_spec(click.File()).kind == "files"

    def test_datetime_has_no_suggestions(self) -> None:
        assert _value_spec(click.DateTime()).kind == "none"

    def test_tuple_uses_position_specific_types(self) -> None:
        spec = _value_spec(click.Tuple([click.Choice(["x"]), click.Path()]))
        assert spec.kind == "tuple"
        assert [part.kind for part in spec.parts] == ["choices", "files"]
        spec = _value_spec(click.Tuple([click.DateTime(), click.Path()]))
        assert spec.kind == "tuple"
        assert [part.kind for part in spec.parts] == ["none", "files"]
        spec = _value_spec(
            click.Tuple([click.DateTime(), click.IntRange(1, 2)])
        )
        assert spec.kind == "none"

    def test_tuple_values_are_completed_by_position(self, script: Path) -> None:
        assert run_completion(script, ["demo", "run", "--pick", ""], 3) == [
            "one"
        ]
        assert run_completion(
            script, ["demo", "run", "--pick", "one", ""], 4
        ) == ["two"]

    def test_tuple_equals_value(self, script: Path) -> None:
        assert run_completion(script, ["demo", "run", "--pick=o"], 2) == [
            "--pick=one"
        ]

    def test_default_help_names(self) -> None:
        @click.command()
        def plain() -> None:
            pass

        assert _help_option_names(plain) == ("-h", "--help")


class TestCompletionDirectory:
    def test_user_dir_precedence(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv(
            "BASH_COMPLETION_USER_DIR",
            os.pathsep.join(["", str(tmp_path / "one"), str(tmp_path / "two")]),
        )
        expected = tmp_path / "one" / "bash-completion" / "completions"
        assert completion_dir() == expected

    def test_xdg_data_home(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("BASH_COMPLETION_USER_DIR", raising=False)
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
        assert completion_dir() == (
            tmp_path / "data" / "bash-completion" / "completions"
        )

    def test_home_fallback(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("BASH_COMPLETION_USER_DIR", raising=False)
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        assert completion_dir() == (
            tmp_path / ".local" / "share" / "bash-completion" / "completions"
        )


class TestInstall:
    def test_writes_and_prints(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(
            "prism.completions.completion_dir", lambda: tmp_path
        )
        path = install_bash_completion(
            demo, "demo", "1.0.0", version_checker=lambda _: (5, 2)
        )
        assert path == tmp_path / "demo.bash"
        assert path.is_file()
        assert stat.S_IMODE(path.stat().st_mode) == 0o644
        captured = capsys.readouterr()
        assert captured.out.strip() == str(path)
        assert "source" in captured.err

    def test_overwrites_existing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(
            "prism.completions.completion_dir", lambda: tmp_path
        )
        target = tmp_path / "demo.bash"
        target.write_text("old")
        install_bash_completion(
            demo, "demo", "1.0.0", version_checker=lambda _: (5, 2)
        )
        assert "old" not in target.read_text()

    def test_missing_bash_warns(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(
            "prism.completions.completion_dir", lambda: tmp_path
        )
        monkeypatch.setattr("prism.completions.shutil.which", lambda _: None)
        install_bash_completion(demo, "demo", "1.0.0")
        assert "bash was not found" in capsys.readouterr().err

    def test_old_bash_warns(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(
            "prism.completions.completion_dir", lambda: tmp_path
        )
        monkeypatch.setattr(
            "prism.completions.shutil.which", lambda _: "/bin/bash"
        )
        install_bash_completion(
            demo, "demo", "1.0.0", version_checker=lambda _: (3, 2)
        )
        assert "too old" in capsys.readouterr().err

    def test_unknown_bash_version_warns(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(
            "prism.completions.completion_dir", lambda: tmp_path
        )
        monkeypatch.setattr(
            "prism.completions.shutil.which", lambda _: "/bin/bash"
        )
        install_bash_completion(
            demo, "demo", "1.0.0", version_checker=lambda _: None
        )
        assert "could not determine" in capsys.readouterr().err


class TestBashVersion:
    def test_real_bash(self) -> None:
        bash = shutil.which("bash")
        assert bash is not None
        version = _bash_version(bash)
        assert version is not None
        assert version >= (4, 4)

    def test_missing_bash(self) -> None:
        assert _bash_version("/does/not/exist") is None


class TestCallback:
    def test_resilient_parsing_returns(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from prism.completions import completions_callback

        class Context:
            resilient_parsing = True

        completions_callback(Context(), None, True)  # ty: ignore[invalid-argument-type]

    def test_version_fallback(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import importlib.metadata

        from prism.completions import completions_callback

        def missing(name: str) -> str:
            raise importlib.metadata.PackageNotFoundError(name)

        monkeypatch.setattr(
            "prism.completions.importlib.metadata.version", missing
        )
        monkeypatch.setattr(
            "prism.completions.completion_dir", lambda: tmp_path
        )

        class Context:
            resilient_parsing = False
            info_name = "demo"
            command = demo

            def exit(self) -> None:
                self.exited = True

        context = Context()
        completions_callback(context, None, True)  # ty: ignore[invalid-argument-type]
        assert context.exited
        assert "demo unknown" in (tmp_path / "demo.bash").read_text()
