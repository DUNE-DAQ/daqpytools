import logging

import kafka
import sh
from rich.traceback import install as rich_traceback_install

from daqpytools.logging.exceptions import LoggerSetupError
from daqpytools.logging.handlers import (
    add_file_handler,
    add_rich_handler,
    add_stderr_handler,
    add_stdout_handler,
)
from daqpytools.logging.utils import get_width, log_level_to_int


def validate_setup_configuration(
    logger_name: str, rich_handler: bool, stdout_handler: bool, stderr_handler: bool
) -> None:
    """Checks for one or less stream-type handler associated with the logger."""
    if sum([rich_handler, stdout_handler, stderr_handler]) > 1:
        err_msg = (
            "All instances of rich_handler, stdout_handler, and std_err will log "
            "to the tty, choose one!"
        )
        raise LoggerSetupError(logger_name, err_msg)
    return


def setup_root_logger(name: str, level: int) -> logging.Logger:
    """Set up the base logger from which all other loggers inherit."""
    root_logger = logging.getLogger(name)
    root_logger.setLevel(level)

    sh_command_level = level if level > logging.INFO else (level + 10)
    sh_command_logger = logging.getLogger(sh.__name__)
    sh_command_logger.setLevel(sh_command_level)
    for handler in sh_command_logger.handlers:
        handler.setLevel(sh_command_level)

    kafka_command_level = level if level > logging.INFO else (level + 10)
    kafka_command_logger = logging.getLogger(kafka.__name__)
    kafka_command_logger.setLevel(kafka_command_level)
    for handler in kafka_command_logger.handlers:
        handler.setLevel(kafka_command_level)

    return root_logger


def get_daq_logger(
    logger_name: str,
    log_level: int | str = logging.INFO,
    use_parent_handlers: bool = True,
    rich_handler: bool = False,
    file_handler_path: str | None = None,
    stream_stdout_handler: bool = False,
    stream_stderr_handler: bool = False,
) -> logging.Logger:
    """C'tor."""
    rich_traceback_install(show_locals=True, width=get_width())

    validate_setup_configuration(
        logger_name, rich_handler, stream_stdout_handler, stream_stderr_handler
    )
    log_level = log_level_to_int(log_level)

    root_logger_name: str = logger_name
    logger: logging.Logger = setup_root_logger(name=root_logger_name, level=log_level)
    logger.propagate = use_parent_handlers

    if rich_handler:
        add_rich_handler(logger, use_parent_handlers)
    if file_handler_path:
        add_file_handler(logger, use_parent_handlers, file_handler_path)
    if stream_stdout_handler:
        add_stdout_handler(logger, use_parent_handlers)
    if stream_stderr_handler:
        add_stderr_handler(logger, use_parent_handlers)
    return logger
