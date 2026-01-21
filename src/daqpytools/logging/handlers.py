from __future__ import annotations

import io
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import ClassVar, cast, Dict, Optional

import time
from collections import defaultdict
from threading import Lock

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
    DATE_TIME_FORMAT,
    LOG_RECORD_PADDING,
    TIME_ZONE,
    LoggingFormatter,
)
from daqpytools.logging.levels import level_to_ers_var, logging_log_level_to_str
from daqpytools.logging.utils import get_width


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
    ERSTrace = "erstrace"
    Throttle = "throttle"

    @classmethod
    def from_string(cls, s: str) -> HandlerType:
        """Converts from a case-independent string to HandlerType."""
        return HandlerType(s.lower())


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
    protobufconf: ProtobufConf = field(default_factory = lambda: ProtobufConf())

@dataclass
class LogHandlerConf:
    """Dataclass that holds the various streams and relevant handlers.
    
    Attributes:
        _BASE_HANDLERS: Private class variable for default base handlers
        _OPMON_HANDLERS: Private class variable for opmon handlers
        BASE_CONFIG: Class variable for base stream configuration
        OPMON_CONFIG: Class variable for opmon stream configuration
        ERS: Instance field for ERS configuration (loaded from environment)
    """

    _BASE_HANDLERS: ClassVar[set] = {HandlerType.Stream, HandlerType.Rich,
        HandlerType.File
        }
    _OPMON_HANDLERS: ClassVar[set] = {HandlerType.Rich, HandlerType.Stream,
        HandlerType.File}
    
    Base: ClassVar[dict] = {
        "handlers": _BASE_HANDLERS,
        "stream": StreamType.BASE
    }
    
    Opmon: ClassVar[dict] = {
        "handlers": _OPMON_HANDLERS,
        "stream": StreamType.OPMON
    }

    ERS: dict=field(default_factory = lambda:
    {
        "ers_handlers":  LogHandlerConf._get_oks_conf(),
        "stream": StreamType.ERS
    }
    )

    @staticmethod
    def _convert_str_to_handlertype(handler_str: str) -> tuple[HandlerType,
        ProtobufConf | None]:
        """Parses a given environment variable to obtain the
        HandlerType and ProtobufConf as necessary. 

        Eg. converts "throttle" to HandlerType.Throttle
            converts "protobufstream(url:port)" to return both the HandlerType and the 
            protobuf configuration
        """
        if "protobufstream" not in handler_str:
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
        if envvalue is None:
            raise ERSEnvError(ers_log_level)
        
        for h in envvalue.split(","):
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

class ThrottleFilterFake(logging.Filter):
    """
    """
    # Needs to be able to accept arguments as it gets iinitialised
    # Needs to be added to each of the relevant log handlers
    # needs to do nothing unless the extra arggument contains the throttle thing
    # see the copilot code for the output

    def __init__(self):
        super().__init__()
    
    def filter(self,record):
        issue_id = f"{record.pathname}:{record.lineno}"
        print(issue_id)
        return True


class IssueRecord:
    """Tracks throttling state for a unique issue (identified by file: line)."""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset all counters and timestamps."""
        self.last_occurrence:  float = 0.0
        self.last_report: float = 0.0
        self.initial_counter: int = 0
        self.threshold:  int = 10
        self.suppressed_counter: int = 0
        self.last_occurrence_formatted: str = ""




class BaseHandlerFilter(logging.Filter):
    def __init__(self):
        super().__init__()
    
    def get_allowed(self, record) -> list | None:
        # TODO/future: kafka protobufs should validate url/port match before transmitting
        
        # Handle the ERS case, requires more processing
        if getattr(record, "stream", None) == StreamType.ERS:
            #TODO/ask: See if we want to define this mapping elsewhere

            # Chain None checks using walrus operator
            if (
                (ers_level_var := level_to_ers_var.get(record.levelname)) is None
                or (ers_handlers := getattr(record, "ers_handlers", None)) is None
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
    allowed handlers
    """
    
    def __init__(self, handler_id:HandlerType):
        """Initialises HandleIDFilter with the handler_id, to identify what
        kind of handler this filter is.
        """
        super().__init__()
        self.handler_id = handler_id
    
    def filter(self, record):
        """Identifies when a log message should be transmitted or not."""
        allowed = self.get_allowed(record)
        if not allowed:
            return False
        return self.handler_id in allowed



class ThrottleFilter(BaseHandlerFilter):
    """
    Advanced logging filter with escalating throttle thresholds.
    
    Args:
        initial_threshold: Number of initial occurrences to let through immediately (default: 30)
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
    
    def __init__(self, initial_threshold: int = 30, time_limit:  int = 30):
        super().__init__()
        self.initial_threshold = initial_threshold
        self.time_limit = time_limit
        self.issue_map: Dict[str, IssueRecord] = defaultdict(IssueRecord)
        self.mutex = Lock()
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Determine if a log record should be emitted.
        
        Args:
            record: The log record to filter
            
        Returns:
            True if the record should be logged, False to suppress it
        """
        # Check if we want to apply the filter
        if HandlerType.Throttle not in self.get_allowed(record):
            return True
        
        # Create unique issue ID from file path and line number
        issue_id = f"{record.pathname}:{record.lineno}"
    
        with self.mutex:
            issue_record = self.issue_map[issue_id]
            return self._throttle(issue_record, record)
    
    def _throttle(self, rec: IssueRecord, record:  logging.LogRecord) -> bool:
        """
        Apply throttling logic to determine if record should be emitted.
        
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
        elif rec.suppressed_counter >= rec.threshold:
            rec.threshold = rec.threshold * 10  # Escalate:  10 -> 100 -> 1000 ... 
            rec.last_occurrence = current_time
            rec. last_occurrence_formatted = self._format_timestamp(current_time)
            self._report_suppression(rec, record)
            return False  # Don't emit the original record
        
        # Step 4: Check if enough time passed since last report
        elif current_time - rec.last_report > self.time_limit:
            rec.last_occurrence = current_time
            rec. last_occurrence_formatted = self._format_timestamp(current_time)
            self._report_suppression(rec, record)
            return False  # Don't emit the original record
        
        # Step 5: Suppress silently
        else:
            rec.suppressed_counter += 1
            rec.last_occurrence = current_time
            rec. last_occurrence_formatted = self._format_timestamp(current_time)
            return False
    
    def _report_suppression(self, rec: IssueRecord, record: logging.LogRecord):
        """
        Create and emit a suppression notice.
        
        Args:
            rec: The issue record with suppression count
            record: The original log record (used as template)
        """
        if rec.suppressed_counter == 0:
            return
        
        # Create a new log record for the suppression notice
        suppression_record = logging.LogRecord(
            name=record.name,
            level=record.levelno,
            pathname=record.pathname,
            lineno=record.lineno,
            msg=record.msg,
            args=record.args,
            exc_info=None,
            func=record.funcName,
            sinfo=None
        )
        
        # Append suppression information to the message
        original_msg = record.getMessage()
        suppression_msg = (
            f" -- {rec.suppressed_counter} similar messages suppressed, "
            f"last occurrence was at {rec.last_occurrence_formatted}"
        )
        suppression_record.msg = original_msg + suppression_msg
        suppression_record.args = ()  # Clear args since we already formatted
        
        # Emit the suppression notice through the logger
        # We need to temporarily remove this filter to avoid recursion

        #! I need to study this
        logger = logging.getLogger(record.name)
        logger.removeFilter(self)
        try:
            logger.handle(suppression_record)
        finally:
            logger.addFilter(self)
        
        # Reset suppression tracking
        rec.last_report = time.time()
        rec.suppressed_counter = 0
    
    @staticmethod
    def _format_timestamp(timestamp: float) -> str:
        """
        Format timestamp in ISO format with microseconds.
        
        Args:
            timestamp: Unix timestamp
            
        Returns:
            Formatted timestamp string
        """
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S.%f")

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
    stdout_handler.addFilter(HandleIDFilter(HandlerType.Stream))
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
    stderr_handler.addFilter(HandleIDFilter(HandlerType.Stream))
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



# Placeholder code for currently nonexisting handlers. 
# These are simply RichHandler instances which replace the utc timing info with their
# Handler names. Will be removed as soon as real handlers are developed

def dummy_add_lstdout_handler(log : logging.Logger, use_parent_handlers: bool) -> None:
    """Adds dummy handler."""
    width: int = get_width()
    handler: RichHandler = LstdoutDummy(width=width)
    handler.addFilter(HandleIDFilter(HandlerType.Lstdout))
    log.addHandler(handler)

def dummy_add_erstrace_handler(log: logging.Logger, use_parent_handlers: bool) -> None:
    """Adds dummy handler."""
    width: int = get_width()
    handler: RichHandler = ERSTraceDummy(width=width)
    handler.addFilter(HandleIDFilter(HandlerType.ERSTrace))
    log.addHandler(handler)

def dummy_add_throttle_handler(log: logging.Logger, use_parent_handlers: bool) -> None:
    """Adds dummy handler."""
    width: int = get_width()
    handler: RichHandler = ThrottleDummy(width=width)
    handler.addFilter(HandleIDFilter(HandlerType.Throttle))
    log.addHandler(handler)
class ClassNameRichHandler(FormattedRichHandler):
    """Handler that displays the class name instead of time. Temporary class."""

    def render(
        self,
        *,
        record: logging.LogRecord,
        traceback: object,
        message_renderable: ConsoleRenderable,
    ) -> Text:
        """Method to render an object."""
        # Use class name instead of time
        class_name: str = self.__class__.__name__
        padding: int = LOG_RECORD_PADDING.get("time", 25)
        class_name_text: Text = Text(class_name.ljust(padding)[:padding], 
            style="logging.time"
        )

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

        message_text: Text
        if isinstance(message_renderable, Text):
            message_text = message_renderable
        else:
            message_text = Text.from_markup(str(message_renderable))

        components: list[Text] = [
            class_name_text,
            level_text,
            file_and_no_text,
            logger_name_text,
            message_text,
        ]

        return Text(" ").join(components)


class LstdoutDummy(ClassNameRichHandler):
    """LstdoutDummy placeholder class."""
    pass

class ERSTraceDummy(ClassNameRichHandler):
    """ERSTraceDummy placeholder class."""
    pass
class ThrottleDummy(ClassNameRichHandler):
    """ThrottleDummy placeholder class."""
    pass
