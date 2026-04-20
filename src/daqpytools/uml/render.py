#!/usr/bin/env python3

import subprocess
import sys
from daqpytools.uml.utils import vprint


def render_dot(dot_path, output_dir, fmt="png", verbose=False):
    """Run graphviz 'dot' to render a .dot file to an image."""
    out_path = output_dir / (dot_path.stem + "." + fmt)
    cmd = ["dot", "-T" + fmt, str(dot_path), "-o", str(out_path)]
    vprint(verbose, f"[style_pyreverse] Rendering: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        vprint(verbose, "[style_pyreverse] dot stderr:", result.stderr)
        sys.exit(result.returncode)
    return out_path
