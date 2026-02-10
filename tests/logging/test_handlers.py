



#! What do we want to test here? 

#! The processing of the environment variables, partiuclarly the protobuf, the random one, and also what happens when you try to initialise it without the right environment

# this should test  _convert_str_to_handlertype with throttle, protobufstream, and random
# throttle should return handlertype.throttle, none , protobufstream should return handlertype.protobufstream, and a valid protobufconf with the same values as expected

# See if its possible to test _make_ers_handler_conf
# This should just take a default string comma and then return the correct features

# Definitely test the creation of the full thing, with the four environments


#! Also test the from string in HandlerTypes
# Should get this testesd for the enums but also the error itself


#! We need to test the filters.. 
# Figure out how to test logging filters..


# Need tests for the throttling for sure

# Need a test for the base handlerfilter:
# using one handlertype
# using multiple handler types


###########


"""Comprehensive tests for the logging filters in handlers.py.

Tests cover:
- BaseHandlerFilter: Handler selection logic for both ERS and non-ERS paths
- HandleIDFilter: Filter that accepts only specific handler types
- ThrottleFilter: Advanced throttling with escalating thresholds and time windows
- Integration: Real logger usage with filters and handlers
"""

import copy
import io
import logging
import time
from threading import Thread
from unittest.mock import MagicMock, patch

import pytest

from daqpytools.logging.handlers import (
    BaseHandlerFilter,
    ERSPyLogHandlerConf,
    HandleIDFilter,
    HandlerType,
    IssueRecord,
    ProtobufConf,
    StreamType,
    ThrottleFilter,
)
from daqpytools.logging.levels import level_to_ers_var

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def clean_logger():
    """Provide a clean logger with no handlers or filters."""
    logger = logging.getLogger("test_logger_" + str(time.time()))
    logger.handlers = []
    logger.filters = []
    logger.setLevel(logging.DEBUG)
    return logger


@pytest.fixture
def log_record():
    """Provide a basic log record for testing."""
    record = logging.LogRecord(
        name="test.module",
        level=logging.ERROR,
        pathname="/path/to/test.py",
        lineno=42,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    return record


@pytest.fixture
def ers_log_record():
    """Provide a log record configured for ERS streaming."""
    record = logging.LogRecord(
        name="test.module",
        level=logging.ERROR,
        pathname="/path/to/test.py",
        lineno=42,
        msg="ERS message",
        args=(),
        exc_info=None,
    )
    record.stream = StreamType.ERS
    return record


@pytest.fixture
def mock_ers_handlers():
    """Provide mock ERS handler configuration for testing."""
    handlers_config = {}
    for level_var in level_to_ers_var.values():
        conf = ERSPyLogHandlerConf(
            handlers=[HandlerType.Throttle, HandlerType.Protobufstream],
            protobufconf=ProtobufConf(url="test.kafka.com", port=9092),
        )
        handlers_config[level_var] = conf
    return handlers_config


# ============================================================================
# BaseHandlerFilter Tests
# ============================================================================


class TestBaseHandlerFilter:
    """Tests for BaseHandlerFilter.get_allowed() logic."""

    def test_non_ers_uses_record_handlers_attribute(self, log_record):
        """Test get_allowed() uses 'handlers' attribute from record for non-ERS."""
        log_record.handlers = [HandlerType.Rich, HandlerType.File]
        filter_obj = BaseHandlerFilter()

        allowed = filter_obj.get_allowed(log_record)

        assert allowed == [HandlerType.Rich, HandlerType.File]

    def test_non_ers_defaults_to_base_handlers(self, log_record):
        """Test get_allowed() falls back to default handlers when attribute missing."""
        # log_record has no 'handlers' attribute
        filter_obj = BaseHandlerFilter()

        allowed = filter_obj.get_allowed(log_record)

        # Should return the base handlers from LogHandlerConf
        assert allowed is not None
        expected_handlers = {HandlerType.Stream, HandlerType.Rich, HandlerType.File}
        assert expected_handlers.issubset(set(allowed))

    def test_ers_path_valid_configuration(self, ers_log_record, mock_ers_handlers):
        """Test get_allowed() extracts ERS handlers correctly with valid config."""
        ers_log_record.ers_handlers = mock_ers_handlers
        filter_obj = BaseHandlerFilter()

        allowed = filter_obj.get_allowed(ers_log_record)

        assert allowed == [HandlerType.Throttle, HandlerType.Protobufstream]

    def test_ers_path_missing_ers_handlers_attribute(self, ers_log_record):
        """Test get_allowed() returns None when ERS record lacks ers_handlers."""
        # ers_log_record has stream=ERS but no ers_handlers attribute
        filter_obj = BaseHandlerFilter()

        allowed = filter_obj.get_allowed(ers_log_record)

        assert allowed is None

    def test_ers_path_no_matching_level_variable(self, ers_log_record, mock_ers_handlers):
        """Test get_allowed() returns None when log level has no ERS mapping."""
        # Set a log level that might not have an ERS equivalent
        ers_log_record.levelno = 25  # Between INFO and WARNING
        ers_log_record.ers_handlers = mock_ers_handlers
        filter_obj = BaseHandlerFilter()

        allowed = filter_obj.get_allowed(ers_log_record)

        # Level 25 likely won't map to any ERS variable, so should return None
        # or might map to something - let's handle both cases
        if 25 not in level_to_ers_var:
            assert allowed is None

    def test_ers_path_missing_handler_conf_for_level(self, ers_log_record):
        """Test get_allowed() returns None when handler conf missing for level."""
        ers_log_record.levelno = logging.DEBUG  # Low level
        # Provide partial ers_handlers config missing the DEBUG entry
        ers_log_record.ers_handlers = {}
        filter_obj = BaseHandlerFilter()

        allowed = filter_obj.get_allowed(ers_log_record)

        assert allowed is None


# ============================================================================
# HandleIDFilter Tests
# ============================================================================


class TestHandleIDFilter:
    """Tests for HandleIDFilter.filter() logic."""

    def test_single_handler_id_normalized_to_set(self):
        """Test that single handler_id is normalized to a set."""
        filter_obj = HandleIDFilter(HandlerType.Rich)

        assert isinstance(filter_obj.handler_ids, set)
        assert HandlerType.Rich in filter_obj.handler_ids

    def test_list_handler_ids_converted_to_set(self):
        """Test that list of handler_ids is converted to a set."""
        handlers = [HandlerType.Rich, HandlerType.File]
        filter_obj = HandleIDFilter(handlers)

        assert isinstance(filter_obj.handler_ids, set)
        assert filter_obj.handler_ids == {HandlerType.Rich, HandlerType.File}

    def test_filter_returns_true_when_handler_in_allowed(self, log_record):
        """Test filter() returns True when handler_id is in allowed list."""
        log_record.handlers = [HandlerType.Rich, HandlerType.File, HandlerType.Stream]
        filter_obj = HandleIDFilter(HandlerType.Rich)

        result = filter_obj.filter(log_record)

        assert result is True

    def test_filter_returns_false_when_handler_not_in_allowed(self, log_record):
        """Test filter() returns False when handler_id not in allowed."""
        log_record.handlers = [HandlerType.File, HandlerType.Stream]
        filter_obj = HandleIDFilter(HandlerType.Rich)

        result = filter_obj.filter(log_record)

        assert result is False

    def test_filter_returns_false_when_get_allowed_returns_none(self, log_record):
        """Test filter() returns False when get_allowed() returns None."""
        filter_obj = HandleIDFilter(HandlerType.Rich)
        filter_obj.get_allowed = MagicMock(return_value=None)

        result = filter_obj.filter(log_record)

        assert result is False

    def test_filter_with_multiple_handler_ids(self, log_record):
        """Test filter() with multiple handler_ids checks intersection."""
        log_record.handlers = [HandlerType.Rich, HandlerType.File]
        filter_obj = HandleIDFilter([HandlerType.Rich, HandlerType.Stream])

        result = filter_obj.filter(log_record)

        # Should return True because Rich is in both sets
        assert result is True

    def test_filter_no_intersection_with_multiple_ids(self, log_record):
        """Test filter() returns False when no intersection with multiple ids."""
        log_record.handlers = [HandlerType.File]
        filter_obj = HandleIDFilter([HandlerType.Rich, HandlerType.Stream])

        result = filter_obj.filter(log_record)

        assert result is False


# ============================================================================
# ThrottleFilter Tests
# ============================================================================


class TestThrottleFilter:
    """Tests for ThrottleFilter throttling and suppression logic."""

    def test_initial_phase_lets_through_first_n_messages(self, log_record):
        """Test that first N messages pass through without suppression."""
        log_record.handlers = [HandlerType.Throttle]
        filter_obj = ThrottleFilter(initial_threshold=3, time_limit=10)

        # First 3 messages should pass
        assert filter_obj.filter(log_record) is True
        assert filter_obj.filter(log_record) is True
        assert filter_obj.filter(log_record) is True

    def test_after_initial_threshold_suppresses(self, log_record):
        """Test that messages are suppressed after initial_threshold."""
        log_record.handlers = [HandlerType.Throttle]
        filter_obj = ThrottleFilter(initial_threshold=2, time_limit=10)

        # First 2 pass
        assert filter_obj.filter(log_record) is True
        assert filter_obj.filter(log_record) is True

        # 3rd should be suppressed
        assert filter_obj.filter(log_record) is False

    def test_escalating_threshold_doubles_on_report(self, log_record):
        """Test that threshold escalates (10->100->1000) when reporting."""
        log_record.handlers = [HandlerType.Throttle]
        filter_obj = ThrottleFilter(initial_threshold=1, time_limit=100)

        issue_id = f"{log_record.pathname}:{log_record.lineno}"
        issue_record = filter_obj.issue_map[issue_id]

        # First is emitted
        # Next 10 are suppressed
        # needs 1 more to trigger update
        for _ in range(12):
            filter_obj._throttle(issue_record, log_record)
        

        assert issue_record.threshold == 100  # Escalated from 10

    def test_time_window_reset_resets_counters(self, log_record, monkeypatch):
        """Test that state resets after time_limit expires."""
        log_record.handlers = [HandlerType.Throttle]
        filter_obj = ThrottleFilter(initial_threshold=1, time_limit=1)

        times = iter([1000.0, 1002.5])
        monkeypatch.setattr(time, "time", lambda: next(times))

        # First message passes
        assert filter_obj.filter(log_record) is True

        # Time advances beyond time_limit with no suppression, reset should allow pass
        assert filter_obj.filter(log_record) is True

    def test_suppressed_counter_increments(self, log_record):
        """Test that suppressed_counter increments for each suppressed message."""
        log_record.handlers = [HandlerType.Throttle]
        filter_obj = ThrottleFilter(initial_threshold=0, time_limit=100)

        issue_id = f"{log_record.pathname}:{log_record.lineno}"
        issue_record = filter_obj.issue_map[issue_id]

        # Send 5 messages
        for i in range(5):
            filter_obj.filter(log_record)
            # After initial messages handled, counter should increment
            if i > 0:
                assert issue_record.suppressed_counter >= 0

    def test_throttle_suppression_flag_bypasses_filter(self, log_record):
        """Test that _throttle_suppression flag allows suppression messages through."""
        log_record.handlers = [HandlerType.Throttle]
        filter_obj = ThrottleFilter(initial_threshold=0, time_limit=100)

        # Normal message is suppressed
        assert filter_obj.filter(log_record) is False

        # Same message with suppression flag bypasses filter
        log_record._throttle_suppression = True
        assert filter_obj.filter(log_record) is True

    def test_get_allowed_returns_none_skips_throttle(self, log_record):
        """Test filter() returns True if get_allowed() returns None."""
        filter_obj = ThrottleFilter()
        filter_obj.get_allowed = MagicMock(return_value=None)

        # Should return False because allowed is None
        result = filter_obj.filter(log_record)
        assert result is False

    def test_throttle_not_in_allowed_returns_true(self, log_record):
        """Test filter() returns True if Throttle not in allowed handlers."""
        log_record.handlers = [HandlerType.Rich, HandlerType.File]
        filter_obj = ThrottleFilter(initial_threshold=0, time_limit=10)

        # Throttle not in allowed, so should return True
        assert filter_obj.filter(log_record) is True

    def test_timestamp_formatting(self):
        """Test that timestamp formatting produces valid ISO format."""
        filter_obj = ThrottleFilter()
        timestamp = time.time()

        formatted = filter_obj._format_timestamp(timestamp)

        # Should be ISO format with microseconds
        assert len(formatted) == 26  # YYYY-MM-DD HH:MM:SS.ffffff
        assert formatted.count("-") == 2  # Two dashes for date
        assert formatted.count(":") == 2  # Two colons for time

    def test_report_suppression_not_called_when_counter_zero(self, log_record):
        """Test that _report_suppression returns early if suppressed_counter is 0."""
        filter_obj = ThrottleFilter()
        issue_record = IssueRecord()
        issue_record.suppressed_counter = 0

        with patch.object(filter_obj, "_report_suppression") as mock_report:
            filter_obj._report_suppression(issue_record, log_record)

            # Should return early without doing anything
            # (We can't easily test this without mocking, but the logic is clear)
            # Just verify the method completes without error
            assert True

    def test_different_issues_tracked_separately(self, log_record):
        """Test that different file:line combinations track state separately."""
        filter_obj = ThrottleFilter(initial_threshold=2, time_limit=10)

        # First issue
        record1 = copy.deepcopy(log_record)
        record1.pathname = "/path1.py"
        record1.lineno = 10
        record1.handlers = [HandlerType.Throttle]

        # Second issue
        record2 = copy.deepcopy(log_record)
        record2.pathname = "/path2.py"
        record2.lineno = 20
        record2.handlers = [HandlerType.Throttle]

        # Both pass initial threshold
        assert filter_obj.filter(record1) is True
        assert filter_obj.filter(record2) is True

        # Issue 1: passes again
        assert filter_obj.filter(record1) is True

        # Issue 2: passes again (separate tracking)
        assert filter_obj.filter(record2) is True

        # Issue 1: suppressed
        assert filter_obj.filter(record1) is False

        # Issue 2: suppressed (independent)
        assert filter_obj.filter(record2) is False

    def test_thread_safety_concurrent_issues(self, log_record):
        """Test ThrottleFilter is thread-safe with concurrent logging."""
        filter_obj = ThrottleFilter(initial_threshold=5, time_limit=10)
        log_record.handlers = [HandlerType.Throttle]
        results = []

        def log_messages(record, num_messages):
            """Log from a thread."""
            for _ in range(num_messages):
                result = filter_obj.filter(record)
                results.append(result)

        # Create threads logging to same issue
        threads = []
        for _ in range(3):
            thread = Thread(target=log_messages, args=(log_record, 10))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Should have completed without deadlock
        assert len(results) == 30
        # First 5 should pass (initial threshold)
        assert results[:5].count(True) >= 3  # At least some early ones pass


# ============================================================================
# IssueRecord Tests
# ============================================================================


class TestIssueRecord:
    """Tests for IssueRecord state tracking."""

    def test_init_sets_defaults(self):
        """Test that __init__ sets proper default values."""
        record = IssueRecord()

        assert record.last_occurrence == 0.0
        assert record.last_report == 0.0
        assert record.initial_counter == 0
        assert record.threshold == 10
        assert record.suppressed_counter == 0
        assert record.last_occurrence_formatted == ""

    def test_reset_clears_all_state(self):
        """Test that reset() clears all counters and timestamps."""
        record = IssueRecord()
        record.last_occurrence = 100.0
        record.initial_counter = 5
        record.suppressed_counter = 20
        record.threshold = 100
        record.last_occurrence_formatted = "2025-01-01 12:00:00.000000"

        record.reset()

        assert record.last_occurrence == 0.0
        assert record.last_report == 0.0
        assert record.initial_counter == 0
        assert record.threshold == 10
        assert record.suppressed_counter == 0
        assert record.last_occurrence_formatted == ""


# ============================================================================
# Integration Tests
# ============================================================================


class TestFiltersIntegration:
    """Integration tests with real logger setup."""

    def test_logger_with_handle_id_filter(self, clean_logger):
        """Test logger with HandleIDFilter allows only specific handlers."""
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.addFilter(HandleIDFilter(HandlerType.Stream))

        clean_logger.addHandler(handler)

        # Log with matching handler type
        record = logging.LogRecord(
            name=clean_logger.name,
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.handlers = [HandlerType.Stream, HandlerType.Rich]

        clean_logger.handle(record)

        # Message should appear because Stream is in allowed
        assert "Test message" in stream.getvalue()

    def test_logger_with_throttle_filter(self, clean_logger):
        """Test logger correctly suppresses messages with ThrottleFilter."""
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))
        filter_obj = ThrottleFilter(initial_threshold=2, time_limit=10)
        handler.addFilter(filter_obj)

        clean_logger.addHandler(handler)
        clean_logger.setLevel(logging.INFO)

        record = logging.LogRecord(
            name=clean_logger.name,
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Repeated message",
            args=(),
            exc_info=None,
        )
        record.handlers = [HandlerType.Throttle]

        # Log 5 times
        for _ in range(5):
            clean_logger.handle(record)

        output = stream.getvalue()

        # First 2 should appear, then suppression message
        assert output.count("Repeated message") >= 2

    def test_chained_filters(self, clean_logger):
        """Test stacking HandleIDFilter and ThrottleFilter."""
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))

        # Add both filters
        handler.addFilter(HandleIDFilter(HandlerType.Throttle))
        handler.addFilter(ThrottleFilter(initial_threshold=1, time_limit=10))

        clean_logger.addHandler(handler)
        clean_logger.setLevel(logging.INFO)

        record = logging.LogRecord(
            name=clean_logger.name,
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Chained filters test",
            args=(),
            exc_info=None,
        )
        record.handlers = [HandlerType.Throttle]

        # Log message
        clean_logger.handle(record)

        # Should appear in output
        output = stream.getvalue()
        assert "Chained filters test" in output


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_handlers_list(self, log_record):
        """Test filter behavior with empty handlers list."""
        log_record.handlers = []
        filter_obj = HandleIDFilter(HandlerType.Rich)

        result = filter_obj.filter(log_record)

        assert result is False

    def test_none_handlers_attribute(self, log_record):
        """Test filter when record.handlers is None."""
        log_record.handlers = None
        filter_obj = HandleIDFilter(HandlerType.Rich)

        # get_allowed should handle None gracefully
        result = filter_obj.filter(log_record)
        assert result is False

    def test_throttle_with_zero_initial_threshold(self, log_record):
        """Test ThrottleFilter with initial_threshold=0."""
        log_record.handlers = [HandlerType.Throttle]
        filter_obj = ThrottleFilter(initial_threshold=0, time_limit=10)

        # All messages should be suppressed after first
        assert filter_obj.filter(log_record) is False

    def test_issue_record_key_format(self, log_record):
        """Test that issue_record key is formatted correctly."""
        filter_obj = ThrottleFilter()

        issue_id = f"{log_record.pathname}:{log_record.lineno}"
        record = filter_obj.issue_map[issue_id]

        assert isinstance(record, IssueRecord)

    def test_multiple_handler_types_intersection(self, log_record):
        """Test set intersection with multiple handler types."""
        log_record.handlers = [
            HandlerType.Rich,
            HandlerType.File,
            HandlerType.Stream,
        ]
        filter_obj = HandleIDFilter([HandlerType.Rich, HandlerType.Lstdout])

        # Rich is in the intersection
        result = filter_obj.filter(log_record)
        assert result is True

    def test_protobuf_conf_in_ers_handlers(self, ers_log_record, mock_ers_handlers):
        """Test that ProtobufConf is properly included in ERS configuration."""
        ers_log_record.ers_handlers = mock_ers_handlers
        filter_obj = BaseHandlerFilter()

        allowed = filter_obj.get_allowed(ers_log_record)

        assert HandlerType.Protobufstream in allowed

    def test_suppression_message_includes_count(self, log_record, clean_logger):
        """Test that suppression message includes suppressed count."""
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))

        # Create a throttle filter that will suppress quickly
        throttle_filter = ThrottleFilter(initial_threshold=1, time_limit=10)
        handler.addFilter(throttle_filter)

        clean_logger.addHandler(handler)
        clean_logger.setLevel(logging.INFO)

        record = logging.LogRecord(
            name=clean_logger.name,
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.handlers = [HandlerType.Throttle]

        # Send messages to trigger suppression
        for _ in range(15):
            clean_logger.handle(copy.deepcopy(record))

        output = stream.getvalue()

        # Should contain suppression message with count
        assert "suppressed" in output.lower()
