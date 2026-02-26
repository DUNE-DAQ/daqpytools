from __future__ import annotations

import copy
import io
import logging
import sys
import time
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from threading import Lock
from typing import cast, Mapping, Any

from erskafka.ERSKafkaLogHandler import ERSKafkaLogHandler
from rich.logging import RichHandler
from rich.text import Text

from daqpytools.logging.exceptions import (
    LoggerHandlerError,
)
from daqpytools.logging.formatter import (
    DATE_TIME_BASE_FORMAT,
    LOG_RECORD_PADDING,
    TIME_ZONE,
    LoggingFormatter,
)

from daqpytools.logging.filters import (
    IssueRecord,
    BaseHandlerFilter,
    HandleIDFilter,
    ThrottleFilter,
)

from daqpytools.logging.rich_handler import FormattedRichHandler
from daqpytools.logging.specs import HandlerSpec, FilterSpec

from daqpytools.logging.handlerdataclasses import (
    HandlerType,
    LogHandlerConf,
    _resolve_default_case
)
from daqpytools.logging.routing import (
    AllowedHandlersStrategy,
    StreamAwareAllowedHandlersStrategy,
)
from daqpytools.logging.utils import get_width


  
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
    handler_type: HandlerType,
    use_parent_handlers:bool, 
    fallback_handler: set[HandlerType] | None,
    extras: Mapping[str, Any] | None = None,
):
    
    specs = get_handler_specs(handler_type) 
    for spec in specs:
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


# We want to eventually depreciate this I think..
# In favour of add_handlers_or_filters
def add_rich_handler(
    log: logging.Logger,
    use_parent_handlers: bool,
    fallback_handlers: set[HandlerType] | None = None,
) -> None:
    
    add_handler(
        log,
        HandlerType.Rich,
        use_parent_handlers,
        fallback_handlers
    )


def add_stdout_handler(
    log: logging.Logger,
    use_parent_handlers: bool,
    fallback_handlers: set[HandlerType] | None = None,
) -> None:
    add_handler(
        log,
        HandlerType.Lstdout,
        use_parent_handlers,
        fallback_handlers
    )


def add_stderr_handler(
    log: logging.Logger,
    use_parent_handlers: bool,
    fallback_handlers: set[HandlerType] | None = None,
) -> None:
    add_handler(
        log,
        HandlerType.Lstderr,
        use_parent_handlers,
        fallback_handlers
    )

def add_file_handler(
    log: logging.Logger,
    use_parent_handlers: bool,
    path: str,
    fallback_handlers: set[HandlerType] | None = None,
) -> None:
    add_handler(
        log,
        HandlerType.File,
        use_parent_handlers,
        fallback_handlers,
        extras = {
            "path" : path
        }
    )

def add_ers_kafka_handler(
    log: logging.Logger,
    use_parent_handlers: bool,
    session_name: str,
    fallback_handlers: set[HandlerType] | None = None,
    app_name : str|None =None,
    topic: str = "ers_stream",
    address: str = "monkafka.cern.ch:30092",
) -> None:
    add_handler(
        log,
        HandlerType.Protobufstream,
        use_parent_handlers,
        fallback_handlers,
        extras={
            "session_name": session_name,
            "topic": topic,
            "address": address,
            "app_name": app_name,
        },
    )
    

from daqpytools.logging.filters import add_throttle_filter

##################################################################################################
##################################################################################################
##################################################################################################
##################################################################################################
##################################################################################################



# def add_ers_kafka_handler(
#     log: logging.Logger,
#     use_parent_handlers: bool,
#     session_name: str,
#     fallback_handlers: set[HandlerType] | None = None,
#     app_name : str|None =None,
#     topic: str = "ers_stream",
#     address: str = "monkafka.cern.ch:30092",
# ) -> None:
#     # TODO/future: topic and address are new, propagate to all relevant implementation
#     """Add an ers protobuf handler to the root logger."""
#     if fallback_handlers is None:
#         fallback_handlers = {HandlerType.Protobufstream}
#     check_parent_handlers(log, use_parent_handlers, ERSKafkaLogHandler)
#     handler: ERSKafkaLogHandler = ERSKafkaLogHandler(session=session_name, 
#                                                      kafka_address = address, 
#                                                      kafka_topic = topic,
#                                                      app_name = app_name,
#                                                      )

#     handler.addFilter(
#         HandleIDFilter(
#             handler_id=HandlerType.Protobufstream,
#             fallback_handlers=fallback_handlers
#             )
#     )
#     log.addHandler(handler)

# def add_file_handler(
#     log: logging.Logger,
#     use_parent_handlers: bool,
#     path: str,
#     fallback_handlers: set[HandlerType] | None = None,
# ) -> None:
#     """Add a file handler to the root logger.

#     Args:
#         log (logging.Logger): Logger to add the file handler to.
#         use_parent_handlers (bool): Whether to check parent handlers.
#         path (str): Path to the log file.
#         fallback_handlers (set[HandlerType] | None): Default handler set used when
#             records do not explicitly include handler routing.

#     Returns:
#         None

#     Raises:
#         LoggerHandlerError: If a parent logger has a file handler.
#     """
#     if fallback_handlers is None:
#         fallback_handlers = {HandlerType.File}
#     check_parent_handlers(log, use_parent_handlers, logging.FileHandler)
#     file_handler = logging.FileHandler(filename=path)
#     file_handler.setFormatter(LoggingFormatter())
#     file_handler.addFilter(
#         HandleIDFilter(
#             handler_id=HandlerType.File,
#             fallback_handlers=fallback_handlers
#             )
#     )
#     log.addHandler(file_handler)
#     return




# This is the big ol massive function..
def add_handlers_from_types(
    log: logging.Logger,
    handler_types: set[HandlerType],
    use_parent_handlers: bool,
    fallback_handlers: set[HandlerType],
    file_name: str | None,
    ers_kafka_session: str | None,
    app_name : str|None = None,
) -> None:
    """Add handlers to a logger based on a set of HandlerType values.

    This helper intentionally supports only the default options for now:
    - ``use_parent_handlers`` is always True.
    - ``HandlerType.File`` is not supported and raises immediately.
    - ``HandlerType.Protobufstream`` requires ``ers_kafka_session``.
    """
    if HandlerType.Protobufstream in handler_types and not ers_kafka_session:
        err_msg = "ers_kafka_session is required for HandlerType.Protobufstream"
        raise ValueError(err_msg)
    
    if HandlerType.File in handler_types and not file_name:
        err_msg = "file_name is required for HandlerType.File"
        raise ValueError(err_msg)

    # Update relevant handler types that was parsed
    effective_handler_types = set(handler_types)
    if HandlerType.Stream in effective_handler_types:
        effective_handler_types.update({HandlerType.Lstdout, HandlerType.Lstderr})

    # Generate handler configurations based on arguments for auto install
    handler_configs: dict[
        HandlerType,
        tuple[
            type[logging.Handler] | None, # Handler as seen by Python's Logger
            io.IOBase | None, # Used for streamhandling
            type[logging.Filter] | None, # For filters attached to loggers
            Callable[[], None],  # Installer code
        ],
    ] = {
        HandlerType.Rich: (
            FormattedRichHandler,
            None,
            None,
            lambda: add_rich_handler(log, use_parent_handlers, fallback_handlers),
        ),
        HandlerType.Lstdout: (
            logging.StreamHandler,
            cast(io.IOBase, sys.stdout),
            None,
            lambda: add_stdout_handler(log, use_parent_handlers, fallback_handlers),
        ),
        HandlerType.Lstderr: (
            logging.StreamHandler,
            cast(io.IOBase, sys.stderr),
            None,
            lambda: add_stderr_handler(log, use_parent_handlers, fallback_handlers),
        ),
        HandlerType.Protobufstream: (
            ERSKafkaLogHandler,
            None,
            None,
            lambda: add_ers_kafka_handler(
                log, use_parent_handlers, ers_kafka_session, {HandlerType.Unknown},
                app_name
                # WE DONT WANT TO TRANSMIT BY DEFAULT
            ),
        ),
        HandlerType.Throttle: (
            None,
            None,
            ThrottleFilter,
            lambda: add_throttle_filter(log, fallback_handlers),
        ),
        HandlerType.File: (
            logging.FileHandler,
            None,
            None,
            lambda: add_file_handler(
                log, use_parent_handlers, file_name, fallback_handlers
            ),
        ),
    }


    for handler_type, (
        handler_class,
        target_stream,
        filter_type,
        installer,
    ) in handler_configs.items():
        
        # Skips if it encounters an unrequested handler
        if handler_type not in effective_handler_types:
            continue
        
        # Skips if handler/filter exists in either the logger or any of its ancestors
        handler_exists = (
            handler_class is not None
            and logger_or_ancestors_have_handler(
                log,
                use_parent_handlers,
                handler_class,
                target_stream=target_stream,
            )
        ) or (filter_type is not None and logger_has_filter(log, filter_type))
        
        if handler_exists:
            continue
        
        installer()
