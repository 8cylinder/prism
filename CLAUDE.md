# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when
working with code in this repository.

## Project Overview

Prism is a TUI (Terminal User Interface) application for viewing and
navigating files found via CLI search tools (find, rg, grep). It
displays search results in a split-pane interface: a file list on the
left and syntax-highlighted file contents on the right.

**Key dependencies:**
- `textual` - TUI framework (version 1.0.0+)
  - `textual reference` - https://textual.textualize.io/reference/
  - `textual widget docs` - https://textual.textualize.io/widget_gallery/
- `click` - CLI argument parsing
- `rich` - Syntax highlighting and terminal formatting


## Coding standards
- All code must have black run on it.

## Development Commands

```bash
# Setup environment
uv sync

# Run the application
uv run prism -h

# Development mode with live reload
uv run textual run --dev prism:prism -h

# Start textual console for debugging (in separate terminal)
uv run textual console -x event

# Code formatting
uv run black src/

# Type checking
uv run mypy src/
```

## Architecture

### Entry Point Flow
1. `src/prism/__init__.py` - Exports the main `prism` function from
   cli module
2. `src/prism/cli.py` - CLI interface using Click, handles
   stdin/argument parsing
3. `src/prism/prism.py` - Textual app implementation with UI
   components

### Input Parsing (`cli.py`)
The application accepts input in two ways:
- **Piped stdin**: `rg pattern | prism` (reopens stdin from `/dev/tty`
  for Textual at line 113)
- **Command arguments**: `prism file1.py file2.py`

Supported input formats (parsed in `parse_filename()`):
- Plain paths: `/path/to/file`
- With match string: `/path/to/file:match_string`
- With line number: `/path/to/file:123:match_string`

### Data Model
`FileData` dataclass (prism.py:22-26) represents each file entry:
- `file: Path` - File path
- `line_num: int` - Line number to highlight (0 if none)
- `match_string: str` - Text to highlight within the line

### UI Components (`prism.py`)

**Main App: `Prism(App)`** (line 62)
- Two-pane layout: `ListView` (file list) + `VerticalScroll` (code
  viewer)
- Reactive variable `show_files` toggles file list visibility
- Key bindings: `l` (toggle light/dark), `f` (toggle file list), `e`
  (edit file), `q` (quit)

**Custom Widget: `FileListItem(ListItem)`** (line 29)
- Displays file path with parent directory styling
- Shows line number if available
- Stores `FileData` for access on selection

**Event Handling:**
- `on_list_view_highlighted()` (line 110): Updates code view when file
  selected
  - Loads syntax highlighting via `rich.syntax.Syntax`
  - Highlights the specified line
  - Uses regex to find and highlight the match string within the line
    (line 126-130)
  - Auto-scrolls to position highlighted line at 1/3 screen height

**Styling:**
- Uses Textual CSS (TCSS) in `src/prism/css/prism.tcss`
- File list visibility controlled by `.-show-files` class modifier
  (tcss:56-59)
- Dark theme: `github-dark` for syntax highlighting

### Editor Integration
The `action_edit_file()` (line 155) currently hardcodes `emacs -nw
-q`. To respect user's `$EDITOR`, replace line 166 with:

```python
editor = os.getenv("EDITOR", "nano")
os.system(f"{editor} {item.file}")
```

## Common Patterns

**Testing input parsing:**
Use `--debug-data` flag to see parsed FileData without launching TUI:
```bash
echo "src/prism/cli.py:42:some text" | uv run prism --debug-data
```

**Null-terminated input:**
For filenames with spaces or special characters:
```bash
find . -name "*.py" -print0 | prism --null
```

## Project Structure
```
src/prism/
├── __init__.py          # Package entry point
├── cli.py               # Click CLI, input parsing
├── prism.py             # Textual app and UI widgets
└── css/
    └── prism.tcss       # Textual CSS styling
```
