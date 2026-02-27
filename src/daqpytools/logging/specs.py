import io
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

"""
 Declarative specification for building and identifying objects
"""


@dataclass(frozen=True)
class HandlerSpec:
    representative_type: Any
    handler_type: type[logging.Handler]
    factory: Callable[..., logging.Handler]
    filter_handler_ids: tuple[Any, ...] # For HandleIDFilter
    target_stream: io.IOBase| None = None


@dataclass(frozen=True)
class FilterSpec:
    representative_type: Any
    filter_type: type[logging.Filter]
    factory: Callable[[set[Any], Mapping[str, Any]], logging.Filter]