"""Regression test: theme helpers must not pass font and **kw twice."""
import ast
from pathlib import Path


def test_theme_helpers_do_not_duplicate_font_keyword():
    source = Path(__file__).parents[1] / "ui" / "theme.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        explicit_font = any(keyword.arg == "font" for keyword in node.keywords)
        expanded_kwargs = any(keyword.arg is None for keyword in node.keywords)
        if explicit_font and expanded_kwargs:
            # Calls using **kw must apply font defaults inside kw, not also
            # pass font as a separate keyword argument.
            assert not any(keyword.arg == "font" for keyword in node.keywords)
