import io
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import cast

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

#! Note that this is a temp place holder, it should be ready from the environment variables!!!

# Oks_logging_map = {
#     #! There is no fatal here
#     "ERROR": "ERROR",
#     "WARNING": "WARNING",
#     "FATAL": "CRITICAL",
#     "INFO": "INFO",
# }

class StreamType(Enum):
    BASE="base"
    OPMON="opmon"
    ERS="ers"


class HandlerType(Enum):
    Unknown = 0
    Stream = 1
    Rich = 2
    File = 3
    Kafka = 4 #TODO Used to be called ERS, need to go through fine tooth comb to fix all instances
    Lstdout = 5
    ERSTrace = 6
    Throttle = 7



"""
If ERS:
    mapping[ERS_{log_level}]
else:
    mapping[thing]
"""


@dataclass
class HandlerConf:
    """Add docstring here"""
    #! Note at some point this will need to be used to initialise the kafkahandler 
    # Because the broadcast server is defined here (?!)
    base: dict = field(default_factory = lambda:
    {
        "handlers":{HandlerType.Stream, HandlerType.Rich, HandlerType.File},
        "stream": StreamType.BASE
    }
    )
    
    Opmon: dict = field(default_factory=lambda:
    {
        "handlers": {HandlerType.Lstdout, HandlerType.Rich},
        "stream": StreamType.OPMON
    }
    )

    ERS: dict=field(default_factory = lambda:
    {
        "ers_handlers":  HandlerConf.get_oks_conf(),
        "stream": StreamType.ERS
    }
    )
    
    #! Make pythonic eg use static method dectorator (if its even necessary here)
    def get_oks_conf():
        Oks_mapping = {
            "ERS_CRITICAL":   {HandlerType.Rich},
            "ERS_ERROR":   {HandlerType.Rich, HandlerType.Throttle},
        }


        #! This will need to be extracted from variables
        #* Will also need to figure out what happens if HandlerConf is initialised not inside the controller shell and similar
        # Eg. no variables exist
        #! Also writing this function its just an get os.env variable and some code to parse it
        # test_loggess.critical(f"{os.getenv('DUNEDAQ_ERS_INFO')=}")        

        return Oks_mapping



class HandleIDFilter(logging.Filter):
    def __init__(self, handler_id):
        super().__init__()
        self.handler_id = handler_id
    def filter(self, record):
        if getattr(record, "stream", None) == StreamType.ERS:
            allowed=getattr(record, "ers_handlers", None)[f"ERS_{record.levelname}"]
        else:
            # If 'handlers' set is provided, only allow if this handler is included
            #TODO: Replace the below with handlerconf.base
            allowed = getattr(record, "handlers", {HandlerType.Stream, HandlerType.Rich, HandlerType.File}) 
        if allowed is None:
            return True
        return self.handler_id in allowed





class OnlyLevelFilter(logging.Filter):
    def __init__(self, level):
        super().__init__()
        self.level = level

    def filter(self, record):
        return record.levelno == self.level



# #! If oks is true, then 
#     - first map the logging log level to the oks log level (static, can be done here)
#     - Look up the oks log level to the relevant oks handler (hard, needs to be obtained from the config) This can probably be done at the init stage of something.. 
#     - Pass the messages to all four filters. Can check if the current filter is allowed or not


#! Consider moving this to a separate filters.py
# class UseERSProtobufFilter(logging.Filter):
#     """Class containing ERS filter."""
#     def filter(self, record: logging.LogRecord,) -> bool:
#         """Checks if use_ers is set to only send ERS messages when specified."""
#         return getattr(record, "use_ers", False)

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
    

def add_ers_protobuf_handler(log: logging.Logger, use_parent_handlers: bool,
                                 session_name:str, topic: str = "ers_stream", 
                                 address: str ="monkafka.cern.ch:30092") -> None:
    # TODO: topic and address are new, propagate to all the relevant implementation
    """Add an ers protobuf handler to the root logger."""
    check_parent_handlers(log, use_parent_handlers, ERSKafkaLogHandler)
    handler: ERSKafkaLogHandler = ERSKafkaLogHandler(session=session_name, 
                                                     kafka_address = address, 
                                                     kafka_topic = topic
                                                     )
    handler.addFilter(HandleIDFilter(HandlerType.Kafka))
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
