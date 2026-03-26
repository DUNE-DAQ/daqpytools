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

The script:
  1. Runs pyreverse with -o dot (always, regardless of what you pass)
  2. Post-processes the .dot file to apply a clean UML style
  3. Renders to PNG via Graphviz

Dependencies:
    pip install graphviz        # Python graphviz bindings (optional, fallback uses subprocess)
    pip install pylint          # provides pyreverse
    graphviz must be installed on your system (provides the 'dot' binary)
"""

import re
import subprocess
import sys
import os
import argparse
from pathlib import Path

# ── Colour palette (tweak these to your taste) ──────────────────────────────
STYLE = {
    # Node (class box) colours
    "class_fill":       "#FFFDE7",   # warm cream  (matches Image 1)
    "class_fill_dark":  "#FFF9C4",   # slightly deeper cream for header rows
    "class_stroke":     "#A0522D",   # siennna-ish border
    "class_font":       "Helvetica", # clean sans-serif
    "class_fontsize":   "10",

    # Edge colours
    "inherit_color":    "#555555",   # solid grey for inheritance
    "uses_color":       "#555555",   # dashed grey for dependencies

    # Graph background
    "bg_color":         "white",
    "rankdir":          "BT",        # bottom-to-top like a proper UML diagram
}
# ────────────────────────────────────────────────────────────────────────────


def run_pyreverse(extra_args: list[str], output_dir: Path) -> list[Path]:
    """Run pyreverse with -o dot and return the paths to generated .dot files."""
    cmd = [
        "pyreverse",
        "-o", "dot",
        "--output-directory", str(output_dir),
    ] + extra_args

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


def patch_dot(dot_src: str) -> str:
    """
    Rewrite the .dot source to apply a clean UML style:
      - cream fill for all class nodes
      - proper record shape kept intact
      - inheritance arrows → open hollow arrowhead (UML style)
      - dependency arrows → dashed with open arrowhead
    """
    s = STYLE

    # ── 1. Graph-level defaults ──────────────────────────────────────────────
    graph_defaults = f"""
    graph [bgcolor="{s['bg_color']}", fontname="{s['class_font']}", pad="0.5", nodesep="0.6", ranksep="0.8"];
    node  [shape=record, style="filled,rounded", fillcolor="{s['class_fill']}",
           color="{s['class_stroke']}", fontname="{s['class_font']}",
           fontsize={s['class_fontsize']}];
    edge  [fontname="{s['class_font']}", fontsize="9"];
"""

    # Insert defaults right after the opening brace of the digraph
    dot_src = re.sub(
        r'(digraph\s+\S+\s*\{)',
        r'\1' + graph_defaults,
        dot_src,
        count=1,
    )

    # ── 2. Strip pyreverse colorised per-node styles ─────────────────────────
    # pyreverse --colorized adds  color="..." fontcolor="..."  inside each node.
    # We remove those so our graph-level defaults win.
    dot_src = re.sub(r'\bcolor="[^"]*"', '', dot_src)
    dot_src = re.sub(r'\bfontcolor="[^"]*"', '', dot_src)
    dot_src = re.sub(r'\bstyle="[^"]*"', '', dot_src)   # remove per-node style too

    # ── 3. Fix arrowheads to proper UML style ────────────────────────────────
    # Inheritance (solid line, hollow triangle): arrowhead=empty
    dot_src = re.sub(
        r'(->.*?)\[([^\]]*)\]',
        lambda m: _fix_edge(m),
        dot_src,
    )

    # ── 4. Tidy up extra whitespace left by removals ─────────────────────────
    dot_src = re.sub(r'\[\s*,', '[', dot_src)
    dot_src = re.sub(r',\s*,', ',', dot_src)
    dot_src = re.sub(r'\[\s*\]', '', dot_src)

    return dot_src


def _fix_edge(match: re.Match) -> str:
    """
    Re-style edges:
      - dashed edge  → arrowhead=open,  style=dashed  (dependency / uses)
      - solid edge   → arrowhead=empty, style=solid   (inheritance)
    """
    full = match.group(0)
    attrs = match.group(2)

    if 'style="dashed"' in attrs or "style=dashed" in attrs:
        new_attrs = re.sub(r'arrowhead="[^"]*"', 'arrowhead="open"', attrs)
        if 'arrowhead' not in new_attrs:
            new_attrs += ', arrowhead="open"'
        new_attrs += f', color="{STYLE["uses_color"]}", style="dashed"'
    else:
        new_attrs = re.sub(r'arrowhead="[^"]*"', 'arrowhead="empty"', attrs)
        if 'arrowhead' not in new_attrs:
            new_attrs += ', arrowhead="empty"'
        new_attrs += f', color="{STYLE["inherit_color"]}", style="solid"'

    arrow_part = match.group(1)
    return f"{arrow_part}[{new_attrs}]"


def render_dot(dot_path: Path, output_dir: Path, fmt: str = "png") -> Path:
    """Run graphviz 'dot' to render a .dot file to an image."""
    out_path = output_dir / (dot_path.stem + f".{fmt}")
    cmd = ["dot", f"-T{fmt}", str(dot_path), "-o", str(out_path)]
    print(f"[style_pyreverse] Rendering: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("[style_pyreverse] dot stderr:", result.stderr)
        sys.exit(result.returncode)
    return out_path


def main():
    # Simple arg parsing: just grab --output-directory / -o ourselves,
    # pass everything else straight to pyreverse.
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--output-directory", default=".")
    parser.add_argument("--format", default="png",
                        help="Output image format (png, svg, pdf …)")

    known, pyreverse_args = parser.parse_known_args()

    # Strip -o / --output from pyreverse args to avoid confusion
    # (we always force -o dot)
    filtered = []
    skip_next = False
    for i, arg in enumerate(pyreverse_args):
        if skip_next:
            skip_next = False
            continue
        if arg in ("-o", "--output"):
            skip_next = True  # skip the value too
            continue
        if arg.startswith("-o") and len(arg) > 2:
            continue  # e.g. -opng
        filtered.append(arg)
    pyreverse_args = filtered

    output_dir = Path(known.output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate .dot files
    dot_files = run_pyreverse(pyreverse_args, output_dir)

    for dot_path in dot_files:
        print(f"[style_pyreverse] Styling {dot_path.name} …")

        # 2. Read & patch
        original = dot_path.read_text(encoding="utf-8")
        patched = patch_dot(original)

        # Save the patched dot alongside the original for debugging
        patched_path = dot_path.with_stem(dot_path.stem + "_styled")
        patched_path.write_text(patched, encoding="utf-8")

        # 3. Render to image
        img_path = render_dot(patched_path, output_dir, fmt=known.format)
        print(f"[style_pyreverse] ✓  Written: {img_path}")


if __name__ == "__main__":
    main()