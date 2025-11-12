import logging
import tempfile

import pytest

from daqpytools.logging.exceptions import LoggerSetupError
from daqpytools.logging.logger import (
    setup_root_logger,
    get_daq_logger
)

test_logger_name = "test_logger"
test_logger_child_name = f"{test_logger_name}.child"


def test_setup_root_logger():
    """
    Test the setup_root_logger function.
    """
    # Set up the root logger
    root_logger = setup_root_logger(test_logger_name, "INFO")
    assert isinstance(root_logger, logging.Logger)
    assert root_logger.name == test_logger_name
    assert root_logger.level == logging.INFO

    # Test that sh loggers are set to WARNING level
    sh_logger = logging.getLogger("sh")
    assert sh_logger.level == logging.WARNING
    for sh_logger_handler in sh_logger.handlers:
        assert sh_logger_handler.level == logging.WARNING

    # Test that kafka loggers are set to WARNING level
    kafka_logger = logging.getLogger("kafka")
    assert kafka_logger.level == logging.WARNING
    for kafka_logger_handler in kafka_logger.handlers:
        assert kafka_logger_handler.level == logging.WARNING

    # Change the log level, assert the sh and kafka loggers are updated accordingly
    setup_root_logger(test_logger_name, "ERROR")
    assert root_logger.level == logging.ERROR
    assert sh_logger.level == logging.ERROR
    for sh_logger_handler in sh_logger.handlers:
        assert sh_logger_handler.level == logging.ERROR
    assert kafka_logger.level == logging.ERROR
    for kafka_logger_handler in kafka_logger.handlers:
        assert kafka_logger_handler.level == logging.ERROR

    # Test that adding a handler to the root logger and setting it up again raises an error
    root_logger.addHandler(logging.NullHandler())
    with pytest.raises(LoggerSetupError, match="already has handlers configured."):
        setup_root_logger(test_logger_name, "DEBUG")

    # Cleanup handlers
    for _logger in [root_logger, sh_logger, kafka_logger]:
        for handler in _logger.handlers[:]:
            _logger.removeHandler(handler)

    # Remove loggers
    for name in [test_logger_name, "sh", "kafka"]:
        logging.root.manager.loggerDict.pop(name, None)
    
    # Shutdown logging to reset any internal state
    logging.shutdown()

def test_rich_daq_logger():
    """
    Test the get_daq_logger function with rich handler.
    """
    test_logger: logging.Logger = get_daq_logger(
        logger_name=test_logger_name,
        log_level= "DEBUG",
        use_parent_handlers=True,
        rich_handler=True,
    )

    # Test that the correct handler has been defined
    handler_names = [type(handler).__name__ for handler in test_logger.handlers]
    assert "FormattedRichHandler" in handler_names
    assert "StreamHandler" not in handler_names
    assert "FileHandler" not in handler_names

    # Cleanup handlers
    for handler in test_logger.handlers[:]:
        test_logger.removeHandler(handler)

    # Remove logger
    logging.root.manager.loggerDict.pop(test_logger_name, None)
    
    # Shutdown logging to reset any internal state
    logging.shutdown()



def test_get_daq_logger(caplog):
    temp_file = tempfile.NamedTemporaryFile()
    log_path = temp_file.name
    
    # Setup testing root logger
    test_root_logger: logging.Logger = setup_root_logger(
        logger_name=test_logger_name,
        log_level= "DEBUG",
    )
    assert isinstance(test_root_logger, logging.Logger)
    assert test_root_logger.name == test_logger_name
    assert test_root_logger.level == logging.DEBUG

    # Setup testing daq logger
    test_logger: logging.Logger = get_daq_logger(
        logger_name=test_logger_child_name + "0",
        log_level= "DEBUG",
        use_parent_handlers=True,
        rich_handler=False,
        file_handler_path=log_path,
        stream_handlers=True,
    )

    # Test that the correct handlers have been defined
    handler_types = [type(handler) for handler in test_logger.handlers]
    assert logging.StreamHandler in handler_types
    assert logging.FileHandler in handler_types

    # Test if logging level set to what what it was initialised with
    assert test_logger.getEffectiveLevel() == logging.DEBUG

    # Test if logging level can be changed
    test_logger.setLevel("INFO")
    assert test_logger.getEffectiveLevel() == logging.INFO

    test_logger.setLevel("WARNING")
    assert test_logger.getEffectiveLevel() == logging.WARNING
    
    test_logger.setLevel("ERROR")
    assert test_logger.getEffectiveLevel() == logging.ERROR

    test_logger.setLevel("CRITICAL")
    assert test_logger.getEffectiveLevel() == logging.CRITICAL

    # Generate a child logger. Test that by default this is initialised with log level INFO    
    # This is the case even if the parent logger has a different log level
    assert get_daq_logger(test_logger_child_name + "1").getEffectiveLevel() == logging.INFO

    # Test if a new child logger can be initialised with a different log level
    assert get_daq_logger(test_logger_child_name + "2", "WARNING").getEffectiveLevel() == logging.WARNING

    # Test if the child logger can be changed
    get_daq_logger(test_logger_child_name + "3").setLevel("INFO")
    assert get_daq_logger(test_logger_child_name + "4").getEffectiveLevel() == logging.INFO

    # Test logging to a file
    logger = get_daq_logger(test_logger_child_name + "0.0", "CRITICAL")
    logger.debug("invisible")
    logger.info("invisible")
    logger.warning("invisible")
    logger.error("invisible")
    logger.critical("VISIBLE") # Caps to avoid false positives
    good_record = 0
    bad_record = 0
    for record in caplog.records:
        if (
            "VISIBLE" in record.getMessage()
            and record.levelno == logging.CRITICAL
            and f"{test_logger_child_name}0.0" in record.name
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
    
    # Validate that you cannot set up the same logger with different handlers
    with pytest.raises(
        LoggerSetupError,
        match="already exists with different handler configuration.",
    ):
        get_daq_logger(
            logger_name=test_logger_name,
            log_level= "DEBUG",
            use_parent_handlers=True,
            rich_handler=True,  # Different from initial setup
            file_handler_path=log_path,
            stream_handlers=True,
        )

    # Cleanup handlers
    loggers = [
        test_logger,
        get_daq_logger(test_logger_child_name + "1"),
        get_daq_logger(test_logger_child_name + "2"),
        get_daq_logger(test_logger_child_name + "3"),
        get_daq_logger(test_logger_child_name + "4"),
        get_daq_logger(test_logger_child_name + "5"),
    ]
    for _logger in loggers:
        for handler in _logger.handlers[:]:
            _logger.removeHandler(handler)

    # Remove loggers
    for name in loggers:
        logging.root.manager.loggerDict.pop(name, None)
    
    # Shutdown logging to reset any internal state
    logging.shutdown()

