import logging
from typing import Literal

logging_log_levels = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
    "NOTSET": logging.NOTSET,
}
logging_log_level_keys = list(logging_log_levels.keys())
logging_log_level_values = list(logging_log_levels.values())
logging_methods = Literal["debug", "info", "warning", "error", "critical", "exception"]


def log_level_to_int(log_level: str | int) -> int:
    """Set up the logging level based on the provided string or integer."""
    if isinstance(log_level, str):
        if log_level not in logging_log_level_keys:
            err_msg = (
                f"Log level {log_level} not recognized. Please use one of "
                f"{', '.join(logging_log_level_keys)}."
            )
            raise ValueError(err_msg) from None
        return logging_log_levels[log_level]
    if isinstance(log_level, int):
        if log_level not in logging_log_level_values:
            err_msg = (
                f"Log level {log_level} not recognized. Please use one of "
                f"{', '.join(map(str, logging_log_level_values))}."
            )
            raise ValueError(err_msg) from None
        return log_level
    err_msg = (
        "Log level must be a string or an integer. "
        f"Received type {type(log_level).__name__}."
    )
    raise TypeError(err_msg) from None


def log_level_to_str(log_level: str | int) -> str:
    """Convert a logging level to its string representation."""
    if isinstance(log_level, str):
        if log_level not in logging_log_level_keys:
            err_msg = (
                f"Log level {log_level} not recognized. Please use one of "
                f"{', '.join(logging_log_level_keys)}."
            )
            raise ValueError(err_msg) from None
        return log_level
    if isinstance(log_level, int):
        if log_level not in logging_log_level_values:
            err_msg = (
                f"Log level {log_level} not recognized. Please use one of "
                f"{', '.join(map(str, logging_log_level_values))}."
            )
            raise ValueError(err_msg) from None
        return logging.getLevelName(log_level)
    err_msg = (
        "Log level must be a string or an integer. "
        f"Received type {type(log_level).__name__}."
    )
    raise TypeError(err_msg) from None


oks_log_levels = {
    "kTopPriority": 0,
    "kEventDriven": 1073741824,
    "kDefault": 2147483648,
    "kLowestPriority": 4294967295,
}

oks_log_level_keys = list(oks_log_levels.keys())
oks_log_level_values = list(oks_log_levels.values())

oks_to_logging_map = {
    "kTopPriority": "ERROR",
    "kEventDriven": "WARNING",
    "kDefault": "INFO",
    "kLowestPriority": "DEBUG",
}

log_level_keys = logging_log_level_keys + oks_log_level_keys
log_level_values = logging_log_level_values + logging_log_level_values
