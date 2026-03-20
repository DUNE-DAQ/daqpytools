#!/usr/bin/env python3
"""Generate targeted logging API docs from daqpytools registries.

This script generates Markdown pages that are easy to import into an existing
MkDocs (or other Markdown-based) documentation tree.

Generated content includes:
- handler registry index + per-handler-type pages
- filter registry index + per-filter-type pages
- logger API reference pages for selected public entry points

By default it also emits a machine-readable JSON manifest alongside Markdown.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any


@dataclass
class DocSpec:
    """Documentation-ready representation of a handler/filter spec."""

    type_name: str
    type_value: str
    kind: str
    class_fqdn: str
    class_name: str
    factory_fqdn: str
    factory_name: str
    fallback_types: list[str]
    summary: str


LOGGER_APIS: list[tuple[str, str]] = [
    ("get_daq_logger", "daqpytools.logging.logger.get_daq_logger"),
    ("setup_root_logger", "daqpytools.logging.logger.setup_root_logger"),
    (
        "setup_daq_ers_logger",
        "daqpytools.logging.logger.setup_daq_ers_logger",
    ),
]


def _install_erskafka_stub() -> None:
    """Install a lightweight erskafka stub so imports are docs-safe.

    The logging handlers module imports `ERSKafkaLogHandler` at module import
    time. In docs environments where `erskafka` is not installed, we provide a
    minimal stub to keep introspection and generation functional.
    """
    if "erskafka" in sys.modules and "erskafka.ERSKafkaLogHandler" in sys.modules:
        return

    erskafka_pkg = ModuleType("erskafka")
    erskafka_submodule = ModuleType("erskafka.ERSKafkaLogHandler")

    class StubERSKafkaLogHandler(logging.Handler):
        """Fallback docs-time stub for ERSKafkaLogHandler."""

        def emit(self, record: logging.LogRecord) -> None:
            del record

    erskafka_submodule.ERSKafkaLogHandler = StubERSKafkaLogHandler

    sys.modules["erskafka"] = erskafka_pkg
    sys.modules["erskafka.ERSKafkaLogHandler"] = erskafka_submodule


def _repo_root_from_script(script_path: Path) -> Path:
    """Infer repository root (`daqpytools`) from script location."""
    return script_path.parents[2]


def _ensure_import_path(repo_root: Path) -> None:
    """Ensure `src/` is importable for local execution without pip install."""
    src_path = repo_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


def _summary_from_docstring(obj: Any) -> str:
    """Extract the first non-empty docstring line as a short summary."""
    doc = getattr(obj, "__doc__", None)
    if not doc:
        return "No description provided."

    for line in doc.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return "No description provided."


def _class_fqdn(cls: type[Any]) -> tuple[str, str]:
    """Return class fully-qualified name and short class name."""
    class_name = cls.__name__
    fqdn = f"{cls.__module__}.{class_name}"
    return fqdn, class_name


def _factory_fqdn(factory: Any) -> tuple[str, str]:
    """Return factory fully-qualified name and short function name."""
    name = factory.__name__
    fqdn = f"{factory.__module__}.{name}"
    return fqdn, name


def _type_slug(type_name: str) -> str:
    """Stable slug for a handler/filter type."""
    return type_name.lower()


def _to_text_list(items: tuple[Any, ...] | list[Any] | set[Any]) -> list[str]:
    """Convert enum-ish values to readable strings."""
    values: list[str] = []
    for item in items:
        value = getattr(item, "value", None)
        if isinstance(value, str):
            values.append(value)
        else:
            values.append(str(item))
    return values


def _build_handler_docspecs() -> dict[str, list[DocSpec]]:
    """Convert handler registry content to grouped doc specs."""
    from daqpytools.logging.handlers import HANDLER_SPEC_REGISTRY

    grouped: dict[str, list[DocSpec]] = {}

    for handler_type, specs in HANDLER_SPEC_REGISTRY.items():
        type_name = handler_type.name
        type_value = handler_type.value
        grouped[type_name] = []

        for spec in specs:
            class_fqdn, class_name = _class_fqdn(spec.handler_class)
            factory_fqdn, factory_name = _factory_fqdn(spec.factory)

            grouped[type_name].append(
                DocSpec(
                    type_name=type_name,
                    type_value=type_value,
                    kind="handler",
                    class_fqdn=class_fqdn,
                    class_name=class_name,
                    factory_fqdn=factory_fqdn,
                    factory_name=factory_name,
                    fallback_types=_to_text_list(spec.fallback_types),
                    summary=_summary_from_docstring(spec.factory),
                )
            )

    return grouped


def _build_filter_docspecs() -> dict[str, list[DocSpec]]:
    """Convert filter registry content to grouped doc specs."""
    from daqpytools.logging.filters import FILTER_SPEC_REGISTRY

    grouped: dict[str, list[DocSpec]] = {}

    for filter_type, spec in FILTER_SPEC_REGISTRY.items():
        type_name = filter_type.name
        type_value = filter_type.value
        class_fqdn, class_name = _class_fqdn(spec.filter_class)
        factory_fqdn, factory_name = _factory_fqdn(spec.factory)

        grouped[type_name] = [
            DocSpec(
                type_name=type_name,
                type_value=type_value,
                kind="filter",
                class_fqdn=class_fqdn,
                class_name=class_name,
                factory_fqdn=factory_fqdn,
                factory_name=factory_name,
                fallback_types=_to_text_list(spec.fallback_types),
                summary=_summary_from_docstring(spec.factory),
            )
        ]

    return grouped


def _render_handlers_index(handler_specs: dict[str, list[DocSpec]]) -> str:
    """Render handlers index page."""
    lines = [
        "# Handlers reference",
        "",
        "Auto-generated from `HANDLER_SPEC_REGISTRY`.",
        "",
        "| HandlerType | Page | Specs |",
        "|---|---|---|",
    ]

    for type_name in sorted(handler_specs):
        slug = _type_slug(type_name)
        specs = handler_specs[type_name]
        type_value = specs[0].type_value
        page = f"[{type_name}](./{slug}.md)"
        lines.append(f"| `{type_name}` (`{type_value}`) | {page} | {len(specs)} |")

    lines.extend(
        [
            "",
            "Factory signatures and kwargs are rendered from mkdocstrings directives",
            "on each per-type page.",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_filters_index(filter_specs: dict[str, list[DocSpec]]) -> str:
    """Render filters index page."""
    lines = [
        "# Filters reference",
        "",
        "Auto-generated from `FILTER_SPEC_REGISTRY`.",
        "",
        "| FilterType | Page | Specs |",
        "|---|---|---|",
    ]

    for type_name in sorted(filter_specs):
        slug = _type_slug(type_name)
        specs = filter_specs[type_name]
        type_value = specs[0].type_value
        page = f"[{type_name}](./{slug}.md)"
        lines.append(f"| `{type_name}` (`{type_value}`) | {page} | {len(specs)} |")

    lines.extend(
        [
            "",
            "Factory signatures and kwargs are rendered from mkdocstrings directives",
            "on each per-type page.",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_type_page(type_name: str, kind: str, specs: list[DocSpec]) -> str:
    """Render per-type page for handler/filter docs."""
    kind_title = "Handler" if kind == "handler" else "Filter"
    lines = [
        f"# {type_name} {kind_title.lower()}",
        "",
        f"This page is auto-generated for `{kind_title}Type.{type_name}`.",
        "",
    ]

    if len(specs) > 1:
        lines.extend(
            [
                "> This type resolves to multiple specs/factories.",
                "",
            ]
        )

    for idx, spec in enumerate(specs, start=1):
        section_title = f"Spec {idx}" if len(specs) > 1 else "Spec"
        lines.extend(
            [
                f"## {section_title}",
                "",
                f"- {kind_title} type: `{spec.type_name}` (`{spec.type_value}`)",
                f"- {kind_title} class: `{spec.class_name}`",
                f"- {kind_title} class FQDN: `{spec.class_fqdn}`",
                f"- Factory: `{spec.factory_name}`",
                f"- Factory FQDN: `{spec.factory_fqdn}`",
                (
                    "- Fallback types: "
                    + (", ".join(f"`{value}`" for value in spec.fallback_types)
                       if spec.fallback_types else "None")
                ),
                f"- Summary: {spec.summary}",
                "",
                "### Factory API",
                "",
                f"::: {spec.factory_fqdn}",
                "",
            ]
        )

    return "\n".join(lines) + "\n"


def _render_logger_api_page(title: str, fqdn: str) -> str:
    """Render one logger API page with mkdocstrings directive."""
    lines = [
        f"# {title}",
        "",
        f"::: {fqdn}",
        "",
    ]
    return "\n".join(lines)


def _render_logging_index() -> str:
    """Render overview page for generated logging docs."""
    lines = [
        "# Logging generated reference",
        "",
        "This section is generated and intended for inclusion in existing docs.",
        "",
        "## Logger APIs",
        "",
        "- [get_daq_logger](./get_daq_logger.md)",
        "- [setup_root_logger](./setup_root_logger.md)",
        "- [setup_daq_ers_logger](./setup_daq_ers_logger.md)",
        "",
        "## Registries",
        "",
        "- [Handlers reference](./handlers/index.md)",
        "- [Filters reference](./filters/index.md)",
        "",
    ]
    return "\n".join(lines)


def _write_text(path: Path, content: str) -> None:
    """Write UTF-8 text to disk, creating parents as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _to_manifest(
    handler_specs: dict[str, list[DocSpec]],
    filter_specs: dict[str, list[DocSpec]],
) -> dict[str, Any]:
    """Build a JSON-serializable manifest for generated docs."""

    def serialize(grouped: dict[str, list[DocSpec]]) -> dict[str, list[dict[str, Any]]]:
        payload: dict[str, list[dict[str, Any]]] = {}
        for type_name, specs in grouped.items():
            payload[type_name] = [
                {
                    "type_name": spec.type_name,
                    "type_value": spec.type_value,
                    "kind": spec.kind,
                    "class_name": spec.class_name,
                    "class_fqdn": spec.class_fqdn,
                    "factory_name": spec.factory_name,
                    "factory_fqdn": spec.factory_fqdn,
                    "fallback_types": spec.fallback_types,
                    "summary": spec.summary,
                }
                for spec in specs
            ]
        return payload

    return {
        "logger_apis": [
            {"name": name, "fqdn": fqdn}
            for name, fqdn in LOGGER_APIS
        ],
        "handlers": serialize(handler_specs),
        "filters": serialize(filter_specs),
    }


def generate(output_root: Path, emit_json_manifest: bool, clean: bool) -> list[Path]:
    """Generate all targeted docs files and return paths written."""
    if clean and output_root.exists():
        shutil.rmtree(output_root)

    handlers_dir = output_root / "handlers"
    filters_dir = output_root / "filters"
    written: list[Path] = []

    handler_specs = _build_handler_docspecs()
    filter_specs = _build_filter_docspecs()

    handlers_index = handlers_dir / "index.md"
    _write_text(handlers_index, _render_handlers_index(handler_specs))
    written.append(handlers_index)

    for type_name in sorted(handler_specs):
        slug = _type_slug(type_name)
        page_path = handlers_dir / f"{slug}.md"
        content = _render_type_page(type_name, "handler", handler_specs[type_name])
        _write_text(page_path, content)
        written.append(page_path)

    filters_index = filters_dir / "index.md"
    _write_text(filters_index, _render_filters_index(filter_specs))
    written.append(filters_index)

    for type_name in sorted(filter_specs):
        slug = _type_slug(type_name)
        page_path = filters_dir / f"{slug}.md"
        content = _render_type_page(type_name, "filter", filter_specs[type_name])
        _write_text(page_path, content)
        written.append(page_path)

    for title, fqdn in LOGGER_APIS:
        api_path = output_root / f"{title}.md"
        _write_text(api_path, _render_logger_api_page(title, fqdn))
        written.append(api_path)

    logging_index = output_root / "index.md"
    _write_text(logging_index, _render_logging_index())
    written.append(logging_index)

    if emit_json_manifest:
        manifest = _to_manifest(handler_specs, filter_specs)
        manifest_path = output_root / "manifest.json"
        _write_text(manifest_path, json.dumps(manifest, indent=2, sort_keys=True))
        written.append(manifest_path)

    return written


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Generate targeted logging docs from daqpytools registries "
            "(handlers, filters, logger APIs)."
        )
    )
    parser.add_argument(
        "--output-root",
        default="docs/generated/logging",
        help="Output directory for generated files (default: docs/generated/logging).",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Path to daqpytools repository root. Auto-detected if omitted.",
    )
    parser.add_argument(
        "--no-json-manifest",
        action="store_true",
        help="Do not emit the machine-readable JSON manifest.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove output directory before regeneration.",
    )
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    args = _parse_args()
    script_path = Path(__file__).resolve()
    repo_root = (
        Path(args.repo_root).resolve()
        if args.repo_root
        else _repo_root_from_script(script_path)
    )

    _ensure_import_path(repo_root)
    _install_erskafka_stub()

    output_root = Path(args.output_root)
    if not output_root.is_absolute():
        output_root = repo_root / output_root

    written = generate(
        output_root=output_root,
        emit_json_manifest=not args.no_json_manifest,
        clean=args.clean,
    )

    print(f"Generated {len(written)} files under: {output_root}")
    for path in sorted(written):
        print(f" - {path.relative_to(repo_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())