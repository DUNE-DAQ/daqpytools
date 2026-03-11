from __future__ import annotations

import copy
import logging
import time
from collections import defaultdict
from datetime import datetime
from threading import Lock

from rich.text import Text

from daqpytools.logging.formatter import (
    DATE_TIME_BASE_FORMAT,
    LOG_RECORD_PADDING,
    TIME_ZONE,
)
from daqpytools.logging.handlerconf import (
    HandlerType,
    LogHandlerConf,
)
from daqpytools.logging.routing import (
    AllowedHandlersStrategy,
    StreamAwareAllowedHandlersStrategy,
)
from daqpytools.logging.specs import FilterSpec


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
        self.fallback_handlers = (
            set(fallback_handlers)
            if fallback_handlers is not None
            else LogHandlerConf.get_base()
        )

        self.allowed_handlers_strategy = (
            allowed_handlers_strategy or 
            StreamAwareAllowedHandlersStrategy()
        )
        super().__init__()

    def get_allowed(self, record: logging.LogRecord) -> set[HandlerType] | None:
        """Resolve the allowed handlers for a record."""
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
  


def _build_throttle_filter(
    fallback_handlers: set[HandlerType],
    initial_treshold : int = 30,
    time_limit: int = 30,
    **extras: object,
) -> logging.Filter:
    """Build a throttle filter from extras."""
    del extras
    return ThrottleFilter(
        fallback_handlers=fallback_handlers,
        initial_threshold=initial_treshold,
        time_limit=time_limit
    )

THROTTLE_FILTER_SPEC = FilterSpec(
    alias = HandlerType.Throttle,
    filter_class = ThrottleFilter,
    factory=_build_throttle_filter,
    fallback_types=(HandlerType.Throttle,),
)

FILTER_SPEC_REGISTRY: dict[HandlerType, FilterSpec] = {
    HandlerType.Throttle: THROTTLE_FILTER_SPEC
}

def get_filter_spec(handler_types: HandlerType) -> FilterSpec | None:
    """Return the filter specification for a handler type."""
    return FILTER_SPEC_REGISTRY.get(handler_types)

def add_filter(
    log: logging.Logger,
    handler_type:HandlerType,
    fallback_handlers : set[HandlerType]| None,
    **extras: object,
) -> None:
    """Add a logger filter according to the spec."""
    spec = get_filter_spec(handler_type)

    effective_fallback_handlers = (
        fallback_handlers
        if fallback_handlers is not None
        else set(spec.fallback_types)
    )
    logger_filter = spec.factory(
        effective_fallback_handlers,
        **extras
    )
    log.addFilter(logger_filter)


def add_throttle_filter(
    log: logging.Logger,
    fallback_handlers: set[HandlerType] | None = None,
) -> None:
    """Add the Throttle filter to the logger."""
    add_filter(
        log,
        HandlerType.Throttle,
        fallback_handlers
    )
