import io
import logging
import sys
from datetime import datetime
from typing import cast

from rich.console import Console, ConsoleRenderable
from rich.logging import RichHandler
from rich.text import Text

from daqpytools.logging.exceptions import LoggerHandlerError
from daqpytools.logging.formatter import (
    CONSOLE_THEME,
    DATE_TIME_FORMAT,
    LOG_RECORD_PADDING,
    TIME_ZONE,
    LoggingFormatter,
)
from daqpytools.logging.levels import logging_log_level_to_str
from daqpytools.logging.utils import get_width


def check_parent_handlers(
    log: logging.Logger,
    use_parent_handlers: bool,
    handler_type: type[logging.Handler],
    target_stream: io.IOBase | None = None,
) -> None:
    """
    Check all parent loggers for an instance of the given logging type.
    
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
        return

    # Check that we are not using the true logging root logger
    python_root_logger_name = logging.getLogger().name
    if log.name == python_root_logger_name:
        raise ValueError("You should not be interfacing with the root logger")
    this_is_root_logger = log.name == python_root_logger_name

    # Validate the stream handler has a target stream
    if handler_type.__name__ == "StreamHandler" and target_stream is None:
        raise ValueError(
            "target_stream must be specified when handler_type is StreamHandler"
        )

    # Validate the non-stream handler does not have a target stream
    if handler_type.__name__ != "StreamHandler" and target_stream is not None:
        raise ValueError(
            "target_stream can only be specified when handler_type is StreamHandler"
        )

    logger_parent = log.parent
    this_is_root_logger = logger_parent.name == python_root_logger_name

    while not this_is_root_logger:
        handler_checking = [
            isinstance(handler, handler_type) for handler in logger_parent.handlers
        ]
        stream_handler_checking = [
            handler.stream is target_stream if target_stream else False
            for handler in logger_parent.handlers
            if isinstance(handler, logging.StreamHandler)
        ]
        if any(handler_checking + stream_handler_checking):
            raise LoggerHandlerError(logger_parent.name, handler_type)
        logger_parent = logger_parent.parent
        this_is_root_logger = logger_parent.name == python_root_logger_name
    return


def add_rich_handler(log: logging.Logger, use_parent_handlers: bool) -> None:
    """
    Add a rich handler to the logger.
    
    Args:
        log (logging.Logger): Logger to add the rich handler to.
        use_parent_handlers (bool): Whether to check parent handlers.

    Returns:
        None

    Raises:
        LoggerHandlerError: If a parent logger has a rich handler.
    """
    check_parent_handlers(log, use_parent_handlers, FormattedRichHandler)
    width: int = get_width()
    handler: RichHandler = FormattedRichHandler(width=width)
    log.addHandler(handler)
    return


def add_stdout_handler(log: logging.Logger, use_parent_handlers: bool) -> None:
    """
    Add a stdout handler to the logger.
    
    Args:
        log (logging.Logger): Logger to add the stdout handler to.
        use_parent_handlers (bool): Whether to check parent handlers.

    Returns:
        None

    Raises:
        LoggerHandlerError: If a parent logger has a stdout handler.
    """
    check_parent_handlers(
        log, use_parent_handlers, logging.StreamHandler, target_stream=cast(io.IOBase, sys.stdout)
    )
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(LoggingFormatter())
    log.addHandler(stdout_handler)
    return


def add_stderr_handler(log: logging.Logger, use_parent_handlers: bool) -> None:
    """
    Add a stderr handler to the logger.
    
    Args:
        log (logging.Logger): Logger to add the stderr handler to.
        use_parent_handlers (bool): Whether to check parent handlers.

    Returns:
        None

    Raises:
        LoggerHandlerError: If a parent logger has a stderr handler.
    """
    check_parent_handlers(
        log, use_parent_handlers, logging.StreamHandler, target_stream=cast(io.IOBase, sys.stderr)
    )
    stdout_handler = logging.StreamHandler(sys.stderr)
    stdout_handler.setFormatter(LoggingFormatter())
    log.addHandler(stdout_handler)
    return


def add_file_handler(log: logging.Logger, use_parent_handlers: bool, path: str) -> None:
    """
    Add a file handler to the root logger.
    
    Args:
        log (logging.Logger): Logger to add the file handler to.
        use_parent_handlers (bool): Whether to check parent handlers.
        path (str): Path to the log file.

    Returns:
        None

    Raises:
        LoggerHandlerError: If a parent logger has a file handler.
    """
    check_parent_handlers(log, use_parent_handlers, logging.FileHandler)
    file_handler = logging.FileHandler(filename=path)
    file_handler.setFormatter(LoggingFormatter())
    log.addHandler(file_handler)
    return


class FormattedRichHandler(RichHandler):
    """RichHandler that formats log messages with time, aligned columns, and styles."""

    def __init__(self, width: int = 100) -> None:
        """Initialize with custom console and style settings."""
        console: Console = Console(
            force_terminal=True, width=width, theme=CONSOLE_THEME
        )
        super().__init__(
            console=console,
            omit_repeated_times=False,
            markup=True,
            rich_tracebacks=True,
            show_path=False,
            show_time=False,  # We format time ourselves
        )

    def render(
        self,
        *,
        record: logging.LogRecord,
        traceback: object,
        message_renderable: ConsoleRenderable,
    ) -> Text:
        """
        Render the log record into a rich Text object with custom formatting.
        
        Args:
            record (logging.LogRecord): The log record to render.
            traceback (object): The traceback object (not used here).
            message_renderable (ConsoleRenderable): The log message renderable.

        Returns:
            Text: The formatted log record as a rich Text object.

        Raises:
            None
        """
        dt: datetime = datetime.fromtimestamp(record.created, tz=TIME_ZONE)
        padding: int = LOG_RECORD_PADDING.get("time", 25)
        time_str: str = dt.strftime(DATE_TIME_FORMAT).ljust(padding)[:padding]
        time_text: Text = Text(time_str, style="logging.time")

        padding = LOG_RECORD_PADDING.get("level", 10)
        level_text: Text = Text(
            record.levelname.ljust(padding)[:padding],
            style=self._get_level_style(record.levelno),
        )

        file_and_no: str = f"{record.filename}:{record.lineno}"
        padding = LOG_RECORD_PADDING.get("file_and_line", 40)
        file_and_no_text: Text = Text(
            file_and_no.ljust(padding)[:padding], style="logging.location"
        )

        padding = LOG_RECORD_PADDING.get("logger_name", 45)
        logger_name_text: Text = Text(
            f"{record.name}".ljust(padding)[:padding], style="logging.logger_name"
        )

        # Convert message_renderable to Text for type consistency
        message_text: Text
        if isinstance(message_renderable, Text):
            message_text = message_renderable
        else:
            message_text = Text.from_markup(str(message_renderable))

        components: list[Text] = [
            time_text,
            level_text,
            file_and_no_text,
            logger_name_text,
            message_text,
        ]

        return Text(" ").join(components)

    def _get_level_style(self, level_no: int) -> str:
        """
        Get the style string for the given log level number from the theme defined in
        CONSOLE_THEME.
        
        Args:
            level_no (int): The log level number.

        Returns:
            str: The style string for the log level.
        """
        return str(
            CONSOLE_THEME.styles.get(
                f"logging.level.{logging_log_level_to_str(level_no).lower()}", ""
            )
        )
