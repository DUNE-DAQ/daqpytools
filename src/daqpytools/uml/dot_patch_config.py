"""Configuration and helpers for .dot patching rules.

This module intentionally separates:
1) Static transformation configuration (regex substitutions + style builders)
2) Runtime execution (performed in style_pyreverse.py)

The goal is to keep patch_dot and fix_edges small and orchestration-focused,
while this file remains the single place to edit transformation behavior.

Substitution semantics
----------------------
Each substitution is a tuple: (pattern, replacement), applied in order.

Regex example notation used below:
    before -> after
"""


Substitution = tuple[str, str]

STRIP_NODE_ATTRS: list[Substitution] = [
    # Remove pyreverse-injected node colors/styles so global defaults can win.
    # Example:
    #   [fontcolor="red", color="blue", style="filled", fillcolor="gray"]
    #   -> [] (then cleaned by CLEANUP_ATTR_LISTS)
    (r',?\s*\bfontcolor\s*=\s*"[^"]*"', ''),
    (r',?\s*\bcolor\s*=\s*"[^"]*"', ''),
    (r',?\s*\bstyle\s*=\s*"[^"]*"', ''),
    (r',?\s*\bfillcolor\s*=\s*"[^"]*"', ''),
]

CLEANUP_ATTR_LISTS: list[Substitution] = [
    # Normalize malformed attribute lists produced by removals.
    # Examples:
    #   []        -> ""
    #   [, a=b]   -> [a=b]
    #   [a=b, ]   -> [a=b]
    #   [a=b,,c]  -> [a=b, c]
    (r'\[\s*\]', ''),
    (r'\[\s*,', '['),
    (r',\s*\]', ']'),
    (r',\s*,', ', '),
]

STRIP_EDGE_ATTRS: list[Substitution] = [
    # Remove edge styling so we can deterministically re-apply UML arrows/colors.
    # Example:
    #   A -> B [arrowhead="vee", style="dashed", color="red"]
    #   -> A -> B [] (then cleaned by CLEANUP_EDGE_ATTRS)
    (r',?\s*arrowhead\s*=\s*"?[^",\]\s]+"?', ''),
    (r',?\s*\bstyle\s*=\s*"[^"]*"', ''),
    (r',?\s*\bcolor\s*=\s*"[^"]*"', ''),
]

CLEANUP_EDGE_ATTRS: list[Substitution] = [
    # Same bracket normalization as node cleanup, scoped to edge lines.
    # Example:
    #   A -> B [, label="x", ] -> A -> B [label="x"]
    (r'\[\s*,', '['),
    (r',\s*\]', ']'),
    (r'\[\s*\]', ''),
]

PATCH_DOT_SUBSTITUTION_PIPELINE: tuple[list[Substitution], ...] = (
    # Dot-level phases run by patch_dot in this exact order.
    STRIP_NODE_ATTRS,
    CLEANUP_ATTR_LISTS,
)

EDGE_SUBSTITUTION_PIPELINE: tuple[list[Substitution], ...] = (
    # Per-edge phases run by fix_edges in this exact order.
    STRIP_EDGE_ATTRS,
    CLEANUP_EDGE_ATTRS,
)

DIGRAPH_OPEN_PATTERN = r'digraph\s+\S+\s*\{'

DEFAULT_BLOCK_BUILDERS = (
    # Build graph/node/edge default attribute blocks inserted after
    # DIGRAPH_OPEN_PATTERN. Using builders keeps this declarative and easy
    # to tweak without touching execution logic.
    lambda style: (
        'graph ['
        f'bgcolor="{style["bg_color"]}" '
        f'fontname="{style["class_font"]}" '
        f'pad="{style["pad"]}" nodesep="{style["nodesep"]}" ranksep="{style["ranksep"]}" '
        f'rankdir="{style["rankdir"]}"'
        '];'
    ),
    lambda style: (
        'node ['
        'shape=record '
        'style="filled" '
        f'fillcolor="{style["class_fill"]}" '
        f'color="{style["class_stroke"]}" '
        f'fontname="{style["class_font"]}" '
        f'fontsize={style["class_fontsize"]}'
        '];'
    ),
    lambda style: (
        'edge ['
        f'fontname="{style["class_font"]}" '
        'fontsize="9" '
        f'color="{style["inherit_color"]}"'
        '];'
    ),
)

EDGE_ATTR_BUILDERS = {
    # True  -> dependency edge (dashed, open arrow)
    # False -> inheritance edge (solid, empty/hollow triangle)
    True: lambda style: (
        'arrowhead="open" '
        'style="dashed" '
        f'color="{style["uses_color"]}"'
    ),
    False: lambda style: (
        'arrowhead="empty" '
        'style="solid" '
        f'color="{style["inherit_color"]}"'
    ),
}


def build_defaults_block(style: dict[str, str]) -> str:
    """Return formatted graph/node/edge defaults block for a digraph body.

    Example output shape:
      graph [...]
      node [...]
      edge [...]
    """
    lines = [builder(style) for builder in DEFAULT_BLOCK_BUILDERS]
    return "\n  " + "\n  ".join(lines) + "\n"


def build_edge_attrs(style: dict[str, str], is_dashed: bool) -> str:
    """Return edge attribute string chosen by edge semantic type.

    is_dashed=True  -> dependency/uses style
    is_dashed=False -> inheritance style
    """
    return EDGE_ATTR_BUILDERS[is_dashed](style)
