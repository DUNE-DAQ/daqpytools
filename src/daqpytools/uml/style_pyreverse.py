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

import argparse
import re
import subprocess
import sys
from pathlib import Path
from daqpytools.uml.dot_parsing import patch_dot
from daqpytools.uml.render import render_dot
from daqpytools.uml.utils import load_style_config, vprint


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



def run_pyreverse(extra_args, output_dir, cwd=None, verbose=False):
    """Run pyreverse with -o dot and return the paths to generated .dot files."""
    cmd = ["pyreverse", "-o", "dot", "--output-directory", str(output_dir)] + extra_args
    vprint(verbose, f"[style_pyreverse] Running: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)

    if result.returncode != 0:
        print("[style_pyreverse] pyreverse stderr:", result.stderr)
        sys.exit(result.returncode)
    dot_files = list(output_dir.glob("*.dot"))
    if not dot_files:
        print("[style_pyreverse] ERROR: pyreverse produced no .dot files in", output_dir)
        sys.exit(1)
    return dot_files





def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--output-directory", default=".")
    parser.add_argument(
        "--suppress-verbose",
        dest="verbose",
        action="store_false",
        help="Suppress pyreverse, patching, and rendering status messages.",
    )
    parser.add_argument(
        "--cwd",
        default=None,
        help="Working directory to run pyreverse from and resolve relative output paths against.",
    )
    parser.add_argument("--format", default=None,
                        help="Output image format (png, svg, pdf …)")
    parser.add_argument("--concise", action="store_true",
                        help="Remove type hints from class attributes and methods")
    parser.add_argument(
        "--style-config",
        default=None,
        help="Path to YAML style config file (defaults to uml/style.yaml).",
    )
    parser.set_defaults(verbose=True)
    
    known, pyreverse_args = parser.parse_known_args()

    pyreverse_args = _filter_pyreverse_args(pyreverse_args)
    style = load_style_config(known.style_config)

    cwd = Path(known.cwd).resolve() if known.cwd else None
    output_dir = Path(known.output_directory)
    if cwd is not None and not output_dir.is_absolute():
        output_dir = cwd / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    
    # Stage 1. Run pyreverse
    dot_files = run_pyreverse(
        pyreverse_args,
        output_dir,
        cwd=str(cwd) if cwd is not None else None,
        verbose=known.verbose,
    )

    # Stage 2. Patch and save the original 
    ## If you are running this script directly you are probably debugging
    ## So we save the patched dot file along with the original
    for dot_path in dot_files:
        vprint(known.verbose, f"[style_pyreverse] Styling {dot_path.name} …")

        original = dot_path.read_text(encoding="utf-8")
        patched  = patch_dot(original, style=style, concise=known.concise)

        # Save patched .dot alongside original (useful for debugging)
        patched_path = dot_path.with_name(dot_path.stem + "_styled.dot")
        patched_path.write_text(patched, encoding="utf-8")

        # Stage 2.5 Render the dot files
        if known.format:
            img_path = render_dot(patched_path, output_dir, fmt=known.format, verbose=known.verbose)
            vprint(known.verbose, f"[style_pyreverse] ✓  Written: {img_path}")
        else:
            vprint(known.verbose, f"[style_pyreverse] x  No format, skipping render")


if __name__ == "__main__":
    main()