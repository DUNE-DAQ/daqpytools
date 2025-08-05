import os

from daqpytools.logging.exceptions import LogLevelError
from daqpytools.logging.levels import (
    logging_log_levels,
    oks_log_levels,
    oks_to_logging_map,
)


def log_level_to_int(level: str | int) -> int:
    """Convert the log level to the equivalent level in python logging as an int.
    Requires discussion about the mapping of OKS log levels to python logging levels.
    """
    if isinstance(level, int):
        if level in oks_log_levels.values():
            oks_level_name: str = next(
                k for k, v in oks_log_levels.items() if v == level
            )
            return logging_log_levels[oks_to_logging_map[oks_level_name]]
        if level in logging_log_levels.values():
            return level
    elif isinstance(level, str):
        if level in oks_log_levels.keys():
            return logging_log_levels[oks_to_logging_map[level]]
        if level.upper() in logging_log_levels.keys():
            return logging_log_levels[level.upper()]
    raise LogLevelError(level)


def get_width() -> int:
    """Get the width of the terminal."""
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 100
