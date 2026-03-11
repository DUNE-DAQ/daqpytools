import logging
import os
import time

import click
from rich.traceback import install as rich_traceback_install

from daqpytools.logging.exceptions import LoggerSetupError
from daqpytools.logging.formatter import CONTEXT_SETTINGS
from daqpytools.logging.handlerconf import LogHandlerConf
from daqpytools.logging.handlers import (
    HandlerType,
    add_handler,
)
from daqpytools.logging.levels import logging_log_level_keys
from daqpytools.logging.logger import get_daq_logger, setup_daq_ers_logger
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



def test_main_functions(main_logger:logging.Logger) -> None:
    """Demonstrates the main functionality of the daqpytools logger.
    
    Args:
        main_logger (logging.Logger): A logger to print messages with
    """
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
        logger_name:str,
        log_level: int|str,
        disable_logger_inheritance:bool,
        rich_handler:bool,
        file_handler_path: str,
        stream_handlers:bool,
) -> None:
    """Demonstrates inheritance with child handlers.

    Args:
        logger_name (str): Name of the initial parent logger.
        log_level (str): Log level to set for the logger.
        
        disable_logger_inheritance (bool): If true, disable logger inheritance so each
            logger instance only uses the logger handlers assigned to the given logger
            instance.
        rich_handler (bool): If true, set up a rich handler.
        file_handler_path (str): If provided, set up a file handler with the given path.
        stream_handlers (bool): If true, set up stdout and stderr stream handlers.
    """
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

def test_throttle(main_logger: logging.Logger) -> None:
    """Demonstrates the throttle filter.
    
    Args:
        main_logger (logging.Logger): A logger to print messages with
    """
    def emit_err(i: int) -> None:
        """Short function that prints out a log message.
        This is used to ensure that the log message is kept on the same line,
        but also to feed in how many repetitions it has gone through
        Args:
            i (int): Integer to be transmitted in the log message.

        Returns:
            None.
        """
        throttle_msg = f"Throttle test {i}"
        main_logger.info(throttle_msg, extra={"handlers": 
            [HandlerType.Rich, HandlerType.Throttle]
        })
    
    for i in range(50):
        emit_err(i)
    main_logger.warning("Sleeping for 30 seconds")
    time.sleep(31)
    for i in range(1000):
        emit_err(i)
    

def test_handlertypes(main_logger: logging.Logger) -> None:
    """Demonstrates the handlertype functionality.
    Note - to have the messages published, the relevant handlers must be enabled.
    
    Args:
        main_logger (logging.Logger): A logger to print messages with
    """
    #* Test choosing which handler to use individually
    main_logger.debug("Default go to whatever handlers were initialised with")
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


def test_handlerconf(main_logger: logging.Logger) -> None:
    """Demonstrates the main functionality of the handlerconf. With ERS support.
    
    Args:
        main_logger (logging.Logger): A logger to print messages with
    """
    #* Test the routing to the Base and Opmon streams
    handlerconf = LogHandlerConf(init_ers=False) # False is the default
    main_logger.warning("Handlerconf Base", extra=handlerconf.Base)
    main_logger.warning("Handlerconf Opmon", extra=handlerconf.Opmon)

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

    #* Init ERS stream
    # Note to developers:
    # HandlerConf will require that these variables are defined!
    # They come from the OKS, so whatever tools you have should have this up
    # You can also initialise via handlerconf = LogHandlerConf(init_ers=True)
    handlerconf.init_ers_stream()
    
    #* Test ERS Streams
    main_logger.warning("ERS Warning erstrace,throttle,lstdout", extra=handlerconf.ERS)
    main_logger.info("ERS Info erstrace,throttle,lstdout", extra=handlerconf.ERS)
    main_logger.critical("ERS Fatal erstrace,lstdout", extra=handlerconf.ERS)
    main_logger.debug("ERS Debug none", extra=handlerconf.ERS)
    main_logger.error("ERS Error erstrace,throttle,lstdout,"
        "protobufstream(monkafka.cern.ch:30092)", 
        extra=handlerconf.ERS
    )     


def test_fallback_handlers(log_level: str) -> None:
    """Demonstrate fallback handler behavior for a logger.

    Args:
        log_level (str): Log level used to initialize the demo logger.

    Returns:
        None
    """
    fallback_log: logging.Logger = get_daq_logger(
        logger_name="fallback_logger",
        log_level=log_level,
        stream_handlers=False,
        rich_handler=True,
    )

    fallback_log.info("Rich Only")
    
    add_handler(
        fallback_log,
        HandlerType.Lstdout,
        True
    )

    add_handler(
        fallback_log,
        HandlerType.Lstderr,
        True,
        fallback_handler = {HandlerType.Unknown}
    )
    
    fallback_log.critical("Rich + stdout only")
    fallback_log.critical(
        "Rich + stdout + stderr",
        extra={"handlers": [HandlerType.Rich, HandlerType.Stream]},
    )

    
def test_ers_handler_configuration(log_level: str) -> None:
    """Demonstrate ERS-driven handler configuration for a logger.

    Args:
        log_level (str): Log level used to initialize the demo logger.

    Returns:
        None
    """
    # Injecting specific 
    os.environ["DUNEDAQ_ERS_WARNING"] = "rich"
    os.environ["DUNEDAQ_ERS_INFO"] = "lstdout"
    os.environ["DUNEDAQ_ERS_FATAL"] = "lstderr,rich"
    os.environ["DUNEDAQ_ERS_ERROR"] = "rich"

    ers_logger: logging.Logger = get_daq_logger(
        logger_name="ers_logger",
        log_level=log_level,
        stream_handlers=False,
        rich_handler=True,
    )
    ers_logger.info("Just rich is added")
   
    # Sets up the logger with all the relevant handlers
    setup_daq_ers_logger(ers_logger, "session_temp")
    ers_logger.info("ERS configured, but should still only be rich")
    
    ers_hc = LogHandlerConf(init_ers=True)
    ers_logger.info("ERS Info lstdout ", extra=ers_hc.ERS)
    ers_logger.warning("ERS error lstdout", extra=ers_hc.ERS)
    ers_logger.critical("ERS critical lstderr + rich", extra=ers_hc.ERS)


class AllOptionsCommand(click.Command):
    """Parse the arguments passed and validate they are acceptable, otherwise print the
    relevant options.

    Click's default functionality does not pick up the optional arguments well. This
    catches any incorrect options or typos, makes the log clearer.
    """
    def parse_args(self, ctx: click.Context, args: list[str]) -> None:
        """Parse the arguments passed to the click command, format them if necessary.

        Args:
            ctx: click context from which the commands are called
            args: list of args to format

        Returns:
            None

        Raises:
            None
        """
        # If the arguments are valid, run the command with the relevant arguments
        try:
            return super().parse_args(ctx, args)
        except click.NoSuchOption as e:
            # Get the list of available options, format them in a readable way
            formatted_opts = []
            
            for param in self.params:
                if isinstance(param, click.Option) and param.opts:
                    # For each option, format as "short_opt (long_opt)"
                    opts = sorted(param.opts, key=len)
                    
                    if len(opts) > 1:
                        # Multiple options
                        formatted_opts.append(f"{opts[0]} ({opts[1]})")
                    else:
                        # One long option
                        formatted_opts.append(opts[0])
            
            # Inform the user why what they have tried to use is wrong
            click.echo(ctx.get_usage() + "\n", err=True)
            
            # Print formatted available options
            msg = (
                f"Error: No such option: {e.option_name}. \n"
                f"Available options: {', '.join(sorted(formatted_opts))}"
            )
            click.echo(msg, err=True)
            ctx.exit(2)

@click.command(cls=AllOptionsCommand, context_settings=CONTEXT_SETTINGS)
@click.option(
    "-l",
    "--log-level",
    type=click.Choice(logging_log_level_keys, case_sensitive=False),
    default="DEBUG",
    help="Set the log level.",
)
@click.option("-r", "--rich-handler", is_flag=True, help=("Set up a rich handler"))
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
    "-ep",
    "--ersprotobufstream", 
    type=str,
    help=(
        "Set up an ERS protobuf handler, and publish to ERS via protobuf."
        )
    )
@click.option(
    "-eh",
    "--ershandlers",
    is_flag=True,
    help=(
        "Demonstrate automatic logger configuration with ers variables."
        )
    )
@click.option(
    "-ht",
    "--handlertypes", 
    is_flag=True, 
    help=(
        "Demonstrate HandlerTypes functionality"
        )
    )
@click.option(
    "-hc",
    "--handlerconf", 
    is_flag=True, 
    help=(
        "Demonstrate HandlerConf functionality"
        )
    )
@click.option(
    "-sb",
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
    "--stream-handlers",
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
@click.option(
    "-fh",
    "--fallback-handlers",
    is_flag=True,
    help=(
        "If true, demonstrates the use of fallback handlers."
    ),
)
def main(
    log_level: str,
    rich_handler: bool,
    file_handler_path: str,
    stream_handlers: bool,
    child_logger: bool,
    disable_logger_inheritance: bool,
    ersprotobufstream: str,
    handlertypes:bool,
    handlerconf:bool,
    throttle: bool,
    suppress_basic: bool,
    fallback_handlers: bool,
    ershandlers: bool,

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
        ersprotobufstream (str): Sets up an ERS protobuf handler with supplied
            session name. Error msg
            are demonstrated in the HandlerType demonstration, requiring handlerconf
            to be set to true. The topic for these tests is session_tester.
        handlertypes (bool): If true, demonstrates the advanced feature of HandlerTypes.
        handlerconf (bool): If true, demonstrates the advanced feature of HandlerConf
            and streams.
        throttle (bool): If true, demonstrates the throttling feature. Requires Rich.
        suppress_basic (bool): If true, supresses basic functionality. 
            Useful to only test the advanced features of logging
        fallback_handlers (bool): If true, demonstrates fallback handler behavior.
        ershandlers (bool): If true, demonstrates ERS-based handler setup.

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
        ers_kafka_session=ersprotobufstream,
        ers_app_name="Custom App Name", # Can be none!
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
    if fallback_handlers:
        test_fallback_handlers(log_level)
    if ershandlers:
        test_ers_handler_configuration(log_level)

if __name__ == "__main__":
    main()
