import logging
import sys
from logging import PlaceHolder

import kafka
import sh
from rich.traceback import install as rich_traceback_install

from daqpytools.logging.exceptions import LoggerSetupError
from daqpytools.logging.handlerconf import HandlerType, LogHandlerConf
from daqpytools.logging.handlers import (
    add_handlers_from_types,
)
from daqpytools.logging.levels import logging_log_level_to_int
from daqpytools.logging.utils import get_width


def setup_root_logger(
    logger_name: str, log_level: int | str = logging.INFO
) -> logging.Logger:
    """Set up the base logger from which all other loggers inherit.
    The remaining sh* and kafka* loggers are set to a higher log level to avoid
    excessive logging output.

    Args:
        logger_name (str): Name of the root logger.
        log_level (int | str): Log level for the root logger.

    Returns:
        logging.Logger: Configured root logger instance.
    """
    # Convert level to int if it's a string
    if isinstance(log_level, str):
        log_level = logging_log_level_to_int(log_level)

    # Set up the root logger
    root_logger = logging.getLogger(logger_name)
    root_logger.setLevel(log_level)

    # Validate the root logger has zero handlers
    if len(root_logger.handlers) != 0:
        err_msg = (
            f"Root logger '{logger_name}' already has handlers configured. "
            "Please use a different logger name."
        )
        raise LoggerSetupError(logger_name, err_msg)

    sh_command_level = log_level if log_level > logging.INFO else (log_level + 10)
    sh_command_logger = logging.getLogger(sh.__name__)
    sh_command_logger.setLevel(sh_command_level)
    for handler in sh_command_logger.handlers:
        handler.setLevel(sh_command_level)

    kafka_command_level = log_level if log_level > logging.INFO else (log_level + 10)
    kafka_command_logger = logging.getLogger(kafka.__name__)
    kafka_command_logger.setLevel(kafka_command_level)
    for handler in kafka_command_logger.handlers:
        handler.setLevel(kafka_command_level)

    return root_logger


def get_daq_logger(
    logger_name: str,
    log_level: int | str = logging.NOTSET,
    use_parent_handlers: bool = True,
    rich_handler: bool = False,
    file_handler_path: str | None = None,
    stream_handlers: bool = False,
    ers_kafka_session: str | None = None,
    throttle: bool = False,
    **extras: object
) -> logging.Logger:
    """Create or reuse a configured DAQ logger.

    Handler/filter installation is driven by selected flags and resolved through
    the handler/filter registries. Additional keyword arguments are forwarded to
    the underlying factory functions.

    Args:
        logger_name: Name of the logger to create or retrieve.
        log_level: Logging level for the logger and its non-stderr handlers.
        use_parent_handlers: If ``True``, logger propagation remains enabled.
        rich_handler: Enable ``HandlerType.Rich``.
        file_handler_path: Optional file path enabling ``HandlerType.File``.
        stream_handlers: Enable ``HandlerType.Stream`` (stdout + stderr specs).
        ers_kafka_session: Optional ERS session enabling
            ``HandlerType.Protobufstream``.
        throttle: Enable ``HandlerType.Throttle`` filter installation.
        **extras: Additional keyword arguments forwarded to handler/filter
            factories via ``add_handlers_from_types(..., **extras)``.

            Common forwarded kwargs include:
            - ``width`` -> ``_build_rich_handler``
            - ``path`` -> ``_build_file_handler`` (internally mapped from
              ``file_handler_path``)
            - ``session_name`` -> ``_build_erskafka_handler`` (internally mapped
              from ``ers_kafka_session``)
            - ``topic``, ``address``, ``ers_app_name`` ->
              ``_build_erskafka_handler``
            - ``initial_treshold``, ``time_limit`` ->
              ``_build_throttle_filter``

            Unsupported kwargs may be ignored by factories that accept ``**_``.

    Returns:
        Configured ``logging.Logger`` instance.

    Raises:
        LoggerSetupError: If a logger with the same name already exists but
            with a conflicting handler configuration.
    """
    rich_traceback_install(show_locals=True, width=get_width())

    # Check if the logger exists with the requested handlers. If different handlers are
    # requested, an exception is raised.
    existing_loggers = logging.root.manager.loggerDict
    if logger_name in existing_loggers:
        existing_logger = existing_loggers[logger_name]

        # If the logger is a placeholder, then a child was initialised before the
        # current parent. Eg. root.parent.child was called before root.parent,
        # and now root.parent is being initialised. If this is the case,
        # then root.parent is a placeholder, and should be initialised as normal
        if not isinstance(existing_logger, PlaceHolder):
            existing_logger_handlers = [
                type(handler).__name__ for handler in existing_logger.handlers
            ]
            rich_handler_valid = (
                "FormattedRichHandler" in existing_logger_handlers
            ) == rich_handler
            file_handler_valid = ("FileHandler" in existing_logger_handlers) == (
                file_handler_path is not None
            )
            stream_handler_valid = (
                "StreamHandler" in existing_logger_handlers
            ) == stream_handlers
            if not all([rich_handler_valid, file_handler_valid, stream_handler_valid]):
                err_msg = (
                    f"Logger '{logger_name}' already exists with different handler "
                    "configuration. Please use a different logger name or adjust the "
                    "handler configuration. Valid checks are: "
                    f"Rich : {rich_handler_valid}, file: {file_handler_valid}, "
                    f"stream: {stream_handler_valid}"
                )
                raise LoggerSetupError(logger_name, err_msg)
            return existing_logger

    # Set up the logger
    log_level = logging_log_level_to_int(log_level)
    logger: logging.Logger = logging.getLogger(logger_name)

    # Set log level only if specifically required
    # If not, rely on inheritance
    if log_level is not logging.NOTSET:
        logger.setLevel(log_level)
    logger.propagate = use_parent_handlers

    fallback_handlers: set[HandlerType] = set()
    if rich_handler:
        fallback_handlers.add(HandlerType.Rich)
    if file_handler_path:
        fallback_handlers.add(HandlerType.File)
    if stream_handlers:
        fallback_handlers.add(HandlerType.Stream)
    if ers_kafka_session:
        fallback_handlers.add(HandlerType.Protobufstream)
    if throttle:
        fallback_handlers.add(HandlerType.Throttle)

    add_handlers_from_types(
        logger,
        fallback_handlers,
        use_parent_handlers,
        fallback_handlers,
        path=file_handler_path,
        session_name=ers_kafka_session,
        **extras
    )

    # Set log level for all handlers if requested
    if log_level is not logging.NOTSET:
        for handler in logger.handlers:
            # Ignore stderr handler resets, needs to be fixed at the error level
            if (isinstance(handler, logging.StreamHandler)
                and handler.stream == sys.stderr):
                continue
            handler.setLevel(log_level)

    return logger


def setup_daq_ers_logger(
    logger: logging.Logger,
    ers_kafka_session: str,
    ers_app_name : str | None = None
) -> None:
    """Configure logger handlers from ERS environment-derived configuration.

    Args:
        logger (logging.Logger): Logger to configure.
        ers_kafka_session (str): ERS session name used for protobufstream handler.
        ers_app_name (str | None): Optional ERS application name for kafka handler.

    Returns:
        None
    """
    oks_conf = LogHandlerConf._get_oks_conf()

    protobuf_configs = {
        handler_conf.protobufconf
        for handler_conf in oks_conf.values()
        if handler_conf.protobufconf is not None
    }

    if len(protobuf_configs) > 1:
        err_msg = (
            "Multiple protobufstream(url:port) configurations are not supported "
            "in Python ERS logger setup"
        )
        raise ValueError(err_msg)

    protobuf_config = next(iter(protobuf_configs), None)
    kafka_address = protobuf_config.get_string() if protobuf_config else None

    all_handlers = {
        handler
        for handler_conf in oks_conf.values()
        for handler in handler_conf.handlers
        if handler is not None
    }

    add_ers_kwargs = {
        "session_name": ers_kafka_session,
        "ers_app_name": ers_app_name,
    }
    if kafka_address is not None:
        add_ers_kwargs["address"] = kafka_address

    add_handlers_from_types(
        logger,
        all_handlers,
        use_parent_handlers=True,
        fallback_handlers={HandlerType.Unknown},
        **add_ers_kwargs,
    )