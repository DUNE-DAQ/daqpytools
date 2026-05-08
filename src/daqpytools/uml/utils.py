"""Utilities for UML styling and type-hint stripping."""

import re
import sys
from importlib.resources import as_file, files
from pathlib import Path
from typing import TextIO

from daqpytools.utils.config_loader import ConfigLoader


def _load_context_settings() -> dict[str, list[str]]:
    """Load CLI context settings from the packaged UML configuration."""
    with as_file(files("daqpytools.uml") / "uml_format.ini") as config_path:
        help_options_str = ConfigLoader(config_path).safe_load_config(
            "cli", "help_option_names"
        )

    return {
        "help_option_names": [opt.strip() for opt in help_options_str.split(",")]
    }


CONTEXT_SETTINGS = _load_context_settings()
__all__ = ["CONTEXT_SETTINGS"]


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
    """Load UML style configuration from ini file using ConfigLoader.

    Uses ``ConfigLoader`` so section/option presence and emptiness are validated
    consistently with the rest of the codebase.
    """
    if path is None:
        path = Path(__file__).parent / "uml_format.ini"

    loader = ConfigLoader(path)

    class_style = loader.safe_load_config("uml_class_style")
    relationships = loader.safe_load_config("uml_relationships")
    graph = loader.safe_load_config("uml_graph")

    # Flatten the ini sections to match existing STYLE dict format
    return {
        "class_fill": class_style["fill"],
        "class_stroke": class_style["stroke"],
        "class_font": class_style["font"],
        "class_fontsize": class_style["fontsize"],
        "inherit_color": relationships["inherit_color"],
        "uses_color": relationships["uses_color"],
        "bg_color": graph["bg_color"],
        "rankdir": graph["rankdir"],
        "pad": graph["pad"],
        "nodesep": graph["nodesep"],
        "ranksep": graph["ranksep"],
    }
