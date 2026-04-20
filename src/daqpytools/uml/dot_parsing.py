#!/usr/bin/env python3

import re
from daqpytools.uml.utils import strip_typehints
from daqpytools.uml.dot_patch_config import (
    PATCH_DOT_SUBSTITUTION_PIPELINE,
    EDGE_SUBSTITUTION_PIPELINE,
    DIGRAPH_OPEN_PATTERN,
    build_defaults_block,
    build_edge_attrs,
)


def apply_substitutions(text: str, substitutions: list[tuple[str, str]]) -> str:
    """Apply regex substitutions in order."""
    for pattern, replacement in substitutions:
        text = re.sub(pattern, replacement, text)
    return text


def patch_dot(dot_src, style, concise=False):
    """Rewrite .dot source to apply a clean UML style."""

    for substitutions in PATCH_DOT_SUBSTITUTION_PIPELINE:
        dot_src = apply_substitutions(dot_src, substitutions)

    if concise:
        dot_src = strip_typehints(dot_src)

    defaults_block = build_defaults_block(style)

    def insert_defaults(m):
        return m.group(0) + defaults_block

    dot_src = re.sub(DIGRAPH_OPEN_PATTERN, insert_defaults, dot_src, count=1)

    dot_src = fix_edges(dot_src, style)

    return dot_src


def fix_edges(dot_src, style):
    """
    Restyle edges line-by-line:
      dashed → dependency/uses:  arrowhead=open,  style=dashed
      solid  → inheritance:      arrowhead=empty, style=solid (hollow triangle)
    """
    lines = dot_src.splitlines()
    out = []
    for line in lines:
        if '->' not in line:
            out.append(line)
            continue

        is_dashed = 'dashed' in line

        for substitutions in EDGE_SUBSTITUTION_PIPELINE:
            line = apply_substitutions(line, substitutions)
        new_attrs = build_edge_attrs(style, is_dashed)

        if '[' in line:
            line = re.sub(
                r'\[([^\]]*)\]',
                lambda m: '[' + (m.group(1).strip().rstrip(',') + ', ' if m.group(1).strip() else '') + new_attrs + ']',
                line
            )
        else:
            line = re.sub(r';?\s*$', ' [' + new_attrs + '];', line.rstrip())

        out.append(line)
    return '\n'.join(out)
