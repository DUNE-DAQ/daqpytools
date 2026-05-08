#!/usr/bin/env python3
"""Helpers for transforming pyreverse dot output."""

import re
from collections.abc import Sequence
from functools import partial

from daqpytools.uml.dot_patch_config import (
    DIGRAPH_OPEN_PATTERN,
    EDGE_SUBSTITUTION_PIPELINE,
    PATCH_DOT_SUBSTITUTION_PIPELINE,
    build_defaults_block,
    build_edge_attrs,
)
from daqpytools.uml.utils import strip_typehints


def apply_substitutions(text: str, substitutions: Sequence[tuple[str, str]]) -> str:
    """Apply regex substitutions in order."""
    for pattern, replacement in substitutions:
        text = re.sub(pattern, replacement, text)
    return text


def _insert_defaults(match: re.Match[str], defaults_block: str) -> str:
    return match.group(0) + defaults_block


def patch_dot(dot_src: str, style: dict[str, str], concise: bool = False) -> str:
    """Rewrite dot source to apply a clean UML style."""
    for substitutions in PATCH_DOT_SUBSTITUTION_PIPELINE:
        dot_src = apply_substitutions(dot_src, substitutions)

    if concise:
        dot_src = strip_typehints(dot_src)

    defaults_block = build_defaults_block(style)
    return fix_edges(
        re.sub(
            DIGRAPH_OPEN_PATTERN,
            partial(_insert_defaults, defaults_block=defaults_block),
            dot_src,
            count=1,
        ),
        style,
    )


def _append_edge_attrs(line: str, new_attrs: str) -> str:
    if "[" in line:
        return re.sub(
            r"\[([^\]]*)\]",
            lambda match: (
                "["
                + (
                    match.group(1).strip().rstrip(",") + ", "
                    if match.group(1).strip()
                    else ""
                )
                + new_attrs
                + "]"
            ),
            line,
        )
    return re.sub(r";?\s*$", f" [{new_attrs}];", line.rstrip())


def fix_edges(dot_src: str, style: dict[str, str]) -> str:
    """Restyle edges line by line.
    dashed → dependency/uses:  arrowhead=open,  style=dashed
    solid  → inheritance:      arrowhead=empty, style=solid (hollow triangle).
    """
    lines = dot_src.splitlines()
    out = []
    for line in lines:
        if "->" not in line:
            out.append(line)
            continue

        is_dashed = "dashed" in line

        for substitutions in EDGE_SUBSTITUTION_PIPELINE:
            line = apply_substitutions(line, substitutions)
        new_attrs = build_edge_attrs(style, is_dashed)
        line = _append_edge_attrs(line, new_attrs)
        out.append(line)
    return "\n".join(out)
