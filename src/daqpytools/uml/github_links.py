"""Resolve GitHub source links for UML nodes and inject them into dot files."""

import re
import shutil
import subprocess
from pathlib import Path

from daqpytools.uml.dot_parsing import append_bracket_attrs

NODE_LINE_PATTERN = re.compile(r'^"([^"]+)"\s*\[')

# Relative path templates tried in order to locate a FQN's source file.
_PATH_CANDIDATE_TEMPLATES = (
    "src/{path}.py",
    "{path}.py",
    "src/{path}/__init__.py",
    "{path}/__init__.py",
)


def resolve_git_ref(cwd: Path, default_ref: str) -> str:
    """Return the current commit SHA of the repo at ``cwd``, or ``default_ref``."""
    git_executable = shutil.which("git")
    if git_executable is None:
        return default_ref

    try:
        result = subprocess.run(  # noqa: S603
            [git_executable, "-C", str(cwd), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return default_ref
    sha = result.stdout.strip()
    return sha or default_ref


def resolve_source_path(fqn: str, cwd: Path) -> Path | None:
    """Return the source file for ``fqn`` relative to ``cwd``, if found."""
    paths = [fqn.split(".")]
    if len(paths[0]) > 1:
        paths.append(paths[0][:-1])

    for segments in paths:
        path = "/".join(segments)
        for template in _PATH_CANDIDATE_TEMPLATES:
            candidate = cwd / template.format(path=path)
            if candidate.is_file():
                return candidate
    return None


def find_class_line(file_path: Path, class_name: str) -> int | None:
    """Return the 1-based line number where ``class_name`` is defined."""
    pattern = re.compile(rf"^\s*class\s+{re.escape(class_name)}\b")
    text = file_path.read_text(encoding="utf-8")
    for lineno, line in enumerate(text.splitlines(), start=1):
        if pattern.match(line):
            return lineno
    return None


def build_node_url(
    fqn: str,
    cwd: Path,
    org: str,
    repo: str,
    ref: str,
    link_line_number: bool,
) -> str | None:
    """Build a GitHub blob URL for ``fqn``, or ``None`` if unresolved."""
    source_path = resolve_source_path(fqn, cwd)
    if source_path is None:
        return None

    rel_path = source_path.relative_to(cwd).as_posix()
    url = f"https://github.com/{org}/{repo}/blob/{ref}/{rel_path}"

    if link_line_number:
        class_name = fqn.rsplit(".", 1)[-1]
        lineno = find_class_line(source_path, class_name)
        if lineno is not None:
            url += f"#L{lineno}"

    return url


def inject_node_links(
    dot_src: str,
    cwd: Path,
    org: str,
    repo: str,
    ref: str,
    link_line_number: bool = False,
) -> str:
    """Add a ``URL`` attribute to each node whose source file can be resolved."""
    out = []
    for line in dot_src.splitlines():
        match = NODE_LINE_PATTERN.match(line.strip())
        if match:
            url = build_node_url(match.group(1), cwd, org, repo, ref, link_line_number)
            if url is not None:
                line = append_bracket_attrs(line, f'URL="{url}", target="_blank"')
        out.append(line)
    return "\n".join(out)
