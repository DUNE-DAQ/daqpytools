#!/usr/bin/env python3
"""
split_diagram.py
----------------
Splits a pyreverse-generated (styled) .dot file into multiple files,
one per connected cluster of classes.

Isolated nodes (no edges) are grouped by their Python module path
rather than generating a file per class.

Usage:
    python split_diagram.py <input.dot> [--output-directory DIR] [--format png] [--concise]

Example:
    python split_diagram.py pics/classes_styled.dot --output-directory pics/split
    
    # With --concise to remove type hints:
    python split_diagram.py pics/classes_styled.dot --output-directory pics/split --concise
"""

import re
import subprocess
import sys
import argparse
from pathlib import Path
from collections import defaultdict


# ── Helpers ──────────────────────────────────────────────────────────────────

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


def strip_typehints(dot_src: str) -> str:
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

def parse_dot(dot_src: str):
    """
    Parse a flat (non-subgraph) dot file.
    Returns:
        header_lines  : list of str  – graph/node/edge default lines
        nodes         : dict[id -> label_line]
        edges         : list of (src, dst, raw_line)
        footer        : str
    """
    header_lines = []
    nodes = {}
    edges = []

    # Regex patterns
    node_re = re.compile(r'^"([^"]+)"\s*\[')
    edge_re = re.compile(r'^"([^"]+)"\s*->\s*"([^"]+)"')

    in_graph = False
    for line in dot_src.splitlines():
        stripped = line.strip()

        if re.match(r'^digraph\s', stripped):
            in_graph = True
            header_lines.append(line)
            continue

        if not in_graph or stripped == '}':
            continue

        em = edge_re.match(stripped)
        if em:
            edges.append((em.group(1), em.group(2), line))
            continue

        nm = node_re.match(stripped)
        if nm:
            nodes[nm.group(1)] = line
            continue

        # Graph/node/edge defaults and other directives
        header_lines.append(line)

    return header_lines, nodes, edges


def find_connected_components(node_ids: set, edges: list):
    """Union-Find over node_ids using edge pairs."""
    parent = {n: n for n in node_ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    for src, dst, _ in edges:
        if src in parent and dst in parent:
            union(src, dst)

    components = defaultdict(set)
    for n in node_ids:
        components[find(n)].add(n)

    return list(components.values())


def module_group(node_id: str) -> str:
    """
    Return a short group name for a node based on its module path.
    e.g. 'src.daqpytools.logging.exceptions.ERSEnvError' -> 'logging.exceptions'
    """
    parts = node_id.split('.')
    # Drop 'src', top-level package, and the class name (last part)
    # Keep the middle portion as the group name
    filtered = [p for p in parts[:-1] if p not in ('src',)]
    # Use last 2 meaningful segments
    return '.'.join(filtered[-2:]) if len(filtered) >= 2 else '.'.join(filtered)


def cluster_name(node_ids: set) -> str:
    """
    Derive a filesystem-safe name for a cluster from its node ids.
    For multi-node clusters: find the longest common module prefix.
    For single-node groups: use the module group name.
    """
    if len(node_ids) == 1:
        return module_group(next(iter(node_ids)))

    # Find common prefix of all node module paths
    all_parts = [nid.split('.') for nid in node_ids]
    common = all_parts[0]
    for parts in all_parts[1:]:
        common = [c for c, p in zip(common, parts) if c == p]

    # Drop 'src' and single-segment prefixes
    common = [p for p in common if p not in ('src',)]
    name = '.'.join(common[-2:]) if len(common) >= 2 else '.'.join(common)
    return name or 'misc'


def build_dot(graph_name: str, header_lines: list, node_lines: list, edge_lines: list, concise: bool = False) -> str:
    """Assemble a complete dot file from parts."""
    # The first header line is the digraph opener; rest are defaults
    opener = header_lines[0]  # e.g. 'digraph "classes" {'
    # Replace the graph name
    opener = re.sub(r'digraph\s+"[^"]*"', f'digraph "{graph_name}"', opener)
    defaults = header_lines[1:]

    parts = [opener]
    parts += defaults
    parts += ['']
    parts += node_lines
    parts += ['']
    parts += edge_lines
    parts += ['}']
    dot_content = '\n'.join(parts)
    
    # Strip type hints if concise mode is enabled
    if concise:
        dot_content = strip_typehints(dot_content)
    
    return dot_content


def render(dot_path: Path, fmt: str = 'png') -> Path:
    out_path = dot_path.with_suffix('.' + fmt)
    cmd = ['dot', '-T' + fmt, str(dot_path), '-o', str(out_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f'  [dot error] {result.stderr.strip()}')
        sys.exit(1)
    return out_path


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input_dot', help='Path to the styled .dot file')
    parser.add_argument('--output-directory', default='.', help='Where to write output files')
    parser.add_argument('--format', default='png', help='Output image format (png, svg, pdf)')
    parser.add_argument('--min-size', type=int, default=1,
                        help='Minimum cluster size to render as its own file (default: 1)')
    parser.add_argument('--concise', action='store_true',
                        help='Remove type hints from class attributes and methods')
    args = parser.parse_args()

    dot_path = Path(args.input_dot)
    output_dir = Path(args.output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)

    dot_src = dot_path.read_text(encoding='utf-8')
    header_lines, nodes, edges = parse_dot(dot_src)

    print(f'[split] Found {len(nodes)} nodes, {len(edges)} edges')

    # ── 1. Find connected components ─────────────────────────────────────────
    components = find_connected_components(set(nodes.keys()), edges)
    print(f'[split] Found {len(components)} connected components')

    # ── 2. Group singleton components by module ──────────────────────────────
    # Singletons: components of size 1
    # Multi-node: keep as-is (they are meaningfully connected)
    singleton_groups: dict[str, set] = defaultdict(set)
    multi_components = []

    for comp in components:
        if len(comp) == 1:
            node_id = next(iter(comp))
            group = module_group(node_id)
            singleton_groups[group].add(node_id)
        else:
            multi_components.append(comp)

    # Merge singleton groups into the component list
    all_clusters = multi_components + list(singleton_groups.values())
    print(f'[split] Will generate {len(all_clusters)} file(s) '
          f'({len(multi_components)} connected + {len(singleton_groups)} module groups)')

    # ── 3. Render each cluster ────────────────────────────────────────────────
    for cluster_nodes in sorted(all_clusters, key=lambda c: -len(c)):
        name = cluster_name(cluster_nodes)
        safe_name = re.sub(r'[^\w\-.]', '_', name)

        # Gather node lines
        node_lines = [nodes[n] for n in cluster_nodes if n in nodes]

        # Gather edge lines that connect nodes within this cluster
        edge_lines = [
            raw for src, dst, raw in edges
            if src in cluster_nodes and dst in cluster_nodes
        ]

        dot_content = build_dot(name, header_lines, node_lines, edge_lines, concise=args.concise)

        out_dot = output_dir / f'{safe_name}.dot'
        out_dot.write_text(dot_content, encoding='utf-8')

        out_img = render(out_dot, fmt=args.format)
        size_label = f'{len(cluster_nodes)} class{"es" if len(cluster_nodes) != 1 else ""}'
        print(f'  ✓  {out_img.name}  ({size_label})')


if __name__ == '__main__':
    main()