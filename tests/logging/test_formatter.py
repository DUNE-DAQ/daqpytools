import logging
from datetime import datetime

from daqpytools.logging.formatter import (
    DATE_TIME_FORMAT,
    LOG_RECORD_PADDING,
    TIME_ZONE,
    LoggingFormatter,
)

test_line_no: int = 10
test_logger_name: str = "test_logger"
test_file_name: str = "test_path.py"
record: logging.LogRecord = logging.LogRecord(
    name=test_logger_name,
    level=logging.INFO,
    pathname="test_path.py",
    lineno=test_line_no,
    msg="Test message",
    args=None,
    exc_info=None,
)
test_timestamp: float = 1700000000.0
record.created = test_timestamp

formatter: logging.Formatter = LoggingFormatter()
formatted_message: str = formatter.format(record)

padding: int = 0


def test_formatter_time_format():
    """Validate the expetcted time stamp is generated."""
    expected_time = datetime.fromtimestamp(test_timestamp, TIME_ZONE).strftime(
        DATE_TIME_FORMAT
    )
    assert expected_time in formatted_message


def test_formatter_file_lineno():
    """Validate the correct format is generated."""
    padding = LOG_RECORD_PADDING.get("file_and_line")
    expected_file_lineno = f"test_path.py:{test_line_no}".ljust(padding)[:padding]
    assert expected_file_lineno in formatted_message


def test_formatter_name_level_message():
    """Validate the correct format and spacing is generated."""
    padding = LOG_RECORD_PADDING.get("logger_name")
    expected_name = (test_logger_name + ":").ljust(padding)[:padding]
    assert expected_name in formatted_message


def test_formatter_level_format():
    """Validate the log level is formatted correctly."""
    padding = LOG_RECORD_PADDING.get("level")
    expected_level = "INFO".ljust(padding)[:padding]
    assert expected_level in formatted_message


def test_formatter_message_content():
    """Validate the message content is included in the formatted message."""
    assert "Test message" in formatted_message
