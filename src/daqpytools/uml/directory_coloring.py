"""Color UML nodes by their top-level source directory."""

import re
from collections.abc import Sequence

from daqpytools.uml.dot_parsing import append_bracket_attrs
from daqpytools.uml.github_links import NODE_LINE_PATTERN

LEGEND_NODE_NAME = "directory_color_legend"


def get_directory_name(node_id: str, package_name: str) -> str | None:
    """Return the top-level package directory represented by ``node_id``."""
    segments = node_id.split(".")
    if segments and segments[0] == "src":
        segments = segments[1:]
    if len(segments) < 2 or segments[0] != package_name:
        return None
    return segments[1]


def assign_directory_colors(
    dot_src: str, package_name: str, palette: Sequence[str]
) -> dict[str, str]:
    """Assign palette colors to directories in first-seen order."""
    colors = {}
    if not palette:
        return colors

    for line in dot_src.splitlines():
        match = NODE_LINE_PATTERN.match(line.strip())
        if not match:
            continue
        directory = get_directory_name(match.group(1), package_name)
        if directory is not None and directory not in colors:
            colors[directory] = palette[len(colors) % len(palette)]
    return colors


def inject_directory_colors(
    dot_src: str, package_name: str, directory_colors: dict[str, str]
) -> str:
    """Apply per-directory fill colors to UML node lines."""
    out = []
    for line in dot_src.splitlines():
        match = NODE_LINE_PATTERN.match(line.strip())
        if match:
            directory = get_directory_name(match.group(1), package_name)
            color = directory_colors.get(directory or "")
            if color is not None:
                line = _replace_or_append_fillcolor(line, color)
        out.append(line)
    return "\n".join(out)


def build_directory_color_legend_dot(directory_colors: dict[str, str]) -> str:
    """Build a standalone Graphviz dot file for directory colors."""
    rows = [
        f'<TR><TD BGCOLOR="{color}">{directory}</TD></TR>'
        for directory, color in directory_colors.items()
    ]
    return "\n".join(
        [
            'digraph "directory_color_legend" {',
            '  graph [bgcolor="white" rankdir="TB" margin="0.1"];',
            f'  "{LEGEND_NODE_NAME}" [',
        "  shape=plain,",
        "  label=<",
        '    <TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="6">',
        '      <TR><TD BGCOLOR="white"><B>Directory</B></TD></TR>',
        *(f"      {row}" for row in rows),
        "    </TABLE>",
        "  >",
            "  ];",
            "}",
        ]
    )


def _replace_or_append_fillcolor(line: str, color: str) -> str:
    if re.search(r'\bfillcolor\s*=\s*"[^"]*"', line):
        return re.sub(r'\bfillcolor\s*=\s*"[^"]*"', f'fillcolor="{color}"', line)
    return append_bracket_attrs(line, f'fillcolor="{color}"')
