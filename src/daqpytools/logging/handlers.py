from __future__ import annotations

import copy
import io
import logging
import os
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import Lock
from typing import ClassVar, cast

from erskafka.ERSKafkaLogHandler import ERSKafkaLogHandler
from rich.console import Console, ConsoleRenderable
from rich.logging import RichHandler
from rich.text import Text

from daqpytools.logging.exceptions import (
    ERSEnvError,
    LoggerHandlerError,
    ProtobufFormatError,
)
from daqpytools.logging.formatter import (
    CONSOLE_THEME,
    DATE_TIME_BASE_FORMAT,
    DATE_TIME_FORMAT,
    LOG_RECORD_PADDING,
    TIME_ZONE,
    LoggingFormatter,
)
from daqpytools.logging.levels import level_to_ers_var, logging_log_level_to_str
from daqpytools.logging.utils import get_width


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
        """Render the log record into a rich Text object with custom formatting.

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
        """Get the style string for the given log level number from the theme defined in
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

# Initialise a logger to catch erstrace + other unknown handlertypes from OKS
log: logging.Logger = logging.getLogger(__name__)
log.addHandler(FormattedRichHandler(width=get_width()))
log.setLevel("INFO")


class StreamType(Enum):
    """Enumtype to classify the set of relevant handlers (i.e streams)."""
    BASE="base"
    OPMON="opmon"
    ERS="ers"

@dataclass 
class ProtobufConf:
    """Dataclass to hold Protobuf Configuration."""
    url:str= "monkafka.cern.ch"
    port:int= 30092

    def get_string(self) -> str:
        """Converts back to string version."""
        return f"{self.url}:{self.port}"

class HandlerType(Enum):
    """Enumtype to classify the existing set of Handlers.
    Values must match exactly what is given in the OKS configuration, if any
    All are in lowercase.
    """
    Unknown = "unknown"
    Stream = "stream"
    Rich = "rich"
    File = "file"
    Protobufstream = "protobufstream"
    Lstdout = "lstdout"
    Lstderr = "lstderr"
    Throttle = "throttle"
    @classmethod
    def from_string(cls, s: str) -> HandlerType | None:
        """Converts from a case-independent string to HandlerType."""
        try:
            return HandlerType(s.lower())
        except ValueError:
            msg=f"[red]{s}[/red] is not a known handler type"
            log.warning(msg)
            return None


@dataclass
class ERSPyLogHandlerConf:
    """Dataclass that holds the relevant ERS configuration from OKS.

    As an example, given the following
    <obj class="Variable" id="ehn1-env-ers-error">
        <attr name="name" type="string" val="DUNEDAQ_ERS_ERROR"/>
        <attr name="value" type="string" val="erstrace,throttle,lstdout,
            protobufstream(monkafka.cern.ch:30092)"/>
    </obj>

    This dataclass holds the list of relevant Handlers attached to the ERS log level. 
    In case it also contains a single protobuf handler, the configuration is stored by 
    the ProtobufConf instance. Multiple protobuf handlers with different url/ports 
    are not yet supported.
    """
    handlers: list = field(default_factory = lambda: [])
    protobufconf: ProtobufConf = field(default_factory = lambda: None)

@dataclass
class LogHandlerConf:
    """Dataclass that holds the various streams and relevant handlers.
    
    Attributes:
        init_ers: If True, automatically initializes ERS configuration 
            during construction.
        _BASE_HANDLERS: Private class variable for default base handlers
        _OPMON_HANDLERS: Private class variable for opmon handlers
        BASE_CONFIG: Class variable for base stream configuration
        OPMON_CONFIG: Class variable for opmon stream configuration
        ERS: Instance field for ERS configuration (loaded from environment)
    """
    init_ers: bool = False

    _BASE_HANDLERS: ClassVar[set] = {HandlerType.Stream, HandlerType.Rich,
        HandlerType.File
        }
    _OPMON_HANDLERS: ClassVar[set] = {HandlerType.Rich, HandlerType.Stream,
        HandlerType.File}
    _ERS: object = None
    
    Base: ClassVar[dict] = {
        "handlers": _BASE_HANDLERS,
        "stream": StreamType.BASE
    }
    
    Opmon: ClassVar[dict] = {
        "handlers": _OPMON_HANDLERS,
        "stream": StreamType.OPMON
    }

    def __post_init__(self) -> None:
        """Initialize ERS configuration if init_ers field is True.

        This method is called automatically after dataclass initialization.
        If the init_ers attribute was set to True, it triggers the complete
        ERS initialization.
        """
        if self.init_ers:
            self.init_ers_stream()

    @property
    def ERS(self) -> dict : # noqa: N802
        """Get the ERS configuration dictionary.
        
        Returns:
            dict: Contains 'ers_handlers' and 'stream' configuration for ERS
            
        Raises:
            AttributeError: If ERS has not been
                initialized (call init_ers_stream() first)
        """
        if not self._ERS:
            err_msg = "ERS stream not initialised. Call init_ers_stream() first"
            raise AttributeError(err_msg)
        return self._ERS

    def init_ers_stream(self) -> None:
        """Initialize ERS configuration from environment variables.
        
        Loads ERS configuration from OKS environment variables and populates
        the _ERS dict with handlers and stream information.
        
        Called automatically during construction if init_ers=True, or can be
        called manually afterwards.
        """
        self._ERS = {
            "ers_handlers":  LogHandlerConf._get_oks_conf(),
            "stream": StreamType.ERS
        }   

    @staticmethod
    def _convert_str_to_handlertype(handler_str: str) -> tuple[HandlerType,
        ProtobufConf | None]:
        """Parses a given environment variable to obtain the
        HandlerType and ProtobufConf as necessary. 

        Eg. converts "throttle" to HandlerType.Throttle
            converts "protobufstream(url:port)" to return both the HandlerType and the 
            protobuf configuration
        """
        # print(f"{handler_str=}")
        if "erstrace" in handler_str:
            msg = (
                "ERSTrace is a C++ implementation, "
                "does not have an equivalent in Python"
            )
            log.debug(msg)
            return None, None

        if HandlerType.Protobufstream.value not in handler_str:
            return HandlerType.from_string(handler_str), None

        match = re.search(r"\(([^:]+):(\d+)\)", handler_str)
        if not match:
            raise ProtobufFormatError(handler_str)
        url, port = match.group(1), int(match.group(2))
        return HandlerType.Protobufstream, ProtobufConf(url=url, port=port)

    @staticmethod
    def _make_ers_handler_conf(ers_log_level :str) -> ERSPyLogHandlerConf:
        """Generates the ERSPyLogHandlerConf from reading an environment variable."""
        erspyloghandlerconf = ERSPyLogHandlerConf()
        envvalue = os.getenv(ers_log_level)
        # print(f"{envvalue=}")
        if envvalue is None:
            raise ERSEnvError(ers_log_level)
        
        for h in envvalue.split(","):
            # print(f"{h=}")
            handlertype, kafkaconf = LogHandlerConf._convert_str_to_handlertype(h)
            erspyloghandlerconf.handlers.append(handlertype)
            if kafkaconf:
                erspyloghandlerconf.protobufconf = kafkaconf 
        return erspyloghandlerconf

    @staticmethod
    def _get_oks_conf() -> dict:
        """From the set of known environment variables, generate the ERS conf dict."""
        return {var: LogHandlerConf._make_ers_handler_conf(var) 
            for var in list(level_to_ers_var.values())}
    
    @staticmethod
    def get_base() -> set[HandlerType]:
        """Returns the default list of handlers from
        LogHandlerConf._BASE_HANDLERS without having to initialise an instance.
        """
        return LogHandlerConf._BASE_HANDLERS

class IssueRecord:
    """Tracks throttling state for a unique issue (identified by file: line)."""
    
    def __init__(self) -> None:
        """C'tor."""
        self.reset()
    
    def reset(self) -> None:
        """Reset all counters and timestamps."""
        self.last_occurrence:  float = 0.0
        self.last_report: float = 0.0
        self.initial_counter: int = 0
        self.threshold:  int = 10
        self.suppressed_counter: int = 0
        self.last_occurrence_formatted: str = ""


class BaseHandlerFilter(logging.Filter):
    """Base filter that hold the logic on choosing if a handler should emit
    based on what HandlersTypes are supplied to it.
    """
    def __init__(self) -> None:
        """C'tor."""
        super().__init__()
    
    def get_allowed(self, record: logging.LogRecord) -> list | None:
        """Parses the record to obtain the set of Handlers that allows transmission."""
        # TODO/future: kafkaprotobufs should validate url/port match before transmitting
        
        # Handle the ERS case, requires more processing
        if getattr(record, "stream", None) == StreamType.ERS:
            # Chain None checks using walrus operator
            if (
                # Checks if python log level has an ERS severity level match
                (ers_level_var := level_to_ers_var.get(record.levelno)) is None
                # Checks if ers_handlers (specifically for ERS) is supplied by the msg
                or (ers_handlers := getattr(record, "ers_handlers", None)) is None
                # _Assigns_ the relevant ERS handler conf from supplied level
                or (ershandlerconf := ers_handlers.get(ers_level_var)) is None
            ):
                return None
            
            allowed = ershandlerconf.handlers


        # Handle the non-ERS case
        else:
            allowed = getattr(record, "handlers", LogHandlerConf.get_base()) 
        return allowed
        
class HandleIDFilter(BaseHandlerFilter):
    """Filter class that accepts a list of 'allowed' handlers and will only fire
    if the current handler (defined by the handler_id) is within the set of 
    allowed handlers.
    """
    def __init__(self, handler_id: HandlerType | list[HandlerType]) -> None:
        """Initialises HandleIDFilter with the handler_id, to identify what
        kind of handler this filter is.
        """
        super().__init__()
        
        # Normalise handler_id to be a set
        if isinstance(handler_id, list):
            self.handler_ids = set(handler_id)
        else:
            self.handler_ids = {handler_id}
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Identifies when a log message should be transmitted or not."""
        if not (allowed:= self.get_allowed(record)):
            return False
        return bool(self.handler_ids & set(allowed))

class ThrottleFilter(BaseHandlerFilter):
    """Advanced logging filter with escalating throttle thresholds.
    
    Args:
        initial_threshold: Number of initial occurrences 
            to let through immediately (default: 30)
        time_limit: Time window in seconds for resetting state (default: 30)
        name: Optional filter name
    
    Example:
        >>> import logging
        >>> logger = logging.getLogger(__name__)
        >>> throttle = ThrottleFilter(initial_threshold=30, time_limit=30)
        >>> logger.addFilter(throttle)
        >>> handler = logging.StreamHandler()
        >>> logger.addHandler(handler)
        >>> logger.setLevel(logging. ERROR)
        >>> 
        >>> # First 30 messages go through immediately
        >>> for i in range(100):
        ...     logger.error("Repeated error message")
    """
    
    def __init__(self, initial_threshold: int = 30, time_limit:  int = 30) -> None:
        """C'tor."""
        super().__init__()
        self.initial_threshold = initial_threshold
        self.time_limit = time_limit
        self.issue_map: dict[str, IssueRecord] = defaultdict(IssueRecord)
        self.mutex = Lock() # Ensures thread safety
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Determine if a log record should be emitted.
        
        Args:
            record: The log record to filter
            
        Returns:
            True if the record should be logged, False to suppress it
        """
        # Check if we want to apply the filter
        if not (allowed:= self.get_allowed(record)):
            return False
        if HandlerType.Throttle not in allowed:
            return True
        
        # Used to bypass the filter to report suppression messages
        if getattr(record, '_throttle_suppression', False):
            return True
        
        issue_id = f"{record.pathname}:{record.lineno}"
        with self.mutex:
            issue_record = self.issue_map[issue_id]
            return self._throttle(issue_record, record)
    
    def _throttle(self, rec: IssueRecord, record:  logging.LogRecord) -> bool:
        """Apply throttling logic to determine if record should be emitted.
        
        Args:
            rec: The issue record tracking state for this unique issue
            record: The log record being evaluated
            
        Returns:
            True if record should be emitted, False otherwise
        """
        current_time = time.time()
        reported = False
        
        # Step 1: Check if time window expired - reset if so
        if current_time - rec.last_occurrence > self.time_limit:
            if rec.suppressed_counter > 0:
                self._report_suppression(rec, record)
                reported = True
            rec.reset()
        
        # Step 2: Initial phase - let first N messages through
        if rec.initial_counter < self.initial_threshold:
            rec.initial_counter += 1
            rec.last_report = current_time
            rec.last_occurrence = current_time
            rec.last_occurrence_formatted = self._format_timestamp(current_time)
            
            # Don't double-report if we just reported suppression
            return not reported
        
        # Step 3: Check if we hit the escalating threshold
        if rec.suppressed_counter >= rec.threshold:
            rec.threshold = rec.threshold * 10  # Escalate:  10 -> 100 -> 1000 ... 
            rec.last_occurrence = current_time
            rec. last_occurrence_formatted = self._format_timestamp(current_time)
            self._report_suppression(rec, record)
            return False  # Don't emit the original record
        
        # Step 4: Check if enough time passed since last report
        if current_time - rec.last_report > self.time_limit:
            rec.last_occurrence = current_time
            rec. last_occurrence_formatted = self._format_timestamp(current_time)
            self._report_suppression(rec, record)
            return False  # Don't emit the original record
        
        # Step 5: Suppress silently
        rec.suppressed_counter += 1
        rec.last_occurrence = current_time
        rec. last_occurrence_formatted = self._format_timestamp(current_time)
        return False
    
    def _report_suppression(self, rec: IssueRecord, record: logging.LogRecord) -> None:
        """Create and emit a suppression notice.
        
        Args:
            rec: The issue record with suppression count
            record: The original log record (used as template)
        """
        if rec.suppressed_counter == 0:
            return
        
        suppression_record = copy.deepcopy(record)
        suppression_record._throttle_suppression = True # pass through filter to report
        
        # Append suppression information to the message
        suppression_msg = (
            f" -- {rec.suppressed_counter} similar messages suppressed, "
            f"last occurrence was at {rec.last_occurrence_formatted}"
        )
        suppression_record.msg = record.getMessage() + suppression_msg
        suppression_record.args = ()  # Clear args since we already formatted
        
        # Emit directly - will pass through filter due to flag
        logger = logging.getLogger(record.name)
        logger.handle(suppression_record)

        
        # Reset suppression tracking
        rec.last_report = time.time()
        rec.suppressed_counter = 0
    
    @staticmethod
    def _format_timestamp(timestamp: float) -> str:
        """Format timestamp in ISO format with microseconds.
        
        Args:
            timestamp: Unix timestamp
            
        Returns:
            Formatted timestamp string
        """
        dt = datetime.fromtimestamp(timestamp, tz=TIME_ZONE)
        padding: int = LOG_RECORD_PADDING.get("time", 25)
        time_str: str = dt.strftime(DATE_TIME_BASE_FORMAT).ljust(padding)[:padding]
        return Text(time_str, style="logging.time")
    

def add_throttle_filter(log: logging.Logger) -> None:
    """Add the Throttle filter to the logger.

    Args:
        log (logging.Logger): Logger to add the rich handler to.

    Returns:
        None
    """
    log.addFilter(ThrottleFilter())
    return

def check_parent_handlers(
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
        return

    # Check that we are not using the true logging root logger
    python_root_logger_name = logging.getLogger().name
    if log.name == python_root_logger_name:
        err_nsg = "You should not be interfacing with the root logger"
        raise ValueError(err_nsg)
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
    """Add a rich handler to the logger.

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
    handler.addFilter(HandleIDFilter(HandlerType.Rich))
    log.addHandler(handler)
    return
    
def add_ers_kafka_handler(log: logging.Logger, use_parent_handlers: bool,
                                 session_name:str, topic: str = "ers_stream", 
                                 address: str ="monkafka.cern.ch:30092") -> None:
    # TODO/future: topic and address are new, propagate to all relevant implementation
    """Add an ers protobuf handler to the root logger."""
    check_parent_handlers(log, use_parent_handlers, ERSKafkaLogHandler)
    handler: ERSKafkaLogHandler = ERSKafkaLogHandler(session=session_name, 
                                                     kafka_address = address, 
                                                     kafka_topic = topic
                                                     )
    handler.addFilter(HandleIDFilter(HandlerType.Protobufstream))
    log.addHandler(handler)

def add_stdout_handler(log: logging.Logger, use_parent_handlers: bool) -> None:
    """Add a stdout handler to the logger.

    Args:
        log (logging.Logger): Logger to add the stdout handler to.
        use_parent_handlers (bool): Whether to check parent handlers.

    Returns:
        None

    Raises:
        LoggerHandlerError: If a parent logger has a stdout handler.
    """
    check_parent_handlers(
        log,
        use_parent_handlers,
        logging.StreamHandler,
        target_stream=cast(io.IOBase, sys.stdout),
    )
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(LoggingFormatter())
    stdout_handler.addFilter(HandleIDFilter([HandlerType.Stream, HandlerType.Lstdout]))
    log.addHandler(stdout_handler)
    return


def add_stderr_handler(log: logging.Logger, use_parent_handlers: bool) -> None:
    """Add a stderr handler to the logger.

    The error is set to the ERROR level, and will only log messages at that level
    or higher. This is to avoid duplicate logging of error messages when both stdout
    and stderr handlers are used.

    Args:
        log (logging.Logger): Logger to add the stderr handler to.
        use_parent_handlers (bool): Whether to check parent handlers.

    Returns:
        None

    Raises:
        LoggerHandlerError: If a parent logger has a stderr handler.
    """
    check_parent_handlers(
        log,
        use_parent_handlers,
        logging.StreamHandler,
        target_stream=cast(io.IOBase, sys.stderr),
    )
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(LoggingFormatter())
    stderr_handler.addFilter(HandleIDFilter([HandlerType.Stream, HandlerType.Lstderr]))
    stderr_handler.setLevel(logging.ERROR)
    log.addHandler(stderr_handler)
    return


def add_file_handler(log: logging.Logger, use_parent_handlers: bool, path: str) -> None:
    """Add a file handler to the root logger.

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
    file_handler.addFilter(HandleIDFilter(HandlerType.File))
    log.addHandler(file_handler)
    return


def _logger_has_handler(
    log: logging.Logger,
    handler_type: type[logging.Handler],
    target_stream: io.IOBase | None = None,
) -> bool:
    """Check if logger already has a matching handler.

    For StreamHandler, ``target_stream`` can be used to distinguish stdout/stderr.
    """
    type_matches = [isinstance(handler, handler_type) for handler in log.handlers]
    stream_matches = [
        handler.stream is target_stream if target_stream else False
        for handler in log.handlers
        if isinstance(handler, logging.StreamHandler)
    ]
    return any(type_matches + stream_matches)


def _logger_has_filter(log: logging.Logger, filter_type: type[logging.Filter]) -> bool:
    """Check if logger already has a matching filter type."""
    return any(isinstance(logger_filter, filter_type) for logger_filter in log.filters)


def add_handlers_from_types(
    log: logging.Logger,
    handler_types: set[HandlerType],
    ers_session_name: str | None,
) -> None:
    """Add handlers to a logger based on HandlerType values.

    This helper intentionally supports only the default options for now:
    - ``use_parent_handlers`` is always True.
    - ``HandlerType.File`` is not supported and raises immediately.
    - ``HandlerType.Protobufstream`` requires ``ers_session_name``.
    """
    if HandlerType.File in handler_types:
        err_msg = "HandlerType.File is not supported by add_handlers_from_types"
        raise ValueError(err_msg)

    if HandlerType.Protobufstream in handler_types and not ers_session_name:
        err_msg = "ers_session_name is required for HandlerType.Protobufstream"
        raise ValueError(err_msg)

    effective_handler_types = set(handler_types)
    if HandlerType.Stream in effective_handler_types:
        effective_handler_types.update({HandlerType.Lstdout, HandlerType.Lstderr})

    existing_stream_handlers = {
        HandlerType.Lstdout
        if _logger_has_handler(
            log, logging.StreamHandler, target_stream=cast(io.IOBase, sys.stdout)
        )
        else None,
        HandlerType.Lstderr
        if _logger_has_handler(
            log, logging.StreamHandler, target_stream=cast(io.IOBase, sys.stderr)
        )
        else None,
    }
    existing_stream_handlers.discard(None)

    existing_handlers = {
        HandlerType.Rich if _logger_has_handler(log, FormattedRichHandler) else None,
        HandlerType.Protobufstream
        if _logger_has_handler(log, ERSKafkaLogHandler)
        else None,
        HandlerType.Throttle if _logger_has_filter(log, ThrottleFilter) else None,
    }
    existing_handlers.discard(None)
    existing_handlers.update(existing_stream_handlers)

    dispatch = {
        HandlerType.Rich: lambda: add_rich_handler(log, True),
        HandlerType.Lstdout: lambda: add_stdout_handler(log, True),
        HandlerType.Lstderr: lambda: add_stderr_handler(log, True),
        HandlerType.Protobufstream: lambda: add_ers_kafka_handler(
            log, True, ers_session_name
        ),
        HandlerType.Throttle: lambda: add_throttle_filter(log)
    }

    #! Try to revisit this logic

    install_order = [
        HandlerType.Rich,
        HandlerType.Lstdout,
        HandlerType.Lstderr,
        HandlerType.Protobufstream,
        HandlerType.Throttle,
    ]

    for handler_type in install_order:
        if handler_type not in effective_handler_types:
            continue
        if handler_type in existing_handlers:
            continue
        installer = dispatch.get(handler_type)
        if installer is None:
            continue
        installer()

