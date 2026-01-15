from __future__ import annotations
from typing import ClassVar
import io
import os
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import cast
import re

from erskafka.ERSKafkaLogHandler import ERSKafkaLogHandler
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


class StreamType(Enum):
    """Enumtype to classify the set of relevant handlers (i.e streams)"""
    BASE="base"
    OPMON="opmon"
    ERS="ers"

@dataclass 
class ProtobufConf:
    """Dataclass to hold Protobut Configuration"""
    url:str= "monkafka.cern.ch"
    port:int= 30092

    def get_string(self):
        """Converts back to string version"""
        return f"{self.url}:{self.port}"

class HandlerType(Enum):
    """Enumtype to classify the existing set of Handlers
    Values must match exactly what is given in the OKS configuration, if any
    All are in lowercase
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
    def from_string(self, s: str) -> HandlerType:
        """Converts from a case-independent string to the"""
        return HandlerType(s.lower())


@dataclass
class ERSHandlerConf:
    """
    Dataclass that holds the relevant ERS configuration from OKS. 

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
    """Dataclass that holds the various streams and relevant handlers
    
    Attributes:
        _BASE_HANDLERS: Private class variable for default base handlers
        _OPMON_HANDLERS: Private class variable for opmon handlers
        BASE_CONFIG: Class variable for base stream configuration
        OPMON_CONFIG: Class variable for opmon stream configuration
        ERS: Instance field for ERS configuration (loaded from environment)
    """

    _BASE_HANDLERS: ClassVar[set] = {HandlerType.Stream, HandlerType.Rich, HandlerType.File}
    _OPMON_HANDLERS: ClassVar[set] = {HandlerType.Lstdout, HandlerType.Rich}
    
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
        "ers_handlers":  LogHandlerConf.get_oks_conf(),
        "stream": StreamType.ERS
    }
    )

    @staticmethod
    def convert_string_to_handlertype(handler_str: str) -> tuple[HandlerType, ProtobufConf | None]:
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
            raise ValueError("protobufstream must contain url and port in format (url:port)")
        url, port = match.group(1), int(match.group(2))
        return HandlerType.Protobufstream, ProtobufConf(url=url, port=port)

    @staticmethod
    def make_ers_handler_conf(ers_log_level :str) ->ERSHandlerConf:
        """Generates the ERSHandlerConf from reading an environment variable"""
        ershandlerconf = ERSHandlerConf()
        envvalue = os.getenv(ers_log_level)
        if envvalue is None:
            #TODO/ask: Need to decide what happens if no environment variable is detected
            # Do we return None or do we raise an error? 
            raise ValueError(f"The environment variable {ers_log_level} is empty")
        
        for h in envvalue.split(","):
            handlertype, kafkaconf = LogHandlerConf.convert_string_to_handlertype(h)
            ershandlerconf.handlers.append(handlertype)

            # TODO/ask: Current implementation only supports one protobuf handler
            # Do we want to support any more? Eg if the environment variable includes
            # Two "protobufstream(url:port)"
            if kafkaconf:
                ershandlerconf.protobufconf = kafkaconf 
        return ershandlerconf

    @staticmethod
    def get_oks_conf():
        """From the set of known environment variables, generate the ERS conf dict"""
        ers_env_vars = [
            "DUNEDAQ_ERS_WARNING",
            "DUNEDAQ_ERS_INFO",
            "DUNEDAQ_ERS_FATAL",
            "DUNEDAQ_ERS_ERROR",
        ]
        return {var: LogHandlerConf.make_ers_handler_conf(var) for var in ers_env_vars}
    
    @staticmethod
    def get_base() -> set[HandlerType]:
        """Returns the default list of handlers from LogHandlerConf._BASE_HANDLERS without having
        to initialise an instance"""
        return LogHandlerConf._BASE_HANDLERS


class HandleIDFilter(logging.Filter):
    """Filter class that accepts a list of 'allowed' handlers and will only fire
    if the current handler (defined by the handler_id) is within the set of 
    allowed handlers"""
    
    def __init__(self, handler_id:HandlerType):
        super().__init__()
        self.handler_id = handler_id
    
    def filter(self, record):
        # TODO/future: kafka protobufs should validate url/port match before transmitting
        
        # Handle the ERS case, requires more processing
        if getattr(record, "stream", None) == StreamType.ERS:
            #TODO/ask: See if we want to define this mapping elsewhere
            level_to_ers_var = {
                "ERROR": "DUNEDAQ_ERS_ERROR",
                "WARNING": "DUNEDAQ_ERS_WARNING",
                "CRITICAL": "DUNEDAQ_ERS_FATAL",
                "INFO": "DUNEDAQ_ERS_INFO",
            }

            # Chain None checks using walrus operator
            if (
                (ers_level_var := level_to_ers_var.get(record.levelname)) is None
                or (ers_handlers := getattr(record, "ers_handlers", None)) is None
                or (ershandlerconf := ers_handlers.get(ers_level_var)) is None
            ):
                return False
            
            allowed = ershandlerconf.handlers
            
        
        # Handle the non-ERS case
        else:
            allowed = getattr(record, "handlers", LogHandlerConf.get_base()) 
        if not allowed:
            return False
        return self.handler_id in allowed

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
    
def add_ers_protobuf_handler(log: logging.Logger, use_parent_handlers: bool,
                                 session_name:str, topic: str = "ers_stream", 
                                 address: str ="monkafka.cern.ch:30092") -> None:
    # TODO/future: topic and address are new, propagate to all the relevant implementation
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

def dummy_add_Lstdout_handler(log : logging.Logger, use_parent_handlers: bool) -> None:
    width: int = get_width()
    handler: RichHandler = LstdoutDummy(width=width)
    handler.addFilter(HandleIDFilter(HandlerType.Lstdout))
    log.addHandler(handler)

def dummy_add_ERSTrace_handler(log: logging.Logger, use_parent_handlers: bool) -> None:
    width: int = get_width()
    handler: RichHandler = ERSTraceDummy(width=width)
    handler.addFilter(HandleIDFilter(HandlerType.ERSTrace))
    log.addHandler(handler)

def dummy_add_Throttle_handler(log: logging.Logger, use_parent_handlers: bool) -> None:
    width: int = get_width()
    handler: RichHandler = ThrottleDummy(width=width)
    handler.addFilter(HandleIDFilter(HandlerType.Throttle))
    log.addHandler(handler)
class ClassNameRichHandler(FormattedRichHandler):
    """Handler that displays the class name instead of time."""

    def render(
        self,
        *,
        record: logging.LogRecord,
        traceback: object,
        message_renderable: ConsoleRenderable,
    ) -> Text:
        # Use class name instead of time
        class_name: str = self.__class__.__name__
        padding: int = LOG_RECORD_PADDING.get("time", 25)
        class_name_text: Text = Text(class_name.ljust(padding)[:padding], style="logging.time")

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
    pass

class ERSTraceDummy(ClassNameRichHandler):
    pass
class ThrottleDummy(ClassNameRichHandler):
    pass
