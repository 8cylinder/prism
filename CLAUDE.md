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
- All code must have black run on it
- Type checking with mypy must pass
- Follow Textual best practices: use CSS for styling, not hardcoded colors in Python

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

### Configuration Constants (prism.py:19-25)
The following constants at the top of `prism.py` control styling and behavior:
- `DEFAULT_SYNTAX_THEME` - Theme for syntax highlighting ("github-dark")
- `DEFAULT_TRACEBACK_THEME` - Theme for error tracebacks
- `SCROLL_OFFSET_RATIO` - Controls scroll position when highlighting a line (3 = 1/3 screen height)
- `MATCH_HIGHLIGHT_COLOR`, `MATCH_HIGHLIGHT_BGCOLOR` - Colors for highlighting matched text

### Data Model
`FileData` dataclass (prism.py:28-31) represents each file entry:
- `file: Path` - File path
- `line_num: int` - Line number to highlight (0 if none)
- `match_string: str` - Text to highlight within the line

### UI Components (`prism.py`)

**Main App: `Prism(App[None])`** (line 56)
- Two-pane layout: `ListView` (file list) + `VerticalScroll` (code viewer)
- Reactive variable `file_list_state` cycles through three width states:
  - `"narrow"` - 20% width
  - `"wide"` - 80% width
  - `"hidden"` - 0% width (invisible)
- Key bindings: `l` (toggle light/dark), `f` (toggle file list width), `e` (edit file), `q` (quit)

**Custom Widget: `FileListItem(ListItem)`** (line 34)
- Uses CSS classes for styling instead of hardcoded Rich markup:
  - `.file-parent` - Parent directory path
  - `.file-name` - Filename
  - `.line-number` - Line number indicator
- Odd/even classes are properly applied for alternating row colors
- Stores `FileData` for access on selection

**Event Handling:**
- `on_list_view_highlighted()` (line 110): Updates code view when file selected
  - Type-checks event.item to ensure it's a FileListItem
  - Loads syntax highlighting via `rich.syntax.Syntax`
  - Highlights the specified line
  - Uses regex to find and highlight the match string within the line
  - Auto-scrolls to position highlighted line based on `SCROLL_OFFSET_RATIO`
  - Error handling: catches `OSError` (file read errors), `UnicodeDecodeError` (binary files), `IndexError` (invalid line numbers)

**Styling:**
- Uses Textual CSS (TCSS) in `src/prism/css/prism.tcss`
- File list width states controlled by classes: `.-files-narrow`, `.-files-wide`, `.-files-hidden`
- Alternating row colors via `FileListItem.odd` and `FileListItem.even` classes
- All colors use Textual theme variables (`$primary-background-darken-1`, `$accent`, `$success`, etc.)
- Syntax theme controlled by `DEFAULT_SYNTAX_THEME` constant

### Editor Integration
The `action_edit_file()` (line 166) uses `subprocess.run()` for security:
- Respects `$EDITOR` environment variable (defaults to "nano")
- Uses `shlex.split()` to safely parse editor commands with arguments
- Type-checks to ensure the selected item is a `FileListItem`
- Suspends the TUI while editing, then resumes

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
