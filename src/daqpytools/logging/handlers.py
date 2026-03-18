from __future__ import annotations

import io
import logging
import sys
from typing import cast

from erskafka.ERSKafkaLogHandler import ERSKafkaLogHandler

from daqpytools.logging.exceptions import ERSInitError, LoggerHandlerError
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

def _build_rich_handler(width: int | None = None, **_: object) -> logging.Handler:
    """Build the rich console handler.

    This factory is invoked from handler resolution in ``get_daq_logger`` and
    receives forwarded ``**extras``.

    Args:
        width: Optional console width used by ``FormattedRichHandler``.
            If ``None``, terminal width is auto-detected via ``get_width``.
        **_: Additional forwarded keyword arguments. Ignored by this factory.

    Returns:
        The configured rich logging handler.
    """
    real_width = width if width is not None else get_width()
    return FormattedRichHandler(width=real_width)

RICH_HANDLER_SPEC = HandlerSpec(
    alias = HandlerType.Rich,
    handler_class = FormattedRichHandler,
    factory=_build_rich_handler,
    fallback_types = (HandlerType.Rich,), # For HandleIDFilter
)

def _build_stdout_handler(**_: object) -> logging.Handler:
    """Build a stdout stream handler.

    Args:
        **_: Additional forwarded keyword arguments. Ignored by this factory.

    Returns:
        A ``logging.StreamHandler`` writing to ``sys.stdout``.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(LoggingFormatter())
    return handler

STDOUT_HANDLER_SPEC = HandlerSpec(
    alias = HandlerType.Lstdout,
    handler_class = logging.StreamHandler,
    target_stream=cast(io.IOBase, sys.stdout),
    factory=_build_stdout_handler,
    fallback_types = (HandlerType.Stream, HandlerType.Lstdout),
)

def _build_stderr_handler(**_: object) -> logging.Handler:
    """Build a stderr stream handler.

    Args:
        **_: Additional forwarded keyword arguments. Ignored by this factory.

    Returns:
        A ``logging.StreamHandler`` writing to ``sys.stderr`` with
        ``ERROR`` level.
    """
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(LoggingFormatter())
    handler.setLevel(logging.ERROR)
    return handler

STDERR_HANDLER_SPEC = HandlerSpec(
    alias = HandlerType.Lstderr,
    handler_class = logging.StreamHandler,
    target_stream=cast(io.IOBase, sys.stderr),
    factory=_build_stderr_handler,
    fallback_types = (HandlerType.Stream, HandlerType.Lstderr),
)

def _build_file_handler(path: str | None = None, **_: object) -> logging.Handler:
    """Build a file handler.

    Args:
        path: Path to the output log file. This is typically forwarded from
            ``get_daq_logger(..., file_handler_path=...)`` as ``path``.
        **_: Additional forwarded keyword arguments. Ignored by this factory.

    Returns:
        A configured ``logging.FileHandler``.

    Raises:
        ValueError: If ``path`` is not provided.
    """
    if not path:
        err_msg = "path is required for file handler"
        raise ValueError(err_msg)
    handler = logging.FileHandler(filename=path)
    handler.setFormatter(LoggingFormatter())

    return handler

FILE_HANDLER_SPEC = HandlerSpec(
    alias=HandlerType.File,
    handler_class = logging.FileHandler,
    factory = _build_file_handler,
    fallback_types=(HandlerType.File,)
)

def _build_erskafka_handler(
        session_name : str,
        topic : str = "ers_stream",
        address : str = "monkafka.cern.ch:30092",
        ers_app_name : str | None = None,
    **_: object) -> logging.Handler: 
    """Build an ERS Kafka handler.

    Args:
        session_name: ERS session name used by the Kafka handler.
        topic: Kafka topic for ERS log messages.
        address: Kafka broker address in ``host:port`` format.
        ers_app_name: Optional ERS application name associated with messages.
        **_: Additional forwarded keyword arguments. Ignored by this factory.

    Returns:
        A configured ``ERSKafkaLogHandler`` instance.

    Raises:
        ERSInitError: If the handler cannot be initialized.
    """
    
    try:
        return ERSKafkaLogHandler(
            session = session_name,
            kafka_address=address,
            kafka_topic = topic,
            app_name=ers_app_name
        )
    except Exception as err:
        raise ERSInitError(address, topic) from err

    
ERSKAFKA_HANDLER_SPEC = HandlerSpec(
    alias=HandlerType.Protobufstream,
    handler_class = ERSKafkaLogHandler,
    factory = _build_erskafka_handler,
    fallback_types=(HandlerType.Protobufstream,),
)




HANDLER_SPEC_REGISTRY : dict[HandlerType, tuple[HandlerSpec, ...]] = {
    HandlerType.Rich: (RICH_HANDLER_SPEC,),
    HandlerType.Lstdout: (STDOUT_HANDLER_SPEC,),
    HandlerType.Lstderr: (STDERR_HANDLER_SPEC,),
    HandlerType.Stream: (STDOUT_HANDLER_SPEC,STDERR_HANDLER_SPEC),
    HandlerType.File: (FILE_HANDLER_SPEC,),
    HandlerType.Protobufstream: (ERSKAFKA_HANDLER_SPEC,)
}

def get_handler_specs(handler_type: HandlerType) -> tuple[HandlerSpec, ...]:
    """Get the specs defined in the registry."""
    return HANDLER_SPEC_REGISTRY.get(handler_type, ())

def add_handler(
    log: logging.Logger,
    handler_type: HandlerType | str, 
    use_parent_handlers:bool, 
    fallback_handler: set[HandlerType] | None = None,
    **extras: object
 ) -> None:
    """Add a handler to the logger from the handler spec registry."""
    ht = (
        HandlerType.from_string(handler_type)
        if isinstance(handler_type, str)
        else handler_type
    )
    specs = get_handler_specs(ht) 
    
    for spec in specs:
        if logger_or_ancestors_have_handler(
            log,
            use_parent_handlers,
            spec.handler_class,
            target_stream=spec.target_stream,
        ):
            continue
            

        check_parent_handlers(
            log,
            use_parent_handlers,
            spec.handler_class,
            target_stream = spec.target_stream
        )

        handler = spec.factory(**extras)
        effective_default_case = (
            fallback_handler
            if fallback_handler is not None
            else spec.fallback_types
        )

        handler_ids: HandlerType | list[HandlerType]
        if len(spec.fallback_types) == 1:
            handler_ids = cast(HandlerType, spec.fallback_types[0])
        else: 
            handler_ids = [
                cast(HandlerType, handler_id)
                for handler_id in spec.fallback_types
            ] 
 
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
    **extras: object,
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
                **extras,
            )
            continue

        filter_spec = get_filter_spec(handler_type)
        if filter_spec and not logger_has_filter(log, filter_spec.filter_class):
            add_filter(log, handler_type, fallback_handlers, **extras)
