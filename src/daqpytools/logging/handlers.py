from __future__ import annotations

import io
import logging
import sys
from collections.abc import Mapping
from typing import Any, cast

from erskafka.ERSKafkaLogHandler import ERSKafkaLogHandler

from daqpytools.logging.exceptions import (
    LoggerHandlerError,
)
from daqpytools.logging.filters import (
    HandleIDFilter,
    add_filter,
    get_filter_spec,
)
from daqpytools.logging.formatter import (
    LoggingFormatter,
)
from daqpytools.logging.handlerconf import (
    HandlerType,
)
from daqpytools.logging.rich_handler import FormattedRichHandler
from daqpytools.logging.specs import HandlerSpec
from daqpytools.logging.utils import get_width


#### Helper functions ####
def logger_has_handler(
    log: logging.Logger,
    handler_type: type[logging.Handler],
    target_stream: io.IOBase | None = None,
) -> bool:
    """Check if logger already has a matching handler.

    For StreamHandler, ``target_stream`` can be used to distinguish stdout/stderr.
    """
    # Catches cases when a MockLogger is used in pytest
    if not isinstance(log, logging.Logger):
        return False

    type_matches = [
        isinstance(handler, handler_type)
        for handler in log.handlers
        if not isinstance(handler, logging.StreamHandler)
    ]

    stream_matches = [
            handler.stream is target_stream if target_stream else False
            for handler in log.handlers
            if isinstance(handler, logging.StreamHandler)
        ]
    return any(type_matches + stream_matches)

def logger_has_filter(log: logging.Logger, filter_type: type[logging.Filter]) -> bool:
    """Check if logger already has a matching filter type."""
    if not isinstance(log, logging.Logger):
        return False

    return any(isinstance(logger_filter, filter_type) for logger_filter in log.filters)

def ancestors_have_handlers(
    log: logging.Logger,
    use_parent_handlers: bool,
    handler_type: type[logging.Handler],
    target_stream: io.IOBase | None = None,
) -> None:
    """Check all parent loggers for an instance of the given logging type.

    Args:
        log (logging.Logger): Logger to check parent handlers of.
        use_parent_handlers (bool): Whether to check parent handlers.
        handler_type (type[logging.Handler]): Type of handler to check for.
        target_stream (io.IOBase | None): If handler_type is StreamHandler, the stream
            to check for. If None, any StreamHandler is checked.

    Returns:
        None

    Raises:
        LoggerHandlerError: If a parent logger has the given handler type.
    """
    # Sanity check
    if not use_parent_handlers:
        return False

    if not isinstance(log, logging.Logger):
        return False

    # Check that we are not using the true logging root logger
    python_root_logger_name = logging.getLogger().name
    if log.name == python_root_logger_name:
        err_msg = "You should not be interfacing with the root logger"
        raise ValueError(err_msg)
    # Validate the stream handler has a target stream
    if handler_type.__name__ == "StreamHandler" and target_stream is None:
        err_msg = (
            "target_stream must be specified when handler_type is StreamHandler"
        )
        raise ValueError(err_msg)

    # Validate the non-stream handler does not have a target stream
    if handler_type.__name__ != "StreamHandler" and target_stream is not None:
        err_msg = (
            "target_stream can only be specified when handler_type is StreamHandler"
        )
        raise ValueError(err_msg)

    logger_parent = log.parent
    visited_logger_ids: set[int] = set()

    while isinstance(logger_parent, logging.Logger):
        logger_id = id(logger_parent)
        if logger_id in visited_logger_ids:
            return False # Prevents infinite loop
        visited_logger_ids.add(logger_id)

        if logger_parent.name == python_root_logger_name:
            break

        if logger_has_handler(logger_parent,handler_type, target_stream):
            return True
        logger_parent = logger_parent.parent
    return False


def check_parent_handlers(
    log: logging.Logger,
    use_parent_handlers: bool,
    handler_type: type[logging.Handler],
    target_stream: io.IOBase | None = None,
) -> None:
    """Raise when a matching handler already exists on an ancestor logger."""
    if ancestors_have_handlers(log, use_parent_handlers, handler_type, target_stream):
        raise LoggerHandlerError(log.name, handler_type)
    
def logger_or_ancestors_have_handler(
    log: logging.Logger,
    use_parent_handlers: bool,
    handler_type: type[logging.Handler],
    target_stream: io.IOBase | None = None,
) -> bool:
    """Check if logger or (optionally) its ancestors have a matching handler."""
    return logger_has_handler(
        log, handler_type, target_stream
    ) or ancestors_have_handlers(log, use_parent_handlers, handler_type, target_stream)


#### Handlers #### 

def _build_rich_handler(extras: Mapping[str, Any]) -> logging.Handler:
    """Building the rich handler with any extras."""
    width = cast(int,  extras.get("width", get_width()))
    return FormattedRichHandler(width=width)

RICH_HANDLER_SPEC = HandlerSpec(
    representative_type = HandlerType.Rich,
    handler_type = FormattedRichHandler,
    factory=_build_rich_handler,
    filter_handler_ids = (HandlerType.Rich,), # For HandleIDFilter
)

def _build_stdout_handler(extras: Mapping[str, Any]) -> logging.Handler:
    del extras #unused
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(LoggingFormatter())
    return handler

STDOUT_HANDLER_SPEC = HandlerSpec(
    representative_type = HandlerType.Lstdout,
    handler_type = logging.StreamHandler,
    target_stream=cast(io.IOBase, sys.stdout),
    factory=_build_stdout_handler,
    filter_handler_ids = (HandlerType.Stream, HandlerType.Lstdout),
)

def _build_stderr_handler(extras: Mapping[str, Any]) -> logging.Handler:
    del extras #unused
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(LoggingFormatter())
    handler.setLevel(logging.ERROR)
    return handler

STDERR_HANDLER_SPEC = HandlerSpec(
    representative_type = HandlerType.Lstderr,
    handler_type = logging.StreamHandler,
    target_stream=cast(io.IOBase, sys.stderr),
    factory=_build_stderr_handler,
    filter_handler_ids = (HandlerType.Stream, HandlerType.Lstderr),
)

def _build_file_handler(extras: Mapping[str, Any]) -> logging.Handler:
    path = cast(str | None, extras.get("path"))
    if not path:
        err_msg = "path is requiired for file handler"
        raise ValueError(err_msg)
    handler = logging.FileHandler(filename=path)
    handler.setFormatter(LoggingFormatter())

    return handler

FILE_HANDLER_SPEC = HandlerSpec(
    representative_type=HandlerType.File,
    handler_type = logging.FileHandler,
    factory = _build_file_handler,
    filter_handler_ids=(HandlerType.File,)
)

def _build_erskafka_handler(extras: Mapping[str, Any]) -> logging.Handler: 
    session_name = cast( str | None, extras.get("session_name"))

    if not session_name:
        err_msg = "'session_name' is required for erskafka handler"
        raise ValueError(err_msg)

    topic = cast(str, extras.get("topic", "ers_stream"))
    address = cast(str, extras.get("address", "monkafka.cern.ch:30092"))
    app_name = cast(str, extras.get("app_name", None))
    return ERSKafkaLogHandler(
        session = session_name,
        kafka_address=address,
        kafka_topic = topic,
        app_name=app_name
    )
    
ERSKAFKA_HANDLER_SPEC = HandlerSpec(
    representative_type=HandlerType.Protobufstream,
    handler_type = ERSKafkaLogHandler,
    factory = _build_erskafka_handler,
    filter_handler_ids=[HandlerType.Protobufstream],
)




HANDLER_SPEC_REGISTRY : dict[HandlerType, tuple[HandlerSpec, ...]] = {
    HandlerType.Rich: (RICH_HANDLER_SPEC,),
    HandlerType.Lstdout: (STDOUT_HANDLER_SPEC,),
    HandlerType.Lstderr: (STDERR_HANDLER_SPEC,),
    HandlerType.Stream: (STDOUT_HANDLER_SPEC,STDERR_HANDLER_SPEC),
    HandlerType.File: (FILE_HANDLER_SPEC,),
    HandlerType.Protobufstream: (ERSKAFKA_HANDLER_SPEC,)
}

def get_handler_specs(handler_type: HandlerType):
    """Get the specs defined in the registry"""
    return HANDLER_SPEC_REGISTRY.get(handler_type, tuple())

def add_handler(
    log: logging.Logger,
    handler_type: HandlerType | str, 
    use_parent_handlers:bool, 
    fallback_handler: set[HandlerType] | None = None,
    extras: Mapping[str, Any] | None = None,
):    
    ht = HandlerType.from_string(handler_type) if isinstance(handler_type, str) else handler_type
    specs = get_handler_specs(ht) 
    
    for spec in specs:
        if logger_or_ancestors_have_handler(
            log,
            use_parent_handlers,
            spec.handler_type,
            target_stream=spec.target_stream,
        ):
            # raise ValueError('HEY THEY ALREADY EXIST')
            continue
            

        check_parent_handlers(
            log,
            use_parent_handlers,
            spec.handler_type,
            target_stream = spec.target_stream
        )

        handler = spec.factory(extras or {})
        effective_default_case = fallback_handler if fallback_handler is not None else spec.filter_handler_ids

        handler_ids: HandlerType | list[HandlerType]
        if len(spec.filter_handler_ids) == 1:
            handler_ids = cast(HandlerType, spec.filter_handler_ids[0])
        else: 
            handler_ids = [cast(HandlerType, handler_id) for handler_id in spec.filter_handler_ids] 
 
        handler.addFilter(
            HandleIDFilter(
                handler_id=handler_ids,
                fallback_handlers=effective_default_case
            )
        )

        log.addHandler(handler)



def add_handlers_from_types(
    log: logging.Logger,
    handler_types: set[HandlerType],
    use_parent_handlers: bool,
    fallback_handlers: set[HandlerType],
    extras: Mapping[str, Any] | None = None,
) -> None:
    """Add handlers and filters from a set of HandlerType values.

    Handler types resolve through ``HANDLER_SPEC_REGISTRY`` and are installed
    using ``add_handler``. Filter types resolve through ``FILTER_SPEC_REGISTRY``
    and are installed using ``add_filter``.
    """
    effective_handler_types = set(handler_types)

    if HandlerType.Stream in effective_handler_types:
        effective_handler_types.discard(HandlerType.Lstdout)
        effective_handler_types.discard(HandlerType.Lstderr)

    for handler_type in effective_handler_types:
        if get_handler_specs(handler_type):
            add_handler(
                log,
                handler_type,
                use_parent_handlers,
                fallback_handlers,
                extras,
            )
            continue

        filter_spec = get_filter_spec(handler_type)
        if filter_spec and not logger_has_filter(log, filter_spec.filter_type):
            add_filter(log, handler_type, fallback_handlers, extras)
