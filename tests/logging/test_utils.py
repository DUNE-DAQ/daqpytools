import pytest

from daqpytools.logging.exceptions import LogLevelError
from daqpytools.logging.levels import logging_log_levels, oks_log_levels
from daqpytools.logging.utils import log_level_to_int

test_log_level_str = "INFO"
oks_log_level_str = "kDefault"
test_log_level_int = logging_log_levels[test_log_level_str]
oks_log_level_int = oks_log_levels[oks_log_level_str]
test_unknown_log_level_str = "UNKNOWN"
test_unknown_log_level_int = 9999


def test_logging_str_to_logging_int():
    """Validate the conversion of a logging level string to an int."""
    assert log_level_to_int(test_log_level_str) == test_log_level_int


def test_logging_int_to_logging_int():
    """Validate the conversion of a logging level int to an int."""
    assert log_level_to_int(test_log_level_int) == test_log_level_int


def test_oks_str_to_logging_int():
    """Validate the conversion of an OKS logging level string to an int."""
    assert log_level_to_int(oks_log_level_str) == test_log_level_int


def test_oks_int_to_logging_int():
    """Validate the conversion of an OKS logging level int to an int."""
    assert log_level_to_int(oks_log_level_int) == test_log_level_int


def test_unknown_str_to_logging_int():
    """Validate the conversion of an unknown logging level string raises an error."""
    with pytest.raises(LogLevelError):
        log_level_to_int(test_unknown_log_level_str)


def test_unknown_int_to_logging_int():
    """Validate the conversion of an unknown logging level int raises an error."""
    with pytest.raises(LogLevelError):
        log_level_to_int(test_unknown_log_level_int)
