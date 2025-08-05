import logging

import pytest

from daqpytools.logging.exceptions import (
    LoggerHandlerError,
    LoggerSetupError,
    LogLevelError,
)


def test_exceptions():
    """Test the custom exceptions."""
    # Test LogLevelError
    with pytest.raises(LogLevelError) as exc_info:
        raise LogLevelError("invalid_level")
    assert str(exc_info.value) == (
        "Level 'invalid_level' is not from the recognised levels (['CRITICAL', "
        "'ERROR', 'WARNING', 'INFO', 'DEBUG', 'NOTSET', 'kTopPriority', "
        "'kEventDriven', 'kDefault', 'kLowestPriority'])."
    )

    # Test LoggerHandlerError
    with pytest.raises(LoggerHandlerError) as exc_info:
        raise LoggerHandlerError("test_logger", logging.StreamHandler)
    assert str(exc_info.value) == (
        "One of the parents of test_logger already has a handler of type StreamHandler"
    )

    # # Test LoggerSetupError
    with pytest.raises(LoggerSetupError) as exc_info:
        raise LoggerSetupError("test_logger", "The test made me do it :(")
    assert str(exc_info.value) == (
        "Constructing test_logger failed as: \nThe test made me do it :("
    )
