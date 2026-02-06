import logging
import os
import time

import click
from rich.traceback import install as rich_traceback_install

from daqpytools.logging.exceptions import LoggerSetupError
from daqpytools.logging.handlers import (
    HandlerType,
    LogHandlerConf,
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



def test_main_functions(main_logger):
    main_logger.debug("example debug message")
    main_logger.info("example info message")
    main_logger.warning("example warning message")
    
    # Error and critical will print twice when using stream handlers
    # This is because StreamHandlers add in a stream each for stdout and stderr
    # stderr log level set to error, so at error or above both handlers will fire
    main_logger.error("example error message")
    main_logger.critical("example critical message")
    main_logger.info(
        "[dim cyan]You[/dim cyan] "
        "[bold green]can[/bold green] "
        "[bold yellow]also[/bold yellow] "
        "[bold red]add[/bold red] "
        "[bold white on red]colours[/bold white on red] "
        "[bold red]to[/bold red] "
        "[bold yellow]your[/bold yellow] "
        "[bold green]log[/bold green] "
        "[dim cyan]record[/dim cyan] "
        "[bold green]text[/bold green] "
        "[bold yellow]with[/bold yellow] "
        "[bold green]markdown[/bold green]!"
    )
    main_logger.warning(
        "Note: [red] the daqpytools.logging.formatter removes markdown-style "
        "comments from the log record message [/red]."
    )

def test_child_logger(
        logger_name,
        log_level,
        disable_logger_inheritance,
        rich_handler,
        file_handler_path,
        stream_handlers
):
        nested_logger: logging.Logger = get_daq_logger(
            logger_name=f"{logger_name}.child",
            log_level=log_level,
            use_parent_handlers=not disable_logger_inheritance,
            rich_handler=rich_handler,
            file_handler_path=file_handler_path,
            stream_handlers=stream_handlers,
        )
        nested_logger.debug("example debug message")
        nested_logger.info("example info message")
        nested_logger.warning("example warning message")
        nested_logger.error("example error message")
        nested_logger.critical("example critical message")
        nested_logger.info(
            "[dim cyan]You[/dim cyan] "
            "[bold green]can[/bold green] "
            "[bold yellow]also[/bold yellow] "
            "[bold red]add[/bold red] "
            "[bold white on red]colours[/bold white on red] "
            "[bold red]to[/bold red] "
            "[bold yellow]your[/bold yellow] "
            "[bold green]log[/bold green] "
            "[dim cyan]record[/dim cyan] "
            "[bold green]text[/bold green] "
            "[bold yellow]with[/bold yellow] "
            "[bold green]markdown[/bold green]!"
        )
        nested_logger.warning(
            "Note: [red] the daqpytools.logging.formatter removes markdown-style "
            "comments from the log record message [/red]."
        )

def test_throttle(main_logger):
    
    emit_err = lambda i: main_logger.info(
        f"Throttle test {i}",
        extra={"handlers": [HandlerType.Rich, HandlerType.Throttle]},
    )
    
    for i in range(50):
        emit_err(i)
    main_logger.warning("Sleeping for 30 seconds")
    time.sleep(31)
    for i in range(1000):
        emit_err(i)
    

def test_handlertypes(main_logger):
    #* Test choosing which handler to use individually
    main_logger.debug("Default go to tty / rich / file when added")
    main_logger.critical("Should only go to tty", 
        extra={"handlers": [HandlerType.Rich]}
    )
    main_logger.critical("Should only go to file", 
        extra={"handlers": [HandlerType.File]}
    )
    main_logger.critical("Should only go to Lstdout",
        extra={"handlers": [HandlerType.Lstdout]}
    )
    main_logger.critical("Should only go to Throttle",
        extra={"handlers": [HandlerType.Throttle]}
    )
    main_logger.critical("Should go to tty and Protobufstream", 
        extra={"handlers": [HandlerType.Rich, HandlerType.Protobufstream]}
    )


def test_handlerconf(main_logger):
    #* Interlude: Inject sample environment variables
    os.environ["DUNEDAQ_ERS_WARNING"] = "erstrace,throttle,lstdout"
    os.environ["DUNEDAQ_ERS_INFO"] = "erstrace,throttle,lstdout"
    os.environ["DUNEDAQ_ERS_FATAL"] = "erstrace,lstdout"
    os.environ["DUNEDAQ_ERS_ERROR"] = (
        "erstrace,"
        "throttle,"
        "lstdout,"
        "protobufstream(monkafka.cern.ch:30092)"
    )
        
    info_out = f"{os.getenv('DUNEDAQ_ERS_ERROR')=}"
    main_logger.info(info_out)
    critical_out = f"{os.getenv('DUNEDAQ_ERS_CRITICAL')=}"
    main_logger.info(critical_out)

    #* Test the routing to the Base and Opmon streams
    handlerconf = LogHandlerConf()
    main_logger.warning("Handlerconf Base", extra=handlerconf.Base)
    main_logger.warning("Handlerconf Opmon", extra=handlerconf.Opmon)

    #* Test ERS Streams
    main_logger.warning("ERS Warning erstrace,throttle,lstdout", extra=handlerconf.ERS)
    main_logger.info("ERS Info erstrace,throttle,lstdout", extra=handlerconf.ERS)
    main_logger.critical("ERS Fatal erstrace,lstdout", extra=handlerconf.ERS)
    main_logger.debug("ERS Debug none", extra=handlerconf.ERS)
    main_logger.error("ERS Error erstrace,throttle,lstdout,"
        "protobufstream(monkafka.cern.ch:30092)", 
        extra=handlerconf.ERS
    )     

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
    "--handlerconf", 
    is_flag=True, 
    help=(
        "Demonstrate HandlerConf functionality"
        )
    )
@click.option(
    "--suppress-basic", 
    is_flag=True, 
    help=(
        "Suppress demonstration of basic logging functionality"
        )
    )
@click.option(
    "-t",
    "--throttle", 
    is_flag=True, 
    help=(
        "Demonstrate throttling functionality. Requires Rich handlers"
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
    handlerconf:bool,
    throttle: bool,
    suppress_basic: bool
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
            are demonstrated in the HandlerType demonstration, requiring handlerconf
            to be set to true.
        handlertypes (bool): If true, demonstrates the advanced feature of HandlerTypes.
        handlerconf (bool): If true, demonstrates the advanced feature of HandlerConf
            and streams.
        throttle (bool): If true, demonstrates the throttling feature. Requires Rich.
        supress_basic (bool): If true, supresses basic functionality. Useful to only test 
            the advanced features of logging

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

    if not suppress_basic:
        test_main_functions(main_logger)
    
    if child_logger: 
        test_child_logger(
            logger_name,
            log_level,
            disable_logger_inheritance,
            rich_handler,
            file_handler_path,
            stream_handlers
        )

    if throttle:
        test_throttle(main_logger)
    if handlertypes:
        test_handlertypes(main_logger)
    if handlerconf:
        test_handlerconf(main_logger)


if __name__ == "__main__":
    main()
