import re
import yaml
from pathlib import Path


def vprint(verbose, *args, **kwargs):
    """Print only when verbose output is enabled."""
    if verbose:
        print(*args, **kwargs)


def _strip_param_types(params_str: str) -> str:
    """Strip type hints from a parameter list (the content between parentheses).

    Handles complex types like ``dict[str, IssueRecord]`` by counting
    bracket depth so inner commas are not treated as parameter separators.
    """
    if not params_str.strip():
        return params_str

    # Split on top-level commas only (not commas inside [] or {})
    params, current, depth = [], [], 0
    for ch in params_str:
        if ch in '[({':
            depth += 1
            current.append(ch)
        elif ch in '])}':
            depth -= 1
            current.append(ch)
        elif ch == ',' and depth == 0:
            params.append(''.join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        params.append(''.join(current).strip())

    # Keep only the name (everything before the first ':')
    stripped = []
    for param in params:
        colon = param.find(':')
        stripped.append(param[:colon].rstrip() if colon != -1 else param)
    return ', '.join(stripped)


def strip_typehints(dot_src):
    """Remove type annotations from class/attribute/method labels.

    Three-pass approach applied only to lines that carry an HTML label:

    1. Return types  – strips ``: ReturnType`` that follows a closing ``)``.
       e.g. ``filter(record: logging.LogRecord): bool`` → ``filter(record: logging.LogRecord)``

    2. Parameter types – strips ``: Type`` from each parameter inside ``()``.
       e.g. ``filter(record: logging.LogRecord)`` → ``filter(record)``
       Handles complex types such as ``dict[str, IssueRecord]`` correctly.

    3. Attribute types – strips `` : Type`` from plain field entries.
       e.g. ``initial_threshold : int`` → ``initial_threshold``
    """
    lines = dot_src.splitlines()
    out_lines = []

    for line in lines:
        if 'label=<' not in line:
            out_lines.append(line)
            continue

        # Pass 1 – return types: ): ReturnType<br  →  )<br
        line = re.sub(r'(?<=\)):\s*[^<}]+(?=<br|}>)', '', line)

        # Pass 2 – parameter types inside ()
        def _replace_params(m):
            return '(' + _strip_param_types(m.group(1)) + ')'
        line = re.sub(r'\(([^)]*)\)', _replace_params, line)

        # Pass 3 – attribute types: name : Type<br  →  name<br
        line = re.sub(r'\s*:\s*[^<}]+(?=<br|}>)', '', line)

        out_lines.append(line)

    return '\n'.join(out_lines)


def load_style_config(path=None):
    """Load UML style configuration from YAML file.

    Loads the style configuration (colors, fonts, layout) from a YAML file
    and returns it as a flat dictionary compatible with the STYLE dict format.

    Args:
        path: Path to the YAML config file. If None, uses default location
              (style.yaml in the same directory as this module).

    Returns:
        Dictionary with keys: class_fill, class_stroke, class_font, class_fontsize,
        inherit_color, uses_color, bg_color, rankdir.
    """
    if path is None:
        path = Path(__file__).parent / "style.yaml"

    with open(path, 'r', encoding='utf-8') as f:
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
