#!/usr/bin/env python3
"""
style_pyreverse.py
------------------
Wraps pyreverse to produce nicely styled UML class diagrams.

Usage:
    python style_pyreverse.py [pyreverse args...]

Example (drop-in replacement for your existing command):
    python style_pyreverse.py \
        -p formatted_rich_handler \
        -c src.daqpytools.logging.filters.BaseHandlerFilter \
        daqpytools \
        --output-directory pics

Dependencies:
    pip install pylint     # provides pyreverse
    graphviz must be installed on your system (provides the 'dot' binary)
"""

import re
import subprocess
import sys
import argparse
from pathlib import Path


# ── Colour palette (tweak these to your taste) ──────────────────────────────
STYLE = {
    "class_fill":     "#FFFDE7",   # warm cream (matches Image 1)
    "class_stroke":   "#8B7355",   # warm brown border
    "class_font":     "Helvetica",
    "class_fontsize": "10",
    "inherit_color":  "#555555",
    "uses_color":     "#555555",
    "bg_color":       "white",
    "rankdir":        "BT",
}
# ────────────────────────────────────────────────────────────────────────────


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


def patch_dot(dot_src):
    """Rewrite .dot source to apply a clean UML style."""
    s = STYLE

    # ── 1. Strip all per-node colour/style attributes pyreverse injected ─────
    dot_src = re.sub(r',?\s*\bfontcolor\s*=\s*"[^"]*"', '', dot_src)
    dot_src = re.sub(r',?\s*\bcolor\s*=\s*"[^"]*"', '', dot_src)
    dot_src = re.sub(r',?\s*\bstyle\s*=\s*"[^"]*"', '', dot_src)
    dot_src = re.sub(r',?\s*\bfillcolor\s*=\s*"[^"]*"', '', dot_src)

    # Clean up empty/malformed attribute lists left by the removals above
    dot_src = re.sub(r'\[\s*\]', '', dot_src)
    dot_src = re.sub(r'\[\s*,', '[', dot_src)
    dot_src = re.sub(r',\s*\]', ']', dot_src)
    dot_src = re.sub(r',\s*,', ', ', dot_src)

    # ── 2. Inject graph-level defaults right after the opening brace ─────────
    graph_line = (
        'graph ['
        'bgcolor="' + s["bg_color"] + '" '
        'fontname="' + s["class_font"] + '" '
        'pad="0.5" nodesep="0.6" ranksep="0.9" '
        'rankdir="' + s["rankdir"] + '"'
        '];'
    )
    node_line = (
        'node ['
        'shape=record '
        'style="filled" '
        'fillcolor="' + s["class_fill"] + '" '
        'color="' + s["class_stroke"] + '" '
        'fontname="' + s["class_font"] + '" '
        'fontsize=' + s["class_fontsize"] +
        '];'
    )
    edge_line = (
        'edge ['
        'fontname="' + s["class_font"] + '" '
        'fontsize="9" '
        'color="' + s["inherit_color"] + '"'
        '];'
    )
    defaults_block = "\n  " + graph_line + "\n  " + node_line + "\n  " + edge_line + "\n"

    def insert_defaults(m):
        return m.group(0) + defaults_block

    dot_src = re.sub(r'digraph\s+\S+\s*\{', insert_defaults, dot_src, count=1)

    # ── 3. Fix arrowheads to proper UML style ────────────────────────────────
    dot_src = fix_edges(dot_src)

    return dot_src


def fix_edges(dot_src):
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

        # Strip existing arrowhead/style/color attrs from this edge line
        line = re.sub(r',?\s*arrowhead\s*=\s*"?[^",\]\s]+"?', '', line)
        line = re.sub(r',?\s*\bstyle\s*=\s*"[^"]*"', '', line)
        line = re.sub(r',?\s*\bcolor\s*=\s*"[^"]*"', '', line)

        # Clean up any resulting empty/malformed brackets
        line = re.sub(r'\[\s*,', '[', line)
        line = re.sub(r',\s*\]', ']', line)
        line = re.sub(r'\[\s*\]', '', line)

        if is_dashed:
            new_attrs = (
                'arrowhead="open" '
                'style="dashed" '
                'color="' + STYLE["uses_color"] + '"'
            )
        else:
            new_attrs = (
                'arrowhead="empty" '
                'style="solid" '
                'color="' + STYLE["inherit_color"] + '"'
            )

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


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--output-directory", default=".")
    parser.add_argument("--format", default="png",
                        help="Output image format (png, svg, pdf …)")
    known, pyreverse_args = parser.parse_known_args()

    # Strip -o / --output flags (we always force dot output)
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
    pyreverse_args = filtered

    output_dir = Path(known.output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)

    dot_files = run_pyreverse(pyreverse_args, output_dir)

    for dot_path in dot_files:
        print(f"[style_pyreverse] Styling {dot_path.name} …")

        original = dot_path.read_text(encoding="utf-8")
        patched  = patch_dot(original)

        # Save patched .dot alongside original (useful for debugging)
        patched_path = dot_path.with_name(dot_path.stem + "_styled.dot")
        patched_path.write_text(patched, encoding="utf-8")

        img_path = render_dot(patched_path, output_dir, fmt=known.format)
        print(f"[style_pyreverse] ✓  Written: {img_path}")


if __name__ == "__main__":
    main()