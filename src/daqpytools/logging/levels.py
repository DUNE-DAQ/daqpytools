import logging
from typing import Literal

# Define logging levels mapping
logging_log_levels = {
    "CRITICAL": logging.CRITICAL,  # 50
    "ERROR": logging.ERROR,  # 40
    "WARNING": logging.WARNING,  # 30
    "INFO": logging.INFO,  # 20
    "DEBUG": logging.DEBUG,  # 10
    "NOTSET": logging.NOTSET,  # 0
}
logging_log_level_keys = list(logging_log_levels.keys())
logging_log_level_values = list(logging_log_levels.values())
logging_methods = Literal["debug", "info", "warning", "error", "critical", "exception"]


# Convert logging log levels to the declared types
def logging_log_level_to_int(log_level: str | int) -> int:
    """Set up the logging level based on the provided string or integer.
    
    Args:
        log_level (str | int): The log level as a string or integer.
    
    Returns:
        int: The log level as an integer.

    Raises:
        ValueError: If the provided log level is not recognized.
        TypeError: If the provided log level is neither a string nor an integer.
    """
    if isinstance(log_level, str):
        log_level = log_level.upper()
        if log_level not in logging_log_level_keys:
            err_msg = (
                f"Level '{log_level}' is not from the recognized logging levels "
                f"{logging_log_level_keys}."
            )
            raise ValueError(err_msg) from None
        return logging_log_levels[log_level]
    if isinstance(log_level, int):
        if log_level not in logging_log_level_values:
            err_msg = (
                f"Level '{log_level}' is not from the recognized logging level values "
                f"{logging_log_level_values}."
            )
            raise ValueError(err_msg) from None
        return log_level
    err_msg = (
        "Log level must be a string or an integer. "
        f"Received type {type(log_level).__name__}."
    )
    raise TypeError(err_msg) from None


def logging_log_level_to_str(log_level: str | int) -> str:
    """Convert a logging level to its string representation.
    
    Args:
        log_level (str | int): The log level as a string or integer.

    Returns:
        str: The log level as a string.

    Raises:
        ValueError: If the provided log level is not recognized.
        TypeError: If the provided log level is neither a string nor an integer.
    """
    if isinstance(log_level, str):
        log_level = log_level.upper()
        if log_level not in logging_log_level_keys:
            err_msg = (
                f"Level '{log_level}' is not from the recognized logging levels "
                f"{logging_log_level_keys}."
            )
            raise ValueError(err_msg) from None
        return log_level
    if isinstance(log_level, int):
        if log_level not in logging_log_level_values:
            err_msg = (
                f"Level '{log_level}' is not from the recognized logging level values "
                f"{logging_log_level_values}."
            )
            raise ValueError(err_msg) from None
        return logging.getLevelName(log_level)
    err_msg = (
        "Log level must be a string or an integer. "
        f"Received type {type(log_level).__name__}."
    )
    raise TypeError(err_msg) from None


# OKS log levels mapping
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


def oks_log_level_to_int(log_level: str | int) -> int:
    """Convert the log level to the equivalent level in python logging as an int.
    Requires discussion about the mapping of OKS log levels to python logging levels.

    Args:
        log_level (str | int): The log level in OKS format (string or int).

    Returns:
        int: The equivalent log level in python logging format.

    Raises:
        ValueError: If the provided log level is not recognized.
        TypeError: If the provided log level is neither a string nor an integer.
    """
    if isinstance(log_level, str):
        if log_level not in oks_log_level_keys:
            err_msg = (
                f"Level '{log_level}' is not from the recognized OKS levels "
                f"({oks_log_level_keys})."
            )
            raise ValueError(err_msg) from None
        return logging_log_levels[oks_to_logging_map[log_level]]
    if isinstance(log_level, int):
        if log_level not in oks_log_level_values:
            err_msg = (
                f"Level '{log_level}' is not from the recognized OKS values "
                f"({oks_log_level_values})."
            )
            raise ValueError(err_msg) from None
        oks_level_name: str = next(
            k for k, v in oks_log_levels.items() if v == log_level
        )
        return logging_log_levels[oks_to_logging_map[oks_level_name]]
    err_msg = (
        "Log level must be a string or an integer. "
        f"Received type {type(log_level).__name__}."
    )
    raise TypeError(err_msg) from None


def oks_log_level_to_str(log_level: str | int) -> str:
    """Convert the log level to the equivalent level in python logging as a str.
    Requires discussion about the mapping of OKS log levels to python logging levels.

    Args:
        log_level (str | int): The log level in OKS format (string or int).

    Returns:
        str: The equivalent log level in python logging format.

    Raises:
        ValueError: If the provided log level is not recognized.
        TypeError: If the provided log level is neither a string nor an integer.
    """
    if isinstance(log_level, str):
        if log_level not in oks_log_level_keys:
            err_msg = (
                f"Level '{log_level}' is not from the recognized OKS levels "
                f"({oks_log_level_keys})."
            )
            raise ValueError(err_msg) from None
        return oks_to_logging_map[log_level]
    if isinstance(log_level, int):
        if log_level not in oks_log_level_values:
            err_msg = (
                f"Level '{log_level}' is not from the recognized OKS values "
                f"({oks_log_level_values})."
            )
            raise ValueError(err_msg) from None
        oks_level_name: str = next(
            k for k, v in oks_log_levels.items() if v == log_level
        )
        return oks_to_logging_map[oks_level_name]
    err_msg = (
        "Log level must be a string or an integer. "
        f"Received type {type(log_level).__name__}."
    )
    raise TypeError(err_msg) from None


# Combine logging and OKS log level keys and values
log_level_keys = logging_log_level_keys + oks_log_level_keys
log_level_values = logging_log_level_values + logging_log_level_values
