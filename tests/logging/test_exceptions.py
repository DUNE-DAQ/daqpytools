import logging

import pytest

from daqpytools.logging.exceptions import (
    LoggerHandlerError,
    LoggerSetupError,
)


def test_exceptions():
    """Test the custom exceptions."""
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
