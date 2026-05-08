#!/usr/bin/env python3
"""Render styled UML dot files using Graphviz."""

from pathlib import Path

from graphviz import Source

from daqpytools.uml.utils import vprint


def render_dot(
    dot_path: Path, output_dir: Path, fmt: str = "png", verbose: bool = False
) -> Path:
    """Render a dot file to an image."""
    output_dir.mkdir(parents=True, exist_ok=True)
    vprint(verbose, f"[style_pyreverse] Rendering {dot_path.name} as {fmt}")
    source = Source.from_file(str(dot_path), format=fmt)
    return Path(
        source.render(
            filename=dot_path.stem,
            directory=str(output_dir),
            cleanup=True,
            quiet=not verbose,
        )
    )
