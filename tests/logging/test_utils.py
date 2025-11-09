import pytest
import tempfile
import logging

from daqpytools.logging.exceptions import LogLevelError, LoggerSetupError
from daqpytools.logging.levels import logging_log_levels, oks_log_levels
from daqpytools.logging.utils import log_level_to_int
from daqpytools.logging.logger import get_daq_logger

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


def test_setup_logger(caplog):
    temp_file = tempfile.NamedTemporaryFile()
    log_path = temp_file.name
    
    # Setup root logger
    root_logger: logging.Logger = get_daq_logger(
        logger_name="root",
        log_level= "DEBUG",
        use_parent_handlers=True,
        rich_handler=True,
        file_handler_path=log_path,
        stream_stdout_handler=False,
        stream_stderr_handler=False,
    )

    # Test if logging level set to what what it was initialised with
    assert root_logger.getEffectiveLevel() == logging.DEBUG

    # Test if logging level can be changed
    root_logger.setLevel("INFO")
    assert root_logger.getEffectiveLevel() == logging.INFO

    root_logger.setLevel("WARNING")
    assert root_logger.getEffectiveLevel() == logging.WARNING
    
    root_logger.setLevel("ERROR")
    assert root_logger.getEffectiveLevel() == logging.ERROR

    root_logger.setLevel("CRITICAL")
    assert root_logger.getEffectiveLevel() == logging.CRITICAL

    # Generate a child logger. Test that by default this is initialised with log level INFO    
    # This is the case even if the parent logger has a different log level
    assert get_daq_logger("tester0").getEffectiveLevel() == logging.INFO

    # Test if a new child logger can be initialised with a different log level
    assert get_daq_logger("tester1", "WARNING").getEffectiveLevel() == logging.WARNING

    # Test if the child logger can be changed
    get_daq_logger("tester1").setLevel("INFO")
    assert get_daq_logger("tester1").getEffectiveLevel() == logging.INFO

    # Test logging to a file
    logger = get_daq_logger("tester2", "CRITICAL")
    logger.debug("invisible")
    logger.info("invisible")
    logger.warning("invisible")
    logger.error("invisible")
    logger.critical("VISIBLE")
    good_record = 0
    bad_record = 0
    for record in caplog.records:
        if (
            "VISIBLE" in record.getMessage()
            and record.levelno == logging.CRITICAL
            and "tester2" in record.name
        ):
            good_record += 1
        else:
            bad_record += 1

    assert good_record == 1
    assert bad_record == 0

    with open(log_path) as f:
        temp_file_data = f.read()
        assert "VISIBLE" in temp_file_data
        assert "invisible" not in temp_file_data

    temp_file.close()

    # Test if loggers fail to initialise with conflicting handlers
    with pytest.raises(LoggerSetupError):
        failing_logger: logging.Logger = get_daq_logger(
            logger_name="root",
            log_level= "DEBUG",
            use_parent_handlers=True,
            rich_handler=True,
            file_handler_path=log_path,
            stream_stdout_handler=True,
            stream_stderr_handler=True,
        )



