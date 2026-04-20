"""Utilities for UML styling and type-hint stripping."""

import re
import sys
from pathlib import Path
from typing import TextIO

import yaml


def vprint(
    verbose: bool,
    *args: object,
    sep: str = " ",
    end: str = "\n",
    file: TextIO | None = None,
    flush: bool = False,
) -> None:
    """Print only when verbose output is enabled."""
    if verbose:
        stream = sys.stdout if file is None else file
        stream.write(sep.join(str(arg) for arg in args) + end)
        if flush:
            stream.flush()


def _strip_param_types(params_str: str) -> str:
    """Strip type hints from a parameter list."""
    if not params_str.strip():
        return params_str

    # Split on top-level commas only (not commas inside [] or {})
    params, current, depth = [], [], 0
    for ch in params_str:
        if ch in "[({":
            depth += 1
            current.append(ch)
        elif ch in "])}":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            params.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        params.append("".join(current).strip())

    # Keep only the name (everything before the first ':')
    stripped = []
    for param in params:
        colon = param.find(":")
        stripped.append(param[:colon].rstrip() if colon != -1 else param)
    return ", ".join(stripped)


def strip_typehints(dot_src: str) -> str:
    """Remove type annotations from HTML labels in dot output."""
    lines = dot_src.splitlines()
    out_lines = []

    for line in lines:
        if "label=<" not in line:
            out_lines.append(line)
            continue

        # Pass 1: return types.
        line = re.sub(r"(?<=\)):\s*[^<}]+(?=<br|}>)", "", line)

        # Pass 2: parameter types.
        def _replace_params(m: re.Match[str]) -> str:
            return "(" + _strip_param_types(m.group(1)) + ")"

        line = re.sub(r"\(([^)]*)\)", _replace_params, line)

        # Pass 3: attribute types.
        line = re.sub(r"\s*:\s*[^<}]+(?=<br|}>)", "", line)

        out_lines.append(line)

    return "\n".join(out_lines)


def load_style_config(path: Path | str | None = None) -> dict[str, str]:
    """Load UML style configuration from YAML."""
    if path is None:
        path = Path(__file__).parent / "style.yaml"

    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Flatten the nested YAML structure to match existing STYLE dict format
    return {
        "class_fill": config["class"]["fill"],
        "class_stroke": config["class"]["stroke"],
        "class_font": config["class"]["font"],
        "class_fontsize": str(config["class"]["fontsize"]),
        "inherit_color": config["relationships"]["inherit_color"],
        "uses_color": config["relationships"]["uses_color"],
        "bg_color": config["graph"]["bg_color"],
        "rankdir": config["graph"]["rankdir"],
    }
