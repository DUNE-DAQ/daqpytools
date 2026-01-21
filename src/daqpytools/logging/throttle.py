"""
ThrottleFilter - Advanced logging throttle with escalating suppression thresholds. 

Mimics the behavior of the C++ ers::ThrottleStream: 
- Allows first N messages through immediately (initial threshold)
- Suppresses repeated messages with escalating thresholds (10, 100, 1000, ...)
- Reports suppression summaries periodically
- Resets state when messages stop for a time window
"""

import logging
import time
from collections import defaultdict
from threading import Lock
from datetime import datetime
from typing import Dict, Optional


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
        self. suppressed_counter: int = 0
        self.last_occurrence_formatted: str = ""


class ThrottleFilter(logging. Filter):
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
    
    def __init__(self, initial_threshold: int = 30, time_limit:  int = 30, name: str = ""):
        super().__init__(name=name)
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


# Example usage and testing
if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger("test_logger")
    
    # Add the throttle filter
    throttle = ThrottleFilter(initial_threshold=5, time_limit=2)
    logger.addFilter(throttle)
    
    print("=== Test 1: Rapid repeated messages ===")
    # First 5 should go through
    for i in range(15):
        logger.error("Repeated error from line 123")
        time.sleep(0.1)
    
    print("\n=== Test 2: Different error location ===")
    # This should also get first 5 through (different line number)
    for i in range(10):
        logger.warning("Different error")
        time.sleep(0.1)
    
    print("\n=== Test 3: Wait for time window reset ===")
    time.sleep(3)  # Wait longer than time_limit
    logger.error("Repeated error from line 123")  # Should go through after reset
    
    print("\n=== Test 4: Many rapid messages to trigger escalation ===")
    for i in range(200):
        logger.error("Spam message")
        if i % 20 == 0:
            time.sleep(0.1)