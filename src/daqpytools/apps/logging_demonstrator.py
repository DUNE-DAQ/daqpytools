import logging
import os
import time
import click
from rich.traceback import install as rich_traceback_install

from daqpytools.logging.exceptions import LoggerSetupError
from daqpytools.logging.handlers import (
    HandlerType,
    LogHandlerConf,
    dummy_add_erstrace_handler,
    ThrottleFilter,
)
from daqpytools.logging.levels import logging_log_level_keys
from daqpytools.logging.logger import get_daq_logger
from daqpytools.logging.utils import get_width


def validate_test_configuration(
    logger_name: str,
    rich_handler: bool,
    stdout_handler: bool,
    stderr_handler: bool,
    file_handler_path: str | None = None,
) -> None:
    """Checks for one or less stream-type handler associated with the root logger."""
    file_handler = False
    if file_handler_path:
        file_handler = True

    if not any([rich_handler, stdout_handler, stderr_handler, file_handler]):
        err_msg = (
            "At least one of rich_handler, stdout_handler, stderr_handler, or "
            "file_handler_path must be set."
        )
        rich_traceback_install(show_locals=True, width=get_width())
        raise LoggerSetupError(logger_name, err_msg)
    return


@click.command()
@click.option(
    "-l",
    "--log-level",
    type=click.Choice(logging_log_level_keys, case_sensitive=False),
    default="DEBUG",
    help="Set the log level.",
)
@click.option("-r", "--rich_handler", is_flag=True, help=("Set up a rich handler"))
@click.option(
    "-f",
    "--file-handler-path",
    type=str,
    help=(
        "Set up a file handler with the given path. If provided with leading backslash "
        "treated as absolute, otherwise as relative."
    ),
)
@click.option(
    "--ersprotobufstream", 
    is_flag=True, 
    help=(
        "Set up an ERS handler, and publish to ERS"
        )
    )
@click.option(
    "--handlertypes", 
    is_flag=True, 
    help=(
        "Demonstrate HandlerTypes functionality"
        )
    )
@click.option(
    "--throttle", 
    is_flag=True, 
    help=(
        "Demonstrate throttling functionality"
        )
    )
@click.option(
    "-s",
    "--stream_handlers",
    is_flag=True,
    help=("Set up stdout and stderr stream handlers"),
)
@click.option(
    "-c",
    "--child-logger",
    is_flag=True,
    help=(
        "If true, sets up a child logger to the demonstrator logger and assigns it the "
        "same logger handlers as the parent loggers."
    ),
)
@click.option(
    "-d",
    "--disable-logger-inheritance",
    is_flag=True,
    help=(
        "If true, disable logger inheritance so each logger instance only uses the "
        "logger handlers assigned to the given logger instance"
    ),
)
def main(
    log_level: str,
    rich_handler: bool,
    file_handler_path: str,
    stream_handlers: bool,
    child_logger: bool,
    disable_logger_inheritance: bool,
    ersprotobufstream: bool,
    handlertypes:bool,
    throttle: bool,
) -> None:
    """Demonstrate use of the daq_logging class with daqpyutils_logging_demonstrator.
    Note - if you are seeing output logs without any explicit handlers assigned, this is
    expected - python loggers propagate to the root logger by default, which has a
    default stderr stream handler assigned if a record ever reaches it.

    Args:
        log_level (str): Log level to set for the logger.
        rich_handler (bool): If true, set up a rich handler.
        file_handler_path (str): If provided, set up a file handler with the given path.
        stream_handlers (bool): If true, set up stdout and stderr stream handlers.
        child_logger (bool): If true, sets up a child logger to the demonstrator logger.
        disable_logger_inheritance (bool): If true, disable logger inheritance so each
            logger instance only uses the logger handlers assigned to the given logger
            instance.
        ersprotobufstream (bool): If true, sets up an ERS protobuf handler. Error msg
            are demonstrated in the HandlerType demonstration, requiring handlertypes
            to be set to true.
        handlertypes (bool): If true, demonstrates the advanced feature of HandlerTypes
            and streams.

    Returns:
        None

    Raises:
        LoggerSetupError: If no handlers are set up for the logger.
    """
    logger_name = "daqpytools_logging_demonstrator"

    main_logger: logging.Logger = get_daq_logger(
        logger_name=logger_name,
        log_level=log_level,
        use_parent_handlers=not disable_logger_inheritance,
        rich_handler=rich_handler,
        file_handler_path=file_handler_path,
        stream_handlers=stream_handlers,
        ers_kafka_handler=ersprotobufstream,
        throttle=throttle
    )


    

    # main_logger.debug("example debug message")

    # HandlerTypes demo
    if not handlertypes:
        return

    # #* Add all dummy handlers which have not been developed yet
    dummy_add_ERSTrace_handler(main_logger, True)
    
    def emit_err(i):
        main_logger.critical(f"Throttle test {i}", extra={"handlers": [HandlerType.File, HandlerType.Throttle]})

    main_logger.critical("Throw me",extra={"handlers": [HandlerType.Throttle]} )
    main_logger.critical("Throw file me",extra={"handlers": [HandlerType.Throttle, HandlerType.File,]} )

    # #* Test choosing which handler to use individually
    for i in range(50):
        emit_err(i)
    time.sleep(6)
    emit_err(0)

    for i in range(500000):
        emit_err(i)

    
    os.environ["DUNEDAQ_ERS_WARNING"] = "erstrace,throttle,lstdout"
    os.environ["DUNEDAQ_ERS_INFO"] = "erstrace,throttle,lstdout"
    os.environ["DUNEDAQ_ERS_FATAL"] = "erstrace,lstdout"
    os.environ["DUNEDAQ_ERS_ERROR"] = (
        "erstrace,"
        "throttle,"
        "lstdout,"
        "protobufstream(monkafka.cern.ch:30092)"
    )


    
    handlerconf = LogHandlerConf()
    main_logger.warning("Handlerconf Base", extra=handlerconf.Base)
    main_logger.critical("ERS Fatal erstrace,lstdout", extra=handlerconf.ERS)

    # test ers throttling
    for i in range(100):
        main_logger.warning("ERS warning throttle erstrace,lstdout", extra=handlerconf.ERS)


    # main_logger.critical("Should only go to tty", extra={"handlers": [HandlerType.Rich]})
    # main_logger.critical("Should only go to file", extra={"handlers": [HandlerType.File]})
    # main_logger.critical("Should only go to Lstdout", extra={"handlers": [HandlerType.Lstdout]})
    # main_logger.critical("Should only go to ERSTrace", extra={"handlers": [HandlerType.ERSTrace]})
    # main_logger.critical("Should only go to Throttle", extra={"handlers": [HandlerType.Throttle]})
    # main_logger.critical("Should go to tty and Protobufstream", extra={"handlers": [HandlerType.Rich, HandlerType.Protobufstream]})
    return


if __name__ == "__main__":
    main()
