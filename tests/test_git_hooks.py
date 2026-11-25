"""Tests for the gitleaks pre-commit hook."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

HOOK = Path(__file__).parent.parent / ".githooks" / "pre-commit"


def run_hook(
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(HOOK)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def write_stub(bin_dir: Path, version: str, exit_code: int = 0) -> Path:
    stub = bin_dir / "gitleaks"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "$1" = "version" ]; then\n'
        f'    echo "{version}"\n'
        "    exit 0\n"
        "fi\n"
        'printf "%s\\n" "$@" > "$STUB_LOG"\n'
        f"exit {exit_code}\n"
    )
    stub.chmod(0o755)
    return stub


def base_env(bin_dir: Path, tmp_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:/usr/bin:/bin"
    env["STUB_LOG"] = str(tmp_path / "args.txt")
    return env


class TestGitHook:
    def test_script_parses(self) -> None:
        result = subprocess.run(
            ["bash", "-n", str(HOOK)],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

    def test_missing_gitleaks(self, tmp_path: Path) -> None:
        env = dict(os.environ)
        env["PATH"] = "/usr/bin:/bin"
        result = run_hook(env)
        assert result.returncode == 1
        assert "gitleaks is not installed" in result.stderr
        assert "gitleaks#installing" in result.stderr

    def test_old_gitleaks(self, tmp_path: Path) -> None:
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        write_stub(bin_dir, "8.16.0")
        result = run_hook(base_env(bin_dir, tmp_path))
        assert result.returncode == 1
        assert "8.19" in result.stderr
        assert "found: 8.16.0" in result.stderr

    def test_supported_gitleaks(self, tmp_path: Path) -> None:
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        write_stub(bin_dir, "8.30.1")
        env = base_env(bin_dir, tmp_path)
        result = run_hook(env)
        assert result.returncode == 0
        args = Path(env["STUB_LOG"]).read_text().splitlines()
        assert args == [
            "git",
            "--staged",
            "--redact",
            "--no-banner",
            "--verbose",
        ]

    def test_gitleaks_failure(self, tmp_path: Path) -> None:
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        write_stub(bin_dir, "8.30.1", exit_code=1)
        result = run_hook(base_env(bin_dir, tmp_path))
        assert result.returncode == 1

    def test_unknown_version(self, tmp_path: Path) -> None:
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        write_stub(bin_dir, "")
        result = run_hook(base_env(bin_dir, tmp_path))
        assert result.returncode == 1
        assert "found: unknown" in result.stderr
