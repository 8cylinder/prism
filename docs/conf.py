"""Sphinx configuration for the prism man page."""

from importlib.metadata import version as pkg_version

project = "prism"
author = "Sheldon McGrandle"
release = pkg_version("prism")

extensions = ["myst_parser", "sphinx_click"]
source_suffix = {".rst": "restructuredtext", ".md": "markdown"}

root_doc = "cli"
exclude_patterns = ["_build"]

# Click help text is plain text, so characters such as * in examples are not
# intended as reStructuredText inline markup.
suppress_warnings = ["docutils"]

man_pages = [
    (
        "cli",
        "prism",
        "View files found with CLI search tools",
        ["Sheldon McGrandle"],
        1,
    ),
]
