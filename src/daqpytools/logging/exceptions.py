import logging
from pathlib import Path


class LoggerHandlerError(Exception):
    """Custom error for attempted duplicate of handler type."""

    def __init__(self, logger_name: str, handler_type: type[logging.Handler]) -> None:
        """C'tor."""
        err_msg = (
            f"One of the parents of {logger_name} already has a handler of type "
            f"{handler_type.__name__}"
        )
        super().__init__(err_msg)


class LoggerSetupError(Exception):
    """Custom error for attempted duplicate of handler type."""

    def __init__(self, logger_name: str, err_msg: str) -> None:
        """C'tor."""
        err_msg = f"Constructing {logger_name} failed as: \n{err_msg}"
        super().__init__(err_msg)


class LoggerConfigurationError(Exception):
    """Custom error for logger configuration issues."""

    def __init__(self, configuration_file_path: str | Path, err_msg: str) -> None:
        """C'tor."""
        err_msg = (
            f"Configuration file '{configuration_file_path}' could not be read or "
            f"contains invalid configuration:\n {err_msg}"
        )
        super().__init__(err_msg)
