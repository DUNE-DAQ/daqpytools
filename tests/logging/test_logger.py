import logging
import tempfile

import pytest

from daqpytools.logging.exceptions import LoggerSetupError
from daqpytools.logging.logger import (
    validate_setup_configuration,
    get_daq_logger
)

test_logger_name = "test_logger"
test_logger_child_name = f"{test_logger_name}.child"

def test_validate_setup_configuration():
    """
    Test the validate_setup_configuration function.
    """
    # Test case where rich_handler is True and stream_handlers is False
    assert validate_setup_configuration(
        logger_name=test_logger_name,
        rich_handler=True,
        stream_handlers=False,
    ) == None

    # Test case where rich_handler and stream_handlers are both True
    with pytest.raises(LoggerSetupError) as exc_info:
        validate_setup_configuration(
            logger_name=test_logger_name,
            rich_handler=True,
            stream_handlers=True,
        )
    assert "choose one!" in str(exc_info.value)




# def test_setup_logger(caplog):
#     temp_file = tempfile.NamedTemporaryFile()
#     log_path = temp_file.name
    
#     # Setup root logger
#     test_logger: logging.Logger = get_daq_logger(
#         logger_name="test_logger",
#         log_level= "DEBUG",
#         use_parent_handlers=True,
#         rich_handler=True,
#         file_handler_path=log_path,
#         stream_handlers=False,
#     )

#     # Test if logging level set to what what it was initialised with
#     assert test_logger.getEffectiveLevel() == logging.DEBUG

#     # Test if logging level can be changed
#     test_logger.setLevel("INFO")
#     assert test_logger.getEffectiveLevel() == logging.INFO

#     test_logger.setLevel("WARNING")
#     assert test_logger.getEffectiveLevel() == logging.WARNING
    
#     test_logger.setLevel("ERROR")
#     assert test_logger.getEffectiveLevel() == logging.ERROR

#     test_logger.setLevel("CRITICAL")
#     assert test_logger.getEffectiveLevel() == logging.CRITICAL

#     # Generate a child logger. Test that by default this is initialised with log level INFO    
#     # This is the case even if the parent logger has a different log level
#     assert get_daq_logger("test_logger.child1").getEffectiveLevel() == logging.INFO

#     # Test if a new child logger can be initialised with a different log level
#     assert get_daq_logger("test_logger.child2", "WARNING").getEffectiveLevel() == logging.WARNING

#     # Test if the child logger can be changed
#     get_daq_logger("tester1").setLevel("INFO")
#     assert get_daq_logger("tester1").getEffectiveLevel() == logging.INFO

#     # Test logging to a file
#     logger = get_daq_logger("tester2", "CRITICAL")
#     logger.debug("invisible")
#     logger.info("invisible")
#     logger.warning("invisible")
#     logger.error("invisible")
#     logger.critical("VISIBLE")
#     good_record = 0
#     bad_record = 0
#     for record in caplog.records:
#         if (
#             "VISIBLE" in record.getMessage()
#             and record.levelno == logging.CRITICAL
#             and "tester2" in record.name
#         ):
#             good_record += 1
#         else:
#             bad_record += 1

#     assert good_record == 1
#     assert bad_record == 0

#     with open(log_path) as f:
#         temp_file_data = f.read()
#         assert "VISIBLE" in temp_file_data
#         assert "invisible" not in temp_file_data

#     temp_file.close()

#     # Test if loggers fail to initialise with conflicting handlers
#     with pytest.raises(LoggerSetupError):
#         failing_logger: logging.Logger = get_daq_logger(
#             logger_name="root",
#             log_level= "DEBUG",
#             use_parent_handlers=True,
#             rich_handler=True,
#             file_handler_path=log_path,
#             stream_stdout_handler=True,
#             stream_stderr_handler=True,
#         )



