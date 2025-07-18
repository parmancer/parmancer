#!/usr/bin/env python3
"""
Development tool to sync README.md with the module docstring from parmancer/__init__.py.

By default, updates README.md from the module docstring.
With --check flag, only checks if they are synchronized.
"""

import argparse
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

from pydoc_markdown import PydocMarkdown
from pydoc_markdown.contrib.loaders.python import PythonLoader
from pydoc_markdown.contrib.processors.filter import FilterProcessor
from pydoc_markdown.contrib.renderers.markdown import MarkdownRenderer

README_PATH = Path(__file__).parents[1].joinpath("README.md")


def extract_module_docstring() -> str:
    """Extract the module docstring from parmancer/__init__.py as markdown."""
    pydoc = PydocMarkdown(
        loaders=[PythonLoader(search_path=["."], modules=["parmancer"])],
        processors=[
            FilterProcessor(
                expression="not hasattr(obj, 'parent') or obj.parent is None",
                do_not_filter_modules=True,
            )
        ],
        renderer=MarkdownRenderer(render_module_header=False, render_toc=False),
    )

    modules = pydoc.load_modules()
    pydoc.process(modules)

    markdown_output = io.StringIO()
    with redirect_stdout(markdown_output):
        pydoc.render(modules)

    # Add a top-level header
    readme_content = f"# Parmancer\n\n{markdown_output.getvalue()}"
    # Ensure 1 newline at end
    readme_content = readme_content.rstrip("\n") + "\n"
    return readme_content


def check_sync() -> bool:
    """Check if README.md is synchronized with module docstring."""
    expected_readme_content = extract_module_docstring()
    readme_content = README_PATH.read_text()

    return expected_readme_content == readme_content


def sync_readme() -> None:
    """Update README.md from module docstring."""
    README_PATH.write_text(extract_module_docstring())
    print("README.md updated from module docstring")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Sync README.md with module docstring")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if README.md is synchronized (don't update)",
    )
    args = parser.parse_args()

    if args.check:
        if check_sync():
            print("README.md is synchronized with module docstring")
        else:
            print(
                "Error: README.md is not synchronized with module docstring",
                file=sys.stderr,
            )
            print(
                "Run tools/sync_readme.py without --check to update README.md",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        sync_readme()


if __name__ == "__main__":
    main()
