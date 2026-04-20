"""CLI interface for generating UML class diagrams.

This command calls the UML helper functions directly to:
1. run pyreverse in a chosen working directory,
2. style the generated dot files,
3. optionally render them, and
4. optionally split the diagrams into connected components.

Usage:
    daqpytools-generate-uml daqpytools --output-directory pics
    daqpytools-generate-uml daqpytools 
        --directory some/path --output-directory pics --split
    daqpytools-generate-uml daqpytools --format none
"""

from pathlib import Path

import click

from daqpytools.logging.formatter import CONTEXT_SETTINGS
from daqpytools.uml.dot_parsing import patch_dot
from daqpytools.uml.render import render_dot
from daqpytools.uml.split_diagram import split_dot_file
from daqpytools.uml.style_pyreverse import run_pyreverse
from daqpytools.uml.utils import load_style_config, vprint


def validate_output_directory(
    ctx: click.Context, param: click.Parameter, value: Path | None
) -> Path | None:
    """Return the output directory path without creating it yet."""
    if value is None:
        return None
    return Path(value)


def build_pyreverse_args(
    targets: tuple[str, ...], packages: tuple[str, ...], classes: tuple[str, ...]
) -> list[str]:
    """Build the pyreverse argument list from CLI inputs."""
    pyreverse_args = []
    pyreverse_args.extend(targets)
    pyreverse_args.extend(packages)
    for cls in classes:
        pyreverse_args.extend(["-c", cls])
    return pyreverse_args


def resolve_output_directory(
    directory: Path | None, output_directory: Path
) -> tuple[Path, Path]:
    """Resolve the working directory and output directory consistently."""
    cwd = Path.cwd() if directory is None else Path(directory).resolve()
    resolved_output = (
        output_directory if output_directory.is_absolute() else cwd / output_directory
    )
    resolved_output.mkdir(parents=True, exist_ok=True)
    return cwd, resolved_output


def style_dot_file(dot_path: Path, style: dict[str, str], concise: bool) -> Path:
    """Patch a raw dot file and write the styled version next to it."""
    original = dot_path.read_text(encoding="utf-8")
    patched = patch_dot(original, style=style, concise=concise)
    patched_path = dot_path.with_name(f"{dot_path.stem}_styled.dot")
    patched_path.write_text(patched, encoding="utf-8")
    return patched_path


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument("targets", nargs=-1, required=False)
@click.option(
    "-d",
    "--directory",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    default=None,
    help="Working directory to run pyreverse from. [default: current directory]",
)
@click.option(
    "-o",
    "-od",
    "--output-directory",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    default=Path("pics"),
    callback=validate_output_directory,
    help="Output directory for generated diagrams. [default: pics]",
)
@click.option(
    "-f",
    "--format",
    "output_format",
    type=click.Choice(["png", "svg", "pdf", "jpg", "none"], case_sensitive=False),
    default="png",
    help="Output image format, or 'none' to keep dot files only. [default: png]",
)
@click.option(
    "-c",
    "--concise",
    is_flag=True,
    help="Remove type hints from class attributes and methods.",
)
@click.option(
    "--split/--no-split",
    default=False,
    help="Split generated diagrams into connected components.",
)
@click.option(
    "-ms",
    "--min-size",
    type=int,
    default=1,
    help="Minimum cluster size to render as separate file. [default: 1]",
)
@click.option(
    "-p",
    "--package",
    multiple=True,
    help="Package(s) to analyze (passed to pyreverse).",
)
@click.option(
    "--class",
    "classes",
    multiple=True,
    help="Specific class(es) to include (passed to pyreverse as -c).",
)
@click.option(
    "--verbose/--suppress-verbose",
    default=True,
    help="Print progress messages.",
)
@click.option(
    "--style-config",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to YAML style config file for the UML renderer.",
)
def main(
    targets: tuple[str, ...],
    directory: Path | None,
    output_directory: Path,
    output_format: str,
    concise: bool,
    split: bool,
    min_size: int,
    package: tuple[str, ...],
    classes: tuple[str, ...],
    verbose: bool,
    style_config: Path | None,
) -> None:
    """Generate styled UML class diagrams from Python code."""
    pyreverse_args = build_pyreverse_args(targets, package, classes)
    if not pyreverse_args:
        click.secho("Error: No targets or packages specified.", fg="red", err=True)
        raise SystemExit(1)

    cwd, resolved_output_dir = resolve_output_directory(directory, output_directory)
    style = load_style_config(style_config)
    render_format = None if output_format.lower() == "none" else output_format.lower()

    vprint(verbose, f"[generate_uml] Running pyreverse in {cwd}")
    dot_files = run_pyreverse(
        pyreverse_args, resolved_output_dir, cwd=str(cwd), verbose=verbose
    )

    styled_dot_files: list[Path] = []
    for dot_path in dot_files:
        vprint(verbose, f"[generate_uml] Styling {dot_path.name}")
        styled_dot_files.append(style_dot_file(dot_path, style=style, concise=concise))

    split_dot_files: list[Path] = []
    if split:
        split_root = resolved_output_dir / "split"
        for styled_dot in styled_dot_files:
            split_output_dir = split_root / styled_dot.stem
            split_dot_files.extend(
                split_dot_file(
                    input_dot=styled_dot,
                    output_dir=split_output_dir,
                    concise=concise,
                    verbose=verbose,
                    min_size=min_size,
                )
            )
            vprint(
                verbose, f"[generate_uml] Split diagrams written to {split_output_dir}"
            )

    if render_format is not None:
        for split_dot in split_dot_files:
            img_path = render_dot(
                split_dot, split_dot.parent, fmt=render_format, verbose=verbose
            )
            vprint(verbose, f"[generate_uml] Written: {img_path}")

        for styled_dot in styled_dot_files:
            img_path = render_dot(
                styled_dot, resolved_output_dir, fmt=render_format, verbose=verbose
            )
            vprint(verbose, f"[generate_uml] Written: {img_path}")
    else:
        vprint(verbose, "[generate_uml] Skipping rendering (--format none)")

    vprint(verbose, "[generate_uml] Complete")
    vprint(verbose, f"[generate_uml] Output directory: {resolved_output_dir.resolve()}")


if __name__ == "__main__":
    main()
