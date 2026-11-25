"""Direct tests for the file renderers."""

from __future__ import annotations

import csv
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from rich.console import Console
from rich.markdown import Markdown
from rich.style import Style
from rich.text import Text as RichText
from textual.css.query import NoMatches
from textual.widgets import Static

from prism.renderers import (
    HTMLRenderer,
    JSONRenderer,
    MarkdownRenderer,
    OrgRenderer,
    SearchHighlighter,
    SourceCodeRenderer,
    TableRenderer,
    _highlight_cell,
    _make_search_styles,
    _set_highlighter,
)


class FakeApp:
    size = SimpleNamespace(height=30)


class FakeRemovable:
    def __init__(self) -> None:
        self.removed = False

    def remove(self) -> None:
        self.removed = True


class FakeContainer:
    def __init__(self, existing: object | None = None) -> None:
        self.existing = existing
        self.children: list[Any] = [FakeRemovable()]
        self.app = FakeApp()
        self.mounted: list[Any] = []

    def query_one(self, selector: object, expect_type: object = None) -> Any:  # noqa: ANN401
        if self.existing is None:
            raise NoMatches("missing")
        return self.existing

    def mount(self, widget: Any) -> None:  # noqa: ANN401
        self.children.append(widget)
        self.mounted.append(widget)


@pytest.fixture(autouse=True)
def stub_static_update(monkeypatch: pytest.MonkeyPatch) -> None:
    def update(self: Static, content: object) -> None:
        self.stored = content  # ty: ignore[missing-attribute]

    monkeypatch.setattr(Static, "update", update)


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


def render_with(
    renderer: Any,  # noqa: ANN401
    container: FakeContainer,
    path: Path,
    **kwargs: Any,  # noqa: ANN401
) -> tuple[Any, int]:
    return renderer.render(container=container, file_path=path, **kwargs)


class TestMarkdownRenderer:
    def test_creates_widget(self, fixtures_dir: Path) -> None:
        container = FakeContainer()
        widget, scroll = render_with(
            MarkdownRenderer, container, fixtures_dir / "test.md"
        )
        assert isinstance(widget, Static)
        assert container.mounted == [widget]
        assert scroll == 0

    def test_reuses_widget(self, fixtures_dir: Path) -> None:
        existing = Static(id="code")
        container = FakeContainer(existing=existing)
        widget, _ = render_with(
            MarkdownRenderer, container, fixtures_dir / "test.md"
        )
        assert widget is existing
        assert container.mounted == []

    def test_search_highlighter_attached(self, fixtures_dir: Path) -> None:
        container = FakeContainer()
        widget, _ = render_with(
            MarkdownRenderer,
            container,
            fixtures_dir / "test.md",
            search_query="Test",
        )
        assert isinstance(widget._search_highlighter, SearchHighlighter)

    def test_no_search_attaches_none(self, fixtures_dir: Path) -> None:
        container = FakeContainer()
        widget, _ = render_with(
            MarkdownRenderer, container, fixtures_dir / "test.md"
        )
        assert widget._search_highlighter is None


class TestHtmlRenderer:
    def test_creates_widget(self, fixtures_dir: Path) -> None:
        container = FakeContainer()
        widget, _ = render_with(
            HTMLRenderer, container, fixtures_dir / "test.html"
        )
        assert isinstance(widget, Static)
        assert container.mounted

    def test_reuses_widget(self, fixtures_dir: Path) -> None:
        existing = Static(id="code")
        container = FakeContainer(existing=existing)
        widget, _ = render_with(
            HTMLRenderer, container, fixtures_dir / "test.html"
        )
        assert widget is existing


class TestJsonRenderer:
    def test_creates_widget(self, fixtures_dir: Path) -> None:
        container = FakeContainer()
        widget, _ = render_with(
            JSONRenderer, container, fixtures_dir / "test.json"
        )
        assert isinstance(widget, Static)
        assert container.mounted

    def test_reuses_widget(self, fixtures_dir: Path) -> None:
        existing = Static(id="code")
        container = FakeContainer(existing=existing)
        widget, _ = render_with(
            JSONRenderer, container, fixtures_dir / "test.json"
        )
        assert widget is existing

    def test_invalid_json_creates_error_view(self, fixtures_dir: Path) -> None:
        container = FakeContainer()
        widget, _ = render_with(
            JSONRenderer, container, fixtures_dir / "invalid.json"
        )
        assert isinstance(widget, Static)
        assert container.mounted

    def test_invalid_json_reuses_error_view(self, fixtures_dir: Path) -> None:
        existing = Static(id="code")
        container = FakeContainer(existing=existing)
        widget, _ = render_with(
            JSONRenderer, container, fixtures_dir / "invalid.json"
        )
        assert widget is existing


class FakeTable:
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.columns: list[Any] = []
        self.rows: list[Any] = []
        self.cleared = False

    def clear(self) -> None:
        self.cleared = True

    def add_columns(self, *columns: Any) -> None:  # noqa: ANN401
        self.columns.extend(columns)

    def add_row(self, *cells: Any) -> None:  # noqa: ANN401
        self.rows.append(cells)

    @property
    def row_count(self) -> int:
        return len(self.rows)


class TestTableRenderer:
    @pytest.fixture(autouse=True)
    def fake_table(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("prism.renderers.DataTable", FakeTable)

    def test_creates_table(self, fixtures_dir: Path) -> None:
        container = FakeContainer()
        table, _ = render_with(
            TableRenderer, container, fixtures_dir / "test.csv"
        )
        assert table in container.mounted
        assert table.row_count > 0

    def test_reuses_table(self, fixtures_dir: Path) -> None:
        table = FakeTable()
        container = FakeContainer(existing=table)
        result, _ = render_with(
            TableRenderer, container, fixtures_dir / "test.csv"
        )
        assert result is table

    def test_tsv_delimiter(self, fixtures_dir: Path) -> None:
        container = FakeContainer()
        table, _ = render_with(
            TableRenderer, container, fixtures_dir / "test.tsv"
        )
        assert table.row_count > 0

    def test_comments_are_ignored(self, fixtures_dir: Path) -> None:
        container = FakeContainer()
        table, _ = render_with(
            TableRenderer,
            container,
            fixtures_dir / "test_with_comments.csv",
        )
        assert table.row_count > 0

    def test_empty_after_comments(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.csv"
        path.write_text("# comment only\n")
        container = FakeContainer()
        table, _ = render_with(TableRenderer, container, path)
        assert table.row_count == 0

    def test_search_highlights_cells(self, fixtures_dir: Path) -> None:
        container = FakeContainer()
        table, _ = render_with(
            TableRenderer,
            container,
            fixtures_dir / "test.csv",
            search_query="a",
            search_current_index=0,
        )
        assert table.row_count > 0

    def test_csv_error_creates_view(
        self, fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def broken_reader(*args: object, **kwargs: object) -> object:
            raise csv.Error("bad csv")

        monkeypatch.setattr("prism.renderers.csv.reader", broken_reader)
        container = FakeContainer()
        widget, _ = render_with(
            TableRenderer, container, fixtures_dir / "test.csv"
        )
        assert isinstance(widget, Static)
        assert container.mounted

    def test_csv_error_reuses_view(
        self, fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def broken_reader(*args: object, **kwargs: object) -> object:
            raise csv.Error("bad csv")

        monkeypatch.setattr("prism.renderers.csv.reader", broken_reader)
        existing = Static(id="code")
        container = FakeContainer(existing=existing)
        widget, _ = render_with(
            TableRenderer, container, fixtures_dir / "test.csv"
        )
        assert widget is existing


class TestOrgRenderer:
    def test_falls_back_without_emacs(
        self, fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("shutil.which", lambda _: None)
        container = FakeContainer()
        widget, _ = render_with(
            OrgRenderer, container, fixtures_dir / "test.org"
        )
        assert isinstance(widget, Static)

    def test_successful_export(
        self, fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/emacs")
        stdout = (
            '<a id="anchor"></a>\n# Title\n\n'
            "<table><tr><td>A</td><td>B</td></tr></table>\n"
        )
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *args, **kwargs: SimpleNamespace(
                returncode=0, stdout=stdout.encode(), stderr=b""
            ),
        )
        container = FakeContainer()
        widget, _ = render_with(
            OrgRenderer, container, fixtures_dir / "test.org"
        )
        assert isinstance(widget, Static)
        assert container.mounted

    def test_failed_export_with_stderr(
        self, fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/emacs")
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *args, **kwargs: SimpleNamespace(
                returncode=1, stdout=b"", stderr=b"boom"
            ),
        )
        container = FakeContainer()
        widget, _ = render_with(
            OrgRenderer, container, fixtures_dir / "test.org"
        )
        assert isinstance(widget, Static)
        assert container.mounted

    def test_failed_export_without_stderr_reuses(
        self, fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/emacs")
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *args, **kwargs: SimpleNamespace(
                returncode=1, stdout=b"", stderr=b""
            ),
        )
        existing = Static(id="code")
        container = FakeContainer(existing=existing)
        widget, _ = render_with(
            OrgRenderer, container, fixtures_dir / "test.org"
        )
        assert widget is existing

    def test_success_reuses_widget(
        self, fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/emacs")
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *args, **kwargs: SimpleNamespace(
                returncode=0, stdout=b"# Title\n", stderr=b""
            ),
        )
        existing = Static(id="code")
        container = FakeContainer(existing=existing)
        widget, _ = render_with(
            OrgRenderer, container, fixtures_dir / "test.org"
        )
        assert widget is existing


class TestSourceRenderer:
    def test_creates_widget(self, fixtures_dir: Path) -> None:
        container = FakeContainer()
        widget, scroll = render_with(
            SourceCodeRenderer, container, fixtures_dir / "test.py"
        )
        assert isinstance(widget, Static)
        assert container.mounted
        assert isinstance(scroll, int)

    def test_reuses_widget(self, fixtures_dir: Path) -> None:
        existing = Static(id="code")
        container = FakeContainer(existing=existing)
        widget, _ = render_with(
            SourceCodeRenderer, container, fixtures_dir / "test.py"
        )
        assert widget is existing

    def test_other_matches(self, fixtures_dir: Path) -> None:
        container = FakeContainer()
        widget, _ = render_with(
            SourceCodeRenderer,
            container,
            fixtures_dir / "test.py",
            other_matches=[
                (1, "Test"),
                (2, "not found"),
                (0, "ignored"),
                (999, "ignored"),
                (3, ""),
            ],
        )
        assert isinstance(widget, Static)

    def test_current_match_and_search(self, fixtures_dir: Path) -> None:
        container = FakeContainer()
        widget, _ = render_with(
            SourceCodeRenderer,
            container,
            fixtures_dir / "test.py",
            line_num=4,
            match_string="def",
            search_matches=[(1, 0, 2), (2, 0, 2), (999, 0, 1)],
            search_current_index=1,
        )
        assert isinstance(widget, Static)

    def test_match_string_not_found(self, fixtures_dir: Path) -> None:
        container = FakeContainer()
        render_with(
            SourceCodeRenderer,
            container,
            fixtures_dir / "test.py",
            line_num=1,
            match_string="zzzz",
        )

    def test_binary_file_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "binary.bin"
        path.write_bytes(b"\xff\xfe\x00")
        container = FakeContainer()
        with pytest.raises(UnicodeDecodeError):
            render_with(SourceCodeRenderer, container, path)


def _render_highlighter(
    console: Console, highlighter: SearchHighlighter
) -> RichText:
    text = RichText()
    for segment in console.render(highlighter, console.options):
        text.append(segment.text, segment.style)
    return text


class TestCanRender:
    @pytest.mark.parametrize(
        ("renderer", "suffix", "mode", "expected"),
        [
            (MarkdownRenderer, ".md", "markdown", True),
            (MarkdownRenderer, ".markdown", "markdown", True),
            (MarkdownRenderer, ".txt", "markdown", False),
            (MarkdownRenderer, ".md", "source", False),
            (HTMLRenderer, ".html", "markdown", True),
            (HTMLRenderer, ".htm", "markdown", True),
            (HTMLRenderer, ".twig", "markdown", True),
            (HTMLRenderer, ".txt", "markdown", False),
            (JSONRenderer, ".json", "markdown", True),
            (JSONRenderer, ".json", "source", False),
            (TableRenderer, ".csv", "markdown", True),
            (TableRenderer, ".tsv", "markdown", True),
            (TableRenderer, ".txt", "markdown", False),
            (OrgRenderer, ".org", "markdown", True),
            (OrgRenderer, ".org", "source", False),
            (SourceCodeRenderer, ".py", "source", True),
            (SourceCodeRenderer, ".py", "markdown", True),
        ],
    )
    def test_can_render(
        self,
        renderer: Any,  # noqa: ANN401
        suffix: str,
        mode: str,
        expected: bool,
    ) -> None:
        assert renderer.can_render(Path("file" + suffix), mode) is expected


class TestHighlighter:
    def test_empty_query_yields_plain_text(self) -> None:
        highlighter = SearchHighlighter(
            Markdown("# Title"),
            "",
            Style(),
            Style(),
        )
        console = Console()
        text = _render_highlighter(console, highlighter)
        assert "Title" in text.plain

    def test_zero_length_match_is_skipped(self) -> None:
        highlighter = SearchHighlighter(
            Markdown("# Title"),
            "^",
            Style(),
            Style(),
        )
        console = Console()
        text = _render_highlighter(console, highlighter)
        assert "Title" in text.plain

    def test_apply_search_highlight_without_query(self) -> None:
        from prism.renderers import apply_search_highlight

        markdown = Markdown("# Title")
        assert (
            apply_search_highlight(markdown, "", 0, "", "", "", "") is markdown
        )

    def test_set_highlighter_none(self) -> None:
        widget = Static()
        _set_highlighter(widget, Markdown("# Title"))
        assert widget._search_highlighter is None  # ty: ignore[missing-attribute]

    def test_highlight_cell_without_pattern(self) -> None:
        match, current = _make_search_styles("red", "blue", "white", "black")
        cell, counter = _highlight_cell("abc", None, match, current, 0, 5)
        assert counter == 5
        assert cell.plain == "abc"
