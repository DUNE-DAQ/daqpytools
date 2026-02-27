"""Declarative specifications used to construct logging handlers and filters.

This module defines immutable spec objects that describe:
- how a handler or filter is built (`factory`),
- how it is identified at runtime (`handler_class` / `filter_class`), and
- which handler types should be used for fallback routing (`fallback_types`).
"""

import io
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HandlerSpec:
    """Specification for creating and identifying a logging handler.

    Attributes:
        alias: Canonical identifier for the spec (typically a `HandlerType`).
        handler_class: Runtime logging class used to detect existing handlers.
        factory: Callable that builds the handler instance from configuration extras.
        fallback_types: Handler types this handler maps to for fallback behavior.
        target_stream: Optional stream discriminator for stream-based handlers
            (for example, stdout vs stderr).
    """

    alias: Any
    handler_class: type[logging.Handler]
    factory: Callable[..., logging.Handler]
    fallback_types: tuple[Any, ...]
    target_stream: io.IOBase | None = None


@dataclass(frozen=True)
class FilterSpec:
    """Specification for creating and identifying a logging filter.

    Attributes:
        alias: Canonical identifier for the spec (typically a `HandlerType`).
        filter_class: Runtime logging filter class used to detect existing filters.
        factory: Callable that builds the filter from fallback handlers and extras.
        fallback_types: Default handler types passed to the filter factory when
            no explicit fallback set is provided by the caller.
    """

    alias: Any
    filter_class: type[logging.Filter]
    factory: Callable[[set[Any], Mapping[str, Any]], logging.Filter]
    fallback_types: tuple[Any, ...] = ()