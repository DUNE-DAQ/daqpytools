#!/usr/bin/env python3
"""
split_diagram.py
----------------
Splits a pyreverse-generated (styled) .dot file into multiple files,
one per connected cluster of classes.

Isolated nodes (no edges) are grouped by their Python module path
rather than generating a file per class.

Usage:
    python split_diagram.py <input.dot> [--output-directory DIR] [--format png] [--concise] [--suppress-verbose]

Example:
    python split_diagram.py pics/classes_styled.dot --output-directory pics/split
    
    # With --concise to remove type hints:
    python split_diagram.py pics/classes_styled.dot --output-directory pics/split --concise
"""

import re
import sys
import argparse
from pathlib import Path
from collections import defaultdict
from daqpytools.uml.utils import strip_typehints, vprint
from daqpytools.uml.render import render_dot


# ── Helpers ──────────────────────────────────────────────────────────────────


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


def split_dot_file(input_dot: Path, output_dir: Path, concise: bool = False, verbose: bool = False, min_size: int = 1):
    """Split a styled .dot file into cluster-specific .dot files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    dot_src = input_dot.read_text(encoding='utf-8')
    header_lines, nodes, edges = parse_dot(dot_src)

    vprint(verbose, f'[split] Found {len(nodes)} nodes, {len(edges)} edges')

    components = find_connected_components(set(nodes.keys()), edges)
    vprint(verbose, f'[split] Found {len(components)} connected components')

    singleton_groups: dict[str, set] = defaultdict(set)
    multi_components = []

    for comp in components:
        if len(comp) == 1:
            node_id = next(iter(comp))
            group = module_group(node_id)
            singleton_groups[group].add(node_id)
        else:
            multi_components.append(comp)

    all_clusters = multi_components + list(singleton_groups.values())
    vprint(verbose, f'[split] Will generate {len(all_clusters)} file(s) '
          f'({len(multi_components)} connected + {len(singleton_groups)} module groups)')

    written_dot_files: list[Path] = []

    for cluster_nodes in sorted(all_clusters, key=lambda c: -len(c)):
        if len(cluster_nodes) < min_size:
            vprint(verbose, f'  -  skipping {len(cluster_nodes)} node cluster below min_size={min_size}')
            continue

        name = cluster_name(cluster_nodes)
        safe_name = re.sub(r'[^\w\-.]', '_', name)
        node_lines = [nodes[n] for n in cluster_nodes if n in nodes]
        edge_lines = [
            raw for src, dst, raw in edges
            if src in cluster_nodes and dst in cluster_nodes
        ]
        dot_content = build_dot(name, header_lines, node_lines, edge_lines, concise=concise)
        out_dot = output_dir / f'{safe_name}.dot'
        out_dot.write_text(dot_content, encoding='utf-8')
        written_dot_files.append(out_dot)

        size_label = f'{len(cluster_nodes)} class{"es" if len(cluster_nodes) != 1 else ""}'
        vprint(verbose, f'  ✓  {out_dot.name}  ({size_label})')

    return written_dot_files


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('input_dot', help='Path to the styled .dot file')
    parser.add_argument('--output-directory', default='.', help='Where to write output files')
    parser.add_argument('--format', default='png', choices=['png', 'svg', 'pdf', 'jpg', 'none'], help='Output image format (png, svg, pdf, jpg) or none')
    parser.add_argument('--min-size', type=int, default=1,
                        help='Minimum cluster size to render as its own file (default: 1)')
    parser.add_argument('--concise', action='store_true',
                        help='Remove type hints from class attributes and methods')
    parser.add_argument('--suppress-verbose', dest='verbose', action='store_false',
                        help='Suppress split progress messages')
    parser.set_defaults(verbose=True)
    args = parser.parse_args()

    dot_files = split_dot_file(
        input_dot=Path(args.input_dot),
        output_dir=Path(args.output_directory),
        concise=args.concise,
        verbose=args.verbose,
        min_size=args.min_size,
    )

    render_format = None if args.format == 'none' else args.format
    if render_format is not None:
        for dot_file in dot_files:
            out_img = render_dot(dot_file, Path(args.output_directory), fmt=render_format, verbose=args.verbose)
            vprint(args.verbose, f'  ✓  {out_img.name}  (rendered)')