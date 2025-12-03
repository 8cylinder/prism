# Prism Tests

This directory contains tests for the Prism TUI application.

## Test Structure

- `test_cli.py` - Tests for CLI argument parsing and input handling
- `test_app.py` - Tests for the main Prism application functionality
- `test_rendering.py` - Tests for different rendering modes (markdown, HTML, CSV/TSV)
- `fixtures/` - Test fixture files for different file types

## Running Tests

Run all tests:
```bash
uv run pytest
```

Run specific test file:
```bash
uv run pytest tests/test_cli.py
```

Run specific test:
```bash
uv run pytest tests/test_cli.py::TestFilenameParsing::test_parse_plain_path
```

Run with verbose output:
```bash
uv run pytest -v
```

Run and show print statements:
```bash
uv run pytest -s
```

## Test Coverage

### CLI Tests (`test_cli.py`)
- ✅ Plain file path parsing
- ✅ File path with line number
- ✅ File path with line number and match string
- ✅ File path with match string only
- ✅ Relative paths
- ✅ Match strings containing colons

### App Tests (`test_app.py`)
- ✅ App startup
- ✅ File list population
- ✅ File list state toggling (narrow/wide/hidden)
- ✅ View mode toggling (source/markdown)
- ✅ Word wrap toggling
- ✅ Navigation (next/previous item)
- ✅ FileListItem creation
- ✅ FileData dataclass

### Rendering Tests (`test_rendering.py`)

#### Markdown Rendering
- ✅ Markdown file detection (.md, .markdown)
- ✅ Markdown rendering when view mode is active
- ✅ Source code display when view mode is off

#### HTML Rendering
- ✅ HTML file detection (.html, .htm, .twig)
- ✅ HTML to Markdown conversion using html2text
- ✅ Source code display when view mode is off

#### CSV/TSV Rendering (Future)
- ⏭️ CSV file detection (.csv)
- ⏭️ CSV rendering as DataTable
- ⏭️ TSV file detection (.tsv)
- ⏭️ TSV tab delimiter handling

#### Source Code Rendering
- ✅ Python syntax highlighting

## Adding New Tests

When adding new rendering modes or features:

1. Add test fixture files to `fixtures/`
2. Create test class in `test_rendering.py`
3. Use `@pytest.mark.skip` for future features
4. Remove skip marker when feature is implemented

Example:
```python
class TestNewRendering:
    """Test new file type rendering."""

    @pytest.mark.skip(reason="Feature not yet implemented")
    @pytest.mark.asyncio
    async def test_new_rendering(self, fixtures_dir):
        """Test that new file type is rendered."""
        # Test implementation
        pass
```
