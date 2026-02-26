from __future__ import annotations

import copy
import io
import logging
import sys
import time
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from threading import Lock
from typing import cast, Mapping, Any

from erskafka.ERSKafkaLogHandler import ERSKafkaLogHandler
from rich.logging import RichHandler
from rich.text import Text

from daqpytools.logging.exceptions import (
    LoggerHandlerError,
)
from daqpytools.logging.formatter import (
    DATE_TIME_BASE_FORMAT,
    LOG_RECORD_PADDING,
    TIME_ZONE,
    LoggingFormatter,
)

from daqpytools.logging.rich_handler import FormattedRichHandler
from daqpytools.logging.specs import HandlerSpec, FilterSpec

from daqpytools.logging.handlerdataclasses import (
    HandlerType,
    LogHandlerConf,
)
from daqpytools.logging.routing import (
    AllowedHandlersStrategy,
    StreamAwareAllowedHandlersStrategy,
)
from daqpytools.logging.utils import get_width


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
    def __init__(
        self,
        fallback_handlers: set[HandlerType] | None = None,
        allowed_handlers_strategy : AllowedHandlersStrategy | None = None,
    ) -> None:
        """C'tor."""
        self.fallback_handlers = set(fallback_handlers) if fallback_handlers is not None else LogHandlerConf.get_base() #! We should check if this is still the case

        self.allowed_handlers_strategy = (
            allowed_handlers_strategy or 
            StreamAwareAllowedHandlersStrategy()
        )
        super().__init__()

    def get_allowed(self, record: logging.LogRecord) -> set[HandlerType] | None:
        return self.allowed_handlers_strategy.resolve(record, self.fallback_handlers)

        
class HandleIDFilter(BaseHandlerFilter):
    """Filter class that accepts a list of 'allowed' handlers and will only fire
    if the current handler (defined by the handler_id) is within the set of 
    allowed handlers.
    """
    def __init__(
        self,
        handler_id: HandlerType | list[HandlerType],
        fallback_handlers: set[HandlerType] | None = None,
        allowed_handlers_strategy: AllowedHandlersStrategy | None = None,
    ) -> None:
        """Initialises HandleIDFilter with the handler_id, to identify what
        kind of handler this filter is.
        """
        super().__init__(
            fallback_handlers = fallback_handlers,
            allowed_handlers_strategy=allowed_handlers_strategy
        )
        
        # Normalise handler_id to be a set
        if isinstance(handler_id, list):
            self.handler_ids = set(handler_id)
        else:
            self.handler_ids = {handler_id}
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Identifies when a log message should be transmitted or not."""
        if not (allowed:= self.get_allowed(record)):
            return False
        return bool(self.handler_ids & allowed)

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
    
    def __init__(
        self,
        fallback_handlers: set[HandlerType] | None = None,
        initial_threshold: int = 30,
        time_limit: int = 30,
        allowed_handlers_strategy : AllowedHandlersStrategy | None = None
    ) -> None:
        """C'tor."""
        super().__init__(
            fallback_handlers = fallback_handlers,
            allowed_handlers_strategy = allowed_handlers_strategy
            )
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
    
def logger_has_handler(
    log: logging.Logger,
    handler_type: type[logging.Handler],
    target_stream: io.IOBase | None = None,
) -> bool:
    """Check if logger already has a matching handler.

    For StreamHandler, ``target_stream`` can be used to distinguish stdout/stderr.
    """
    # Catches cases when a MockLogger is used in pytest
    if not isinstance(log, logging.Logger):
        return False

    type_matches = [
        isinstance(handler, handler_type)
        for handler in log.handlers
        if not isinstance(handler, logging.StreamHandler)
    ]

    stream_matches = [
            handler.stream is target_stream if target_stream else False
            for handler in log.handlers
            if isinstance(handler, logging.StreamHandler)
        ]
    return any(type_matches + stream_matches)

def logger_has_filter(log: logging.Logger, filter_type: type[logging.Filter]) -> bool:
    """Check if logger already has a matching filter type."""
    if not isinstance(log, logging.Logger):
        return False

    return any(isinstance(logger_filter, filter_type) for logger_filter in log.filters)

def ancestors_have_handlers(
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
        return False

    if not isinstance(log, logging.Logger):
        return False

    # Check that we are not using the true logging root logger
    python_root_logger_name = logging.getLogger().name
    if log.name == python_root_logger_name:
        err_msg = "You should not be interfacing with the root logger"
        raise ValueError(err_msg)
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
    visited_logger_ids: set[int] = set()

    while isinstance(logger_parent, logging.Logger):
        logger_id = id(logger_parent)
        if logger_id in visited_logger_ids:
            return False # Prevents infinite loop
        visited_logger_ids.add(logger_id)

        if logger_parent.name == python_root_logger_name:
            break

        if logger_has_handler(logger_parent,handler_type, target_stream):
            return True
        logger_parent = logger_parent.parent
    return False


def check_parent_handlers(
    log: logging.Logger,
    use_parent_handlers: bool,
    handler_type: type[logging.Handler],
    target_stream: io.IOBase | None = None,
) -> None:
    """Raise when a matching handler already exists on an ancestor logger."""
    if ancestors_have_handlers(log, use_parent_handlers, handler_type, target_stream):
        raise LoggerHandlerError(log.name, handler_type)
    

def logger_or_ancestors_have_handler(
    log: logging.Logger,
    use_parent_handlers: bool,
    handler_type: type[logging.Handler],
    target_stream: io.IOBase | None = None,
) -> bool:
    """Check if logger or (optionally) its ancestors have a matching handler."""
    return logger_has_handler(
        log, handler_type, target_stream
    ) or ancestors_have_handlers(log, use_parent_handlers, handler_type, target_stream)


def _build_rich_handler(extras: Mapping[str, Any]) -> logging.Handler:
    """Building the rich handler with any extras."""
    width = cast(int,  extras.get("width", get_width()))
    return FormattedRichHandler(width=width)


RICH_HANDLER_SPEC = HandlerSpec(
    representative_type = HandlerType.Rich,
    handler_type = FormattedRichHandler,
    factory=_build_rich_handler,
    filter_handler_ids = (HandlerType.Rich,), # For HandleIDFilter
)

HANDLER_SPEC_REGISTRY : dict[HandlerType, tuple[HandlerSpec, ...]] = {
    HandlerType.Rich: (RICH_HANDLER_SPEC,),
}

#! Lets try go tet the add rich handler thing running!


def get_handler_specs(handler_type: HandlerType):
    """Get the specs defined in the registry"""
    return HANDLER_SPEC_REGISTRY.get(handler_type, tuple())


#! This we should be careful with..
def _resolve_default_case(
    default_case: set[HandlerType] | None
) -> set[HandlerType]:
    "Return a safe copy of default_case with sensible fallback"
    if default_case is None:
        return LogHandlerConf.get_base()
    return set(default_case)

def add_handler(
    log: logging.logger_has_filter,
    spec: HandlerSpec,
    use_parent_handlers:bool, 
    fallback_handler: set[HandlerType] | None,
    extras: Mapping[str, Any] | None = None,
):
    check_parent_handlers(
        log,
        use_parent_handlers,
        spec.handler_type,
        target_stream = spec.target_stream
    )

    handler = spec.factory(extras or {})
    effective_default_case = _resolve_default_case(fallback_handler)

    handler_ids: HandlerType | list[HandlerType]
    if len(spec.filter_handler_ids) == 1:
        handler_ids = cast(HandlerType, spec.filter_handler_ids[0])
    else: 
        handler_ids = [cast(HandlerType, handler_id) for handler_id in spec.filter_handler_ids] 

    handler.addFilter(
        HandleIDFilter(
            handler_id=handler_ids,
            fallback_handlers=effective_default_case
        )
    )

    log.addHandler(handler)

def add_rich_handler(
    log: logging.Logger,
    use_parent_handlers: bool,
    fallback_handlers: set[HandlerType] | None = None,
) -> None:
    
    add_handler(
        log,
        RICH_HANDLER_SPEC,
        use_parent_handlers,
        fallback_handlers
    )

##################################################################################################
##################################################################################################
##################################################################################################
##################################################################################################
##################################################################################################


def add_throttle_filter(
    log: logging.Logger,
    fallback_handlers: set[HandlerType] | None = None,
) -> None:
    """Add the Throttle filter to the logger.

    Args:
        log (logging.Logger): Logger to add the rich handler to.
        fallback_handlers (set[HandlerType] | None): Default handler set used when
            records do not explicitly include handler routing.

    Returns:
        None
    """
    if fallback_handlers is None:
        fallback_handlers = {HandlerType.Throttle}
    log.addFilter(ThrottleFilter(fallback_handlers=fallback_handlers))
    return

# def add_rich_handler(
#     log: logging.Logger,
#     use_parent_handlers: bool,
#     fallback_handlers: set[HandlerType] | None = None,
# ) -> None:
#     """Add a rich handler to the logger.

#     Args:
#         log (logging.Logger): Logger to add the rich handler to.
#         use_parent_handlers (bool): Whether to check parent handlers.
#         fallback_handlers (set[HandlerType] | None): Default handler set used when
#             records do not explicitly include handler routing.

#     Returns:
#         None

#     Raises:
#         LoggerHandlerError: If a parent logger has a rich handler.
#     """
#     if fallback_handlers is None:
#         fallback_handlers = {HandlerType.Rich}
#     check_parent_handlers(log, use_parent_handlers, FormattedRichHandler)
#     width: int = get_width()
#     handler: RichHandler = FormattedRichHandler(width=width)    
    
#     handler.addFilter(
#         HandleIDFilter(
#             handler_id=HandlerType.Rich,
#             fallback_handlers=fallback_handlers
#             )
#     )
#     log.addHandler(handler)
#     return

def add_ers_kafka_handler(
    log: logging.Logger,
    use_parent_handlers: bool,
    session_name: str,
    fallback_handlers: set[HandlerType] | None = None,
    app_name : str|None =None,
    topic: str = "ers_stream",
    address: str = "monkafka.cern.ch:30092",
) -> None:
    # TODO/future: topic and address are new, propagate to all relevant implementation
    """Add an ers protobuf handler to the root logger."""
    if fallback_handlers is None:
        fallback_handlers = {HandlerType.Protobufstream}
    check_parent_handlers(log, use_parent_handlers, ERSKafkaLogHandler)
    handler: ERSKafkaLogHandler = ERSKafkaLogHandler(session=session_name, 
                                                     kafka_address = address, 
                                                     kafka_topic = topic,
                                                     app_name = app_name,
                                                     )

    handler.addFilter(
        HandleIDFilter(
            handler_id=HandlerType.Protobufstream,
            fallback_handlers=fallback_handlers
            )
    )
    log.addHandler(handler)

def add_stdout_handler(
    log: logging.Logger,
    use_parent_handlers: bool,
    fallback_handlers: set[HandlerType] | None = None,
) -> None:
    """Add a stdout handler to the logger.

    Args:
        log (logging.Logger): Logger to add the stdout handler to.
        use_parent_handlers (bool): Whether to check parent handlers.
        fallback_handlers (set[HandlerType] | None): Default handler set used when
            records do not explicitly include handler routing.

    Returns:
        None

    Raises:
        LoggerHandlerError: If a parent logger has a stdout handler.
    """
    if fallback_handlers is None:
        fallback_handlers = {HandlerType.Stream, HandlerType.Lstdout}
    check_parent_handlers(
        log,
        use_parent_handlers,
        logging.StreamHandler,
        target_stream=cast(io.IOBase, sys.stdout),
    )
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(LoggingFormatter())
    
    stdout_handler.addFilter(
        HandleIDFilter(
            handler_id=[HandlerType.Stream, HandlerType.Lstdout],
            fallback_handlers=fallback_handlers
            )
    )    
    log.addHandler(stdout_handler)
    return

def add_stderr_handler(
    log: logging.Logger,
    use_parent_handlers: bool,
    fallback_handlers: set[HandlerType] | None = None,
) -> None:
    """Add a stderr handler to the logger.

    The error is set to the ERROR level, and will only log messages at that level
    or higher. This is to avoid duplicate logging of error messages when both stdout
    and stderr handlers are used.

    Args:
        log (logging.Logger): Logger to add the stderr handler to.
        use_parent_handlers (bool): Whether to check parent handlers.
        fallback_handlers (set[HandlerType] | None): Default handler set used when
            records do not explicitly include handler routing.

    Returns:
        None

    Raises:
        LoggerHandlerError: If a parent logger has a stderr handler.
    """
    if fallback_handlers is None:
        fallback_handlers = {HandlerType.Lstderr, HandlerType.Stream}
    check_parent_handlers(
        log,
        use_parent_handlers,
        logging.StreamHandler,
        target_stream=cast(io.IOBase, sys.stderr),
    )
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(LoggingFormatter())
    stderr_handler.addFilter(
        HandleIDFilter(
            handler_id=[HandlerType.Stream, HandlerType.Lstderr],
            fallback_handlers=fallback_handlers
            )
    )    
    stderr_handler.setLevel(logging.ERROR)
    log.addHandler(stderr_handler)
    return

def add_file_handler(
    log: logging.Logger,
    use_parent_handlers: bool,
    path: str,
    fallback_handlers: set[HandlerType] | None = None,
) -> None:
    """Add a file handler to the root logger.

    Args:
        log (logging.Logger): Logger to add the file handler to.
        use_parent_handlers (bool): Whether to check parent handlers.
        path (str): Path to the log file.
        fallback_handlers (set[HandlerType] | None): Default handler set used when
            records do not explicitly include handler routing.

    Returns:
        None

    Raises:
        LoggerHandlerError: If a parent logger has a file handler.
    """
    if fallback_handlers is None:
        fallback_handlers = {HandlerType.File}
    check_parent_handlers(log, use_parent_handlers, logging.FileHandler)
    file_handler = logging.FileHandler(filename=path)
    file_handler.setFormatter(LoggingFormatter())
    file_handler.addFilter(
        HandleIDFilter(
            handler_id=HandlerType.File,
            fallback_handlers=fallback_handlers
            )
    )
    log.addHandler(file_handler)
    return

def add_handlers_from_types(
    log: logging.Logger,
    handler_types: set[HandlerType],
    use_parent_handlers: bool,
    fallback_handlers: set[HandlerType],
    file_name: str | None,
    ers_kafka_session: str | None,
    app_name : str|None = None,
) -> None:
    """Add handlers to a logger based on a set of HandlerType values.

    This helper intentionally supports only the default options for now:
    - ``use_parent_handlers`` is always True.
    - ``HandlerType.File`` is not supported and raises immediately.
    - ``HandlerType.Protobufstream`` requires ``ers_kafka_session``.
    """
    if HandlerType.Protobufstream in handler_types and not ers_kafka_session:
        err_msg = "ers_kafka_session is required for HandlerType.Protobufstream"
        raise ValueError(err_msg)
    
    if HandlerType.File in handler_types and not file_name:
        err_msg = "file_name is required for HandlerType.File"
        raise ValueError(err_msg)

    # Update relevant handler types that was parsed
    effective_handler_types = set(handler_types)
    if HandlerType.Stream in effective_handler_types:
        effective_handler_types.update({HandlerType.Lstdout, HandlerType.Lstderr})

    # Generate handler configurations based on arguments for auto install
    handler_configs: dict[
        HandlerType,
        tuple[
            type[logging.Handler] | None, # Handler as seen by Python's Logger
            io.IOBase | None, # Used for streamhandling
            type[logging.Filter] | None, # For filters attached to loggers
            Callable[[], None],  # Installer code
        ],
    ] = {
        HandlerType.Rich: (
            FormattedRichHandler,
            None,
            None,
            lambda: add_rich_handler(log, use_parent_handlers, fallback_handlers),
        ),
        HandlerType.Lstdout: (
            logging.StreamHandler,
            cast(io.IOBase, sys.stdout),
            None,
            lambda: add_stdout_handler(log, use_parent_handlers, fallback_handlers),
        ),
        HandlerType.Lstderr: (
            logging.StreamHandler,
            cast(io.IOBase, sys.stderr),
            None,
            lambda: add_stderr_handler(log, use_parent_handlers, fallback_handlers),
        ),
        HandlerType.Protobufstream: (
            ERSKafkaLogHandler,
            None,
            None,
            lambda: add_ers_kafka_handler(
                log, use_parent_handlers, ers_kafka_session, {HandlerType.Unknown},
                app_name
                # WE DONT WANT TO TRANSMIT BY DEFAULT
            ),
        ),
        HandlerType.Throttle: (
            None,
            None,
            ThrottleFilter,
            lambda: add_throttle_filter(log, fallback_handlers),
        ),
        HandlerType.File: (
            logging.FileHandler,
            None,
            None,
            lambda: add_file_handler(
                log, use_parent_handlers, file_name, fallback_handlers
            ),
        ),
    }


    for handler_type, (
        handler_class,
        target_stream,
        filter_type,
        installer,
    ) in handler_configs.items():
        
        # Skips if it encounters an unrequested handler
        if handler_type not in effective_handler_types:
            continue
        
        # Skips if handler/filter exists in either the logger or any of its ancestors
        handler_exists = (
            handler_class is not None
            and logger_or_ancestors_have_handler(
                log,
                use_parent_handlers,
                handler_class,
                target_stream=target_stream,
            )
        ) or (filter_type is not None and logger_has_filter(log, filter_type))
        
        if handler_exists:
            continue
        
        installer()
