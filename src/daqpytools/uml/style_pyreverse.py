#!/usr/bin/env python3
"""
style_pyreverse.py
------------------
Wraps pyreverse to produce nicely styled UML class diagrams.

Usage:
    python style_pyreverse.py [pyreverse args...] [--concise] [--style-config PATH]

Example (drop-in replacement for your existing command):
    python style_pyreverse.py \
        -p formatted_rich_handler \
        -c src.daqpytools.logging.filters.BaseHandlerFilter \
        daqpytools \
        --output-directory pics

    # With --concise to remove type hints:
    python style_pyreverse.py daqpytools --output-directory pics --concise

Dependencies:
    pip install pylint     # provides pyreverse
    graphviz must be installed on your system (provides the 'dot' binary)
"""

import re
import subprocess
import sys
import argparse
from pathlib import Path
from daqpytools.uml.utils import strip_typehints, load_style_config
from daqpytools.uml.dot_patch_config import (
    PATCH_DOT_SUBSTITUTION_PIPELINE,
    EDGE_SUBSTITUTION_PIPELINE,
    DIGRAPH_OPEN_PATTERN,
    build_defaults_block,
    build_edge_attrs,
)

def _apply_substitutions(text: str, substitutions: list[tuple[str, str]]) -> str:
    """Apply regex substitutions in order."""
    for pattern, replacement in substitutions:
        text = re.sub(pattern, replacement, text)
    return text


def run_pyreverse(extra_args, output_dir):
    """Run pyreverse with -o dot and return the paths to generated .dot files."""
    cmd = ["pyreverse", "-o", "dot", "--output-directory", str(output_dir)] + extra_args
    print(f"[style_pyreverse] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("[style_pyreverse] pyreverse stderr:", result.stderr)
        sys.exit(result.returncode)
    dot_files = list(output_dir.glob("*.dot"))
    if not dot_files:
        print("[style_pyreverse] ERROR: pyreverse produced no .dot files in", output_dir)
        sys.exit(1)
    return dot_files


def patch_dot(dot_src, style, concise=False):
    """Rewrite .dot source to apply a clean UML style."""

    # ── 1. Run configured dot-level substitution pipeline ────────────────────
    for substitutions in PATCH_DOT_SUBSTITUTION_PIPELINE:
        dot_src = _apply_substitutions(dot_src, substitutions)
    
    # ── Concise mode: strip type hints ─────────────────────────────────────
    if concise:
        dot_src = strip_typehints(dot_src)

    # ── 2. Inject graph-level defaults right after the opening brace ─────────
    defaults_block = build_defaults_block(style)

    def insert_defaults(m):
        return m.group(0) + defaults_block

    dot_src = re.sub(DIGRAPH_OPEN_PATTERN, insert_defaults, dot_src, count=1)

    # ── 3. Fix arrowheads to proper UML style ────────────────────────────────
    dot_src = fix_edges(dot_src, style)

    return dot_src


#TODO: There is scope here to instead of 'fix' the edge to make this modifiable
# maybe not for the initial release..
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

        # Run configured edge-level substitution pipeline, then append style attrs
        for substitutions in EDGE_SUBSTITUTION_PIPELINE:
            line = _apply_substitutions(line, substitutions)
        new_attrs = build_edge_attrs(style, is_dashed)

        if '[' in line:
            # Append new attrs inside the existing bracket
            line = re.sub(
                r'\[([^\]]*)\]',
                lambda m: '[' + (m.group(1).strip().rstrip(',') + ', ' if m.group(1).strip() else '') + new_attrs + ']',
                line
            )
        else:
            # No existing bracket — add one before the semicolon or at end
            line = re.sub(r';?\s*$', ' [' + new_attrs + '];', line.rstrip())

        out.append(line)
    return '\n'.join(out)


def render_dot(dot_path, output_dir, fmt="png"):
    """Run graphviz 'dot' to render a .dot file to an image."""
    out_path = output_dir / (dot_path.stem + "." + fmt)
    cmd = ["dot", "-T" + fmt, str(dot_path), "-o", str(out_path)]
    print(f"[style_pyreverse] Rendering: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("[style_pyreverse] dot stderr:", result.stderr)
        sys.exit(result.returncode)
    return out_path


def _filter_pyreverse_args(pyreverse_args: list[str]) -> list[str]:
    """Remove CLI args we override when forcing pyreverse dot output."""
    filtered = []
    skip_next = False
    for arg in pyreverse_args:
        if skip_next:
            skip_next = False
            continue
        if arg in ("-o", "--output"):
            skip_next = True
            continue
        if re.match(r'^-o\w+', arg):    # e.g. -opng
            continue
        if arg == "--colorized":         # we handle colour ourselves
            continue
        filtered.append(arg)
    return filtered


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--output-directory", default=".")
    parser.add_argument("--format", default="png",
                        help="Output image format (png, svg, pdf …)")
    parser.add_argument("--concise", action="store_true",
                        help="Remove type hints from class attributes and methods")
    parser.add_argument(
        "--style-config",
        default=None,
        help="Path to YAML style config file (defaults to uml/style.yaml).",
    )
    
    known, pyreverse_args = parser.parse_known_args()

    pyreverse_args = _filter_pyreverse_args(pyreverse_args)
    style = load_style_config(known.style_config)

    output_dir = Path(known.output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)

    dot_files = run_pyreverse(pyreverse_args, output_dir)

    for dot_path in dot_files:
        print(f"[style_pyreverse] Styling {dot_path.name} …")

        original = dot_path.read_text(encoding="utf-8")
        patched  = patch_dot(original, style=style, concise=known.concise)

        # Save patched .dot alongside original (useful for debugging)
        patched_path = dot_path.with_name(dot_path.stem + "_styled.dot")
        patched_path.write_text(patched, encoding="utf-8")

        img_path = render_dot(patched_path, output_dir, fmt=known.format)
        print(f"[style_pyreverse] ✓  Written: {img_path}")


if __name__ == "__main__":
    main()