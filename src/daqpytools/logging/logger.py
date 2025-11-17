import logging
from logging import PlaceHolder

import kafka
import sh
from rich.traceback import install as rich_traceback_install

from daqpytools.logging.exceptions import LoggerSetupError
from daqpytools.logging.handlers import (
    add_file_handler,
    add_rich_handler,
    add_stderr_handler,
    add_stdout_handler,
    add_ers_protobuf_handler,
)
from daqpytools.logging.levels import logging_log_level_to_int
from daqpytools.logging.utils import get_width


def setup_root_logger(logger_name: str, log_level: int | str) -> logging.Logger:
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
    ers_protobuf_handler: bool = False,
) -> logging.Logger:
    """C'tor for the default logging instances.

    Args:
        logger_name (str): Name of the logger.
        log_level (int | str): Log level for the logger.
        use_parent_handlers (bool): Whether to use parent handlers.
        rich_handler (bool): Whether to add a rich handler.
        file_handler_path (str | None): Path to the file handler log file. If None, no
            file handler is added.
        stream_handlers (bool): Whether to add both stdout and stderr stream handlers.

    Returns:
        logging.Logger: Configured logger instance.

    Raises:
        LoggerSetupError: If the configuration is invalid.

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

    # Add requested handlers
    if rich_handler:
        add_rich_handler(logger, use_parent_handlers)
    if file_handler_path:
        add_file_handler(logger, use_parent_handlers, file_handler_path)
    if stream_handlers:
        add_stdout_handler(logger, use_parent_handlers)
        add_stderr_handler(logger, use_parent_handlers)
    if ers_protobuf_handler: 
        add_ers_protobuf_handler(logger, use_parent_handlers, "session_temporary") #! Change name

    # Set log level for all handlers if requested
    if log_level is not logging.NOTSET:
        for handler in logger.handlers:
            handler.setLevel(log_level)

    return logger
