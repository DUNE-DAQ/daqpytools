"""
generate_uml.py
---------------
CLI interface for generating UML class diagrams using pyreverse.

This tool wraps style_pyreverse.py and split_diagram.py to produce
nicely styled UML diagrams, optionally split into multiple files by connected components.

Usage:
    daqpytools-generate-uml daqpytools --output-directory pics
    daqpytools-generate-uml daqpytools --output-directory pics --concise
    daqpytools-generate-uml -p my_package -c MyClass --output-directory pics --no-split
    daqpytools-generate-uml daqpytools --format svg --min-size 2
    daqpytools-generate-uml daqpytools --style-config ./my_style.yaml
"""

import subprocess
import sys
from pathlib import Path
import click
from daqpytools.logging.formatter import CONTEXT_SETTINGS


class PassthroughArgs(click.Command):
    """Custom Click command that captures unknown arguments for pyreverse passthrough."""
    
    def main(self, *args, **kwargs):
        """Override main to collect unknown args."""
        try:
            return super().main(*args, **kwargs)
        except click.exceptions.UsageError as e:
            # Check if this is an unrecognized option meant for pyreverse
            if "no such option" in str(e):
                # Let it through for passthrough handling
                raise
            raise


def validate_output_directory(ctx, param, value):
    """Validate and create output directory if needed."""
    if value:
        out_dir = Path(value)
        out_dir.mkdir(parents=True, exist_ok=True)
    return value


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument("targets", nargs=-1, required=False)
@click.option(
    "-o",
    "--output-directory",
    type=click.Path(),
    default=".",
    callback=validate_output_directory,
    help="Output directory for generated diagrams. [default: .]",
)
@click.option(
    "-f",
    "--format",
    type=click.Choice(["png", "svg", "pdf", "jpg"]),
    default="png",
    help="Output image format. [default: png]",
)
@click.option(
    "-c",
    "--concise",
    is_flag=True,
    help="Remove type hints from class attributes and methods.",
)
@click.option(
    "-ns",
    "--no-split",
    is_flag=True,
    help="Do not split diagram by connected components; generate single diagram.",
)
@click.option(
    "-ms",
    "--min-size",
    type=int,
    default=1,
    help="Minimum cluster size to render as separate file (used with --split). [default: 1]",
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
    "-v",
    "--verbose",
    is_flag=True,
    help="Verbose output.",
)
@click.option(
    "--style-config",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to YAML style config file for style_pyreverse.",
)
def main(
    targets,
    output_directory,
    format,
    concise,
    no_split,
    min_size,
    package,
    classes,
    verbose,
    style_config,
):
    """
    Generate styled UML class diagrams from Python code.

    You can specify packages/modules as TARGETS or use --package/-p.
    
    Examples:
        # Generate diagram for daqpytools package
        daqpytools-generate-uml daqpytools --output-directory pics
        
        # Generate with concise mode (no type hints)
        daqpytools-generate-uml daqpytools --concise
        
        # Generate specific class diagram
        daqpytools-generate-uml -p daqpytools -c MyClass
        
        # Skip splitting into components
        daqpytools-generate-uml daqpytools --no-split
        
        # Generate SVG with minimum cluster size of 2
        daqpytools-generate-uml daqpytools --format svg --min-size 2
    """
    
    output_dir = Path(output_directory)
    
    # ── Step 1: Build pyreverse command ──────────────────────────────────────
    pyreverse_args = []
    
    # Add targets and packages
    for target in targets:
        pyreverse_args.append(target)
    for pkg in package:
        pyreverse_args.append(pkg)
    
    # Add specific classes (-c flag)
    for cls in classes:
        pyreverse_args.extend(["-c", cls])
    
    if not pyreverse_args and not targets:
        click.secho("Error: No targets or packages specified.", fg="red", err=True)
        sys.exit(1)
    
    # ── Step 2: Run style_pyreverse.py ───────────────────────────────────────
    click.secho("[generate_uml] Running style_pyreverse...", fg="cyan")
    
    style_cmd = [
        "python", "-m", "daqpytools.uml.style_pyreverse",
    ] + pyreverse_args + [
        "--output-directory", str(output_dir),
        "--format", format,
    ]
    
    if concise:
        style_cmd.append("--concise")

    if style_config is not None:
        style_cmd.extend(["--style-config", str(style_config)])
    
    if verbose:
        click.echo(f"  Command: {' '.join(style_cmd)}")
    
    result = subprocess.run(style_cmd, capture_output=not verbose, text=True)
    if result.returncode != 0:
        click.secho(f"Error running style_pyreverse: {result.stderr}", fg="red", err=True)
        sys.exit(result.returncode)
    
    # ── Step 3: Find the generated .dot file ─────────────────────────────────
    dot_files = sorted(output_dir.glob("*_styled.dot"))
    if not dot_files:
        click.secho(
            "Warning: No styled .dot files found. Check style_pyreverse output.",
            fg="yellow",
            err=True,
        )
        return
    
    styled_dot = dot_files[-1]  # Use most recent if multiple
    click.secho(f"  ✓ Generated: {styled_dot.name}", fg="green")
    
    # ── Step 4: Run split_diagram.py (unless --no-split) ──────────────────────
    if not no_split:
        click.secho("[generate_uml] Running split_diagram...", fg="cyan")
        
        split_dir = output_dir / "split"
        split_cmd = [
            "python", "-m", "daqpytools.uml.split_diagram",
            str(styled_dot),
            "--output-directory", str(split_dir),
            "--format", format,
            "--min-size", str(min_size),
        ]
        
        if concise:
            split_cmd.append("--concise")
        
        if verbose:
            click.echo(f"  Command: {' '.join(split_cmd)}")
        
        result = subprocess.run(split_cmd, capture_output=not verbose, text=True)
        if result.returncode != 0:
            click.secho(f"Error running split_diagram: {result.stderr}", fg="red", err=True)
            sys.exit(result.returncode)
        
        click.secho(f"  ✓ Split diagrams written to: {split_dir}", fg="green")
    else:
        click.secho("[generate_uml] Skipping split_diagram (--no-split set)", fg="yellow")
    
    # ── Summary ──────────────────────────────────────────────────────────────
    click.secho("\n[generate_uml] ✓ Complete!", fg="green", bold=True)
    click.echo(f"  Output directory: {output_dir.resolve()}")
    if not no_split:
        click.echo(f"  Split diagrams: {(output_dir / 'split').resolve()}")


if __name__ == "__main__":
    main()