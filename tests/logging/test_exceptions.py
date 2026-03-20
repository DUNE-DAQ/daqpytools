import logging

import pytest

from daqpytools.logging.exceptions import (
    ERSEnvError,
    ERSInitError,
    LoggerConfigurationError,
    LoggerHandlerError,
    LoggerSetupError,
    ProtobufFormatError,
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


def test_configuration_and_ers_related_exceptions() -> None:
    config_path = "tests/logging/log_format.ini"
    with pytest.raises(LoggerConfigurationError) as exc_info:
        raise LoggerConfigurationError(config_path, "bad section")
    assert f"Configuration file '{config_path}'" in str(exc_info.value)
    assert "bad section" in str(exc_info.value)

    with pytest.raises(ERSEnvError) as exc_info:
        raise ERSEnvError("DUNEDAQ_ERS_ERROR")
    assert str(exc_info.value) == "The environment variable DUNEDAQ_ERS_ERROR is empty"

    with pytest.raises(ERSInitError) as exc_info:
        raise ERSInitError("host:30092", "ers_stream")
    assert "address='host:30092'" in str(exc_info.value)
    assert "topic='ers_stream'" in str(exc_info.value)

    with pytest.raises(ProtobufFormatError) as exc_info:
        raise ProtobufFormatError("protobufstream(bad)")
    assert "protobufstream URLs must be formatted (url:port)." in str(exc_info.value)
    assert "protobufstream(bad)" in str(exc_info.value)
