#!/usr/bin/env python3
"""Mirror docs/ and docs_dev/ into a unified virtual FS for MkDocs.

Virtual output structure:
    readme.md        ← from docs_dev/readme_toplevel.md
    user/            ← from docs/
    dev/             ← from docs_dev/ (excluding utils/,
                       requirements.txt, readme_toplevel.md)
"""

from __future__ import annotations

from pathlib import Path

DOCS_DEV_EXCLUDE = {
    "utils",
    "requirements.txt",
    "readme_toplevel.md",
}


def _repo_root_from_script(script_path: Path) -> Path:
    """Infer repository root from script location."""
    return script_path.parents[2]


def _mirror_into_virtual_fs(
    source_dir: Path,
    virtual_prefix: str,
    exclude: set[str] | None = None,
) -> None:
    """Read all files from source_dir and write them into the mkdocs virtual FS.

    Args:
        source_dir: Real directory to mirror.
        virtual_prefix: Virtual FS prefix to write files under.
        exclude: Top-level names within source_dir to skip.
    """
    import mkdocs_gen_files

    exclude = exclude or set()

    for source_file in source_dir.rglob("*"):
        if not source_file.is_file():
            continue

        relative = source_file.relative_to(source_dir)

        if relative.parts[0] in exclude:
            continue

        virtual_path = f"{virtual_prefix}/{relative.as_posix()}"
        with mkdocs_gen_files.open(virtual_path, "wb") as fd:
            fd.write(source_file.read_bytes())


def _run_from_mkdocs_gen_files() -> None:
    """Run when this module is loaded by mkdocs-gen-files."""
    import mkdocs_gen_files

    script_path = Path(__file__).resolve()
    repo_root = _repo_root_from_script(script_path)

    # 1. readme_toplevel.md → virtual readme.md
    readme_source = repo_root / "docs_dev" / "readme_toplevel.md"
    if readme_source.exists():
        with mkdocs_gen_files.open("README.md", "wb") as fd:
            fd.write(readme_source.read_bytes())
    else:
        print(f"Warning: '{readme_source}' does not exist, skipping.")  # noqa: T201

    # 2. docs/ → virtual user/
    docs_dir = repo_root / "docs"
    if docs_dir.exists():
        _mirror_into_virtual_fs(docs_dir, "user")
    else:
        print(f"Warning: '{docs_dir}' does not exist, skipping.")  # noqa: T201

    # 3. docs_dev/ → virtual dev/ (with exclusions)
    docs_dev_dir = repo_root / "docs_dev"
    if docs_dev_dir.exists():
        _mirror_into_virtual_fs(docs_dev_dir, "dev", exclude=DOCS_DEV_EXCLUDE)
    else:
        print(f"Warning: '{docs_dev_dir}' does not exist, skipping.")  # noqa: T201


if __name__ != "__main__":
    _run_from_mkdocs_gen_files()