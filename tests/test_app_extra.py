"""Additional app tests for branches not covered by the main suite."""

from __future__ import annotations

import importlib
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest
from textual.css.query import NoMatches
from textual.widgets import ListView

from prism.prism import FileData, FileListItem, Prism, snip


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_files(fixtures_dir: Path) -> list[FileData]:
    return [
        FileData(fixtures_dir / "test.py", 3, "def"),
        FileData(fixtures_dir / "test.py", 10, "hello"),
        FileData(fixtures_dir / "test.md", 1, "Test"),
    ]


class TestSnip:
    def test_short_string(self) -> None:
        assert snip("abc", 10) == "abc"

    def test_long_string(self) -> None:
        result = snip("abcdefghijklmnopqrstuvwxyz", 10)
        assert len(result) == 10
        assert "…" in result

    def test_tiny_length(self) -> None:
        assert snip("abcdef", 0) == "…"


class TestFileListItem:
    def test_relative_path_has_one_line(self) -> None:
        item = FileListItem(FileData(Path("test.py"), 0, ""), is_last=True)
        text = item.render()
        assert "\n" not in text.plain

    def test_absolute_path_has_two_lines(self) -> None:
        item = FileListItem(FileData(Path("/tmp/test.py"), 4, ""), is_last=True)
        text = item.render()
        assert "\n" in text.plain
        assert ":4" in text.plain


class TestWatchers:
    def test_word_wrap_early_return(self) -> None:
        app = Prism([])
        app._rendering = True
        app.watch_word_wrap(True)

    def test_view_mode_early_return(self) -> None:
        app = Prism([])
        app._rendering = True
        app.watch_view_mode("markdown")

    def test_word_wrap_without_screen(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        app = Prism([])

        def missing(*args: object, **kwargs: object) -> object:
            raise NoMatches("missing")

        monkeypatch.setattr(app, "query_one", missing)
        app.watch_word_wrap(True)

    def test_view_mode_without_screen(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        app = Prism([])

        def missing(*args: object, **kwargs: object) -> object:
            raise NoMatches("missing")

        monkeypatch.setattr(app, "query_one", missing)
        app.watch_view_mode("markdown")

    @pytest.mark.asyncio
    async def test_watchers_with_empty_list(self) -> None:
        app = Prism([])
        async with app.run_test() as pilot:
            await pilot.pause()
            app.watch_word_wrap(True)
            app.watch_view_mode("markdown")


class TestSearchBranches:
    @pytest.mark.asyncio
    async def test_search_next_without_query_opens_search(
        self, sample_files: list[FileData]
    ) -> None:
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+n")
            await pilot.pause()
            assert app.has_class("-searching")

    @pytest.mark.asyncio
    async def test_search_prev_without_query_opens_search(
        self, sample_files: list[FileData]
    ) -> None:
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+p")
            await pilot.pause()
            assert app.has_class("-searching")

    @pytest.mark.asyncio
    async def test_search_next_without_matches(
        self, sample_files: list[FileData]
    ) -> None:
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()
            app._search_query = "no-such-text"
            app._search_matches = []
            app.action_search_next()
            app.action_search_prev()

    @pytest.mark.asyncio
    async def test_clear_search_without_query(
        self, sample_files: list[FileData]
    ) -> None:
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.action_clear_search()

    @pytest.mark.asyncio
    async def test_clear_search_with_query_but_not_searching(
        self, sample_files: list[FileData]
    ) -> None:
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()
            app._search_query = "hello"
            app.action_clear_search()
            assert app._search_query == ""

    def test_compute_matches_without_query(self) -> None:
        app = Prism([])
        assert app._compute_search_matches(Path("missing")) == []

    def test_compute_matches_unreadable_file(self, tmp_path: Path) -> None:
        app = Prism([])
        app._search_query = "x"
        assert app._compute_search_matches(tmp_path / "missing") == []

    @pytest.mark.asyncio
    async def test_rendered_search_scrolls(self, fixtures_dir: Path) -> None:
        files = [FileData(fixtures_dir / "test.md", 0, "")]
        app = Prism(files)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("m")
            await pilot.pause()
            await pilot.press("slash")
            for char in "Test":
                await pilot.press(char)
            await pilot.pause()
            await pilot.press("ctrl+n")
            await pilot.pause()
            assert app._current_match_index >= 0

    @pytest.mark.asyncio
    async def test_search_index_resets(
        self, sample_files: list[FileData]
    ) -> None:
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()
            app._search_query = "hello"
            app._current_match_index = 99
            app._render_file(sample_files[1])
            assert app._current_match_index == 0


class TestScroll:
    def test_no_highlighter(self) -> None:
        app = Prism([])
        app._scroll_to_rendered_match(SimpleNamespace())  # ty: ignore[invalid-argument-type]

    def test_no_current_line(self) -> None:
        app = Prism([])
        widget = SimpleNamespace(
            _search_highlighter=SimpleNamespace(current_match_line=None)
        )
        app._scroll_to_rendered_match(widget)  # ty: ignore[invalid-argument-type]

    def test_no_container(self, monkeypatch: pytest.MonkeyPatch) -> None:
        app = Prism([])

        def missing(*args: object, **kwargs: object) -> object:
            raise NoMatches("missing")

        monkeypatch.setattr(app, "query_one", missing)
        widget = SimpleNamespace(
            _search_highlighter=SimpleNamespace(current_match_line=3)
        )
        app._scroll_to_rendered_match(widget)  # ty: ignore[invalid-argument-type]


class TestNavigation:
    @pytest.mark.asyncio
    async def test_next_and_previous_file(
        self, sample_files: list[FileData]
    ) -> None:
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()
            list_view = app.query_one("#file-list", ListView)
            assert list_view.index == 0
            await pilot.press("right")
            await pilot.pause()
            assert list_view.index == 2
            await pilot.press("left")
            await pilot.pause()
            assert list_view.index == 0

    @pytest.mark.asyncio
    async def test_next_file_without_item(self) -> None:
        app = Prism([])
        async with app.run_test() as pilot:
            await pilot.pause()
            app.action_next_file()

    @pytest.mark.asyncio
    async def test_prev_file_without_item(self) -> None:
        app = Prism([])
        async with app.run_test() as pilot:
            await pilot.pause()
            app.action_prev_file()

    @pytest.mark.asyncio
    async def test_next_file_no_later_file(
        self, sample_files: list[FileData]
    ) -> None:
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()
            list_view = app.query_one("#file-list", ListView)
            list_view.index = len(sample_files) - 1
            await pilot.pause()
            app.action_next_file()

    @pytest.mark.asyncio
    async def test_prev_file_no_earlier_file(
        self, sample_files: list[FileData]
    ) -> None:
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.action_prev_file()


class TestRenderErrors:
    @pytest.mark.asyncio
    async def test_missing_file_shows_traceback(self, tmp_path: Path) -> None:
        files = [FileData(tmp_path / "missing.py", 0, "")]
        app = Prism(files)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.title == "ERROR: FileNotFoundError"

    @pytest.mark.asyncio
    async def test_line_out_of_range_match(self, fixtures_dir: Path) -> None:
        files = [FileData(fixtures_dir / "test.py", 999, "def")]
        app = Prism(files)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.is_running

    @pytest.mark.asyncio
    async def test_select_same_file_group(
        self, sample_files: list[FileData]
    ) -> None:
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("j")
            await pilot.pause()
            assert app.is_running

    @pytest.mark.asyncio
    async def test_non_file_list_item(self) -> None:
        app = Prism([])
        async with app.run_test() as pilot:
            await pilot.pause()
            app.on_list_view_highlighted(
                SimpleNamespace(item=None, stop=lambda: None)  # ty: ignore[invalid-argument-type]
            )

    @pytest.mark.asyncio
    async def test_reentrant_highlight(
        self, sample_files: list[FileData]
    ) -> None:
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()
            item = app.query_one(FileListItem)
            app._rendering = True
            list_view = app.query_one("#file-list", ListView)
            app.on_list_view_highlighted(
                type(
                    "Event",
                    (),
                    {"item": item, "stop": lambda self: None},
                )()  # ty: ignore[invalid-argument-type]
            )
            app._rendering = False
            assert list_view is not None

    def test_refresh_without_current_data(self) -> None:
        app = Prism([])
        app._refresh_current_view()


class TestEdit:
    @pytest.mark.asyncio
    async def test_edit_emacs_with_column(
        self,
        sample_files: list[FileData],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        calls: list[list[str]] = []
        module = importlib.import_module("prism.prism")
        monkeypatch.setenv("EDITOR", "emacs -nw")
        monkeypatch.setattr(
            module.subprocess,
            "run",
            lambda args, **kwargs: calls.append(args),
        )
        monkeypatch.setattr(
            module.Prism,
            "suspend",
            lambda self: nullcontext(),
        )
        sample_files[0].column = 5
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.action_edit_file()
            await pilot.pause()
        assert calls
        assert any(part.startswith("+3:5") for part in calls[0])

    @pytest.mark.asyncio
    async def test_edit_non_emacs(
        self,
        sample_files: list[FileData],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        calls: list[list[str]] = []
        module = importlib.import_module("prism.prism")
        monkeypatch.setenv("EDITOR", "nano")
        monkeypatch.setattr(
            module.subprocess,
            "run",
            lambda args, **kwargs: calls.append(args),
        )
        monkeypatch.setattr(
            module.Prism,
            "suspend",
            lambda self: nullcontext(),
        )
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.action_edit_file()
            await pilot.pause()
        assert calls
        assert not any(part.startswith("+") for part in calls[0])

    @pytest.mark.asyncio
    async def test_edit_without_item(self) -> None:
        app = Prism([])
        async with app.run_test() as pilot:
            await pilot.pause()
            app.action_edit_file()


class TestRemainingBranches:
    def test_watchers_when_container_not_mounted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        app = Prism([])

        class Container:
            is_mounted = False

        monkeypatch.setattr(app, "query_one", lambda *args: Container())
        app.watch_word_wrap(True)
        app.watch_view_mode("markdown")

    def test_input_handlers_ignore_other_inputs(self) -> None:
        app = Prism([])
        event = SimpleNamespace(input=SimpleNamespace(id="other"), value="x")
        app.on_input_changed(event)  # ty: ignore[invalid-argument-type]
        app.on_input_submitted(event)  # ty: ignore[invalid-argument-type]

    def test_next_file_with_none_index(
        self, sample_files: list[FileData], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        app = Prism(sample_files)
        item = FileListItem(sample_files[0])
        fake_list = SimpleNamespace(
            highlighted_child=item, index=None, children=[]
        )
        monkeypatch.setattr(app, "query_one", lambda *args: fake_list)
        app.action_next_file()

    def test_prev_file_with_none_index(
        self, sample_files: list[FileData], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        app = Prism(sample_files)
        item = FileListItem(sample_files[0])
        fake_list = SimpleNamespace(
            highlighted_child=item, index=None, children=[]
        )
        monkeypatch.setattr(app, "query_one", lambda *args: fake_list)
        app.action_prev_file()

    @pytest.mark.asyncio
    async def test_prev_file_scans_same_file(
        self, sample_files: list[FileData]
    ) -> None:
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()
            list_view = app.query_one("#file-list", ListView)
            list_view.index = 1
            await pilot.pause()
            app.action_prev_file()

    @pytest.mark.asyncio
    async def test_edit_emacs_without_column(
        self,
        sample_files: list[FileData],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        calls: list[list[str]] = []
        module = importlib.import_module("prism.prism")
        monkeypatch.setenv("EDITOR", "emacs")
        monkeypatch.setattr(
            module.subprocess,
            "run",
            lambda args, **kwargs: calls.append(args),
        )
        monkeypatch.setattr(module.Prism, "suspend", lambda self: nullcontext())
        sample_files[0].column = 0
        app = Prism(sample_files)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.action_edit_file()
            await pilot.pause()
        assert any(part == "+3" for part in calls[0])
