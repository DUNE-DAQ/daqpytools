import logging
import os
import click
from rich.traceback import install as rich_traceback_install

from daqpytools.logging.exceptions import LoggerSetupError
from daqpytools.logging.handlers import (
    HandlerConf,
    HandlerType,
    dummy_add_ERSTrace_handler,
    dummy_add_Lstdout_handler,
    dummy_add_Throttle_handler,
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
    "--ers", 
    is_flag=True, 
    help=(
        "Set up an ERS handler, and publish to ERS"
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
    ers: bool
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
        ers (bool): If true, sets up an ERS protobuf handler. A log message will always 
            be printed to stdout to demonstrate an ERS message; if true, this log 
            message will also be published to ers. 

    Returns:
        None

    Raises:
        LoggerSetupError: If no handlers are set up for the logger.
    """
    logger_name = "daqpytools_logging_demonstrator"

    #! Initialise the main logger and all the relevant handlers
    main_logger: logging.Logger = get_daq_logger(
        logger_name=logger_name,
        log_level=log_level,
        use_parent_handlers=not disable_logger_inheritance,
        rich_handler=rich_handler,
        file_handler_path=file_handler_path,
        stream_handlers=stream_handlers,
        ers_protobuf_handler=True
    )
    dummy_add_Lstdout_handler(main_logger, True)
    dummy_add_ERSTrace_handler(main_logger, True)
    dummy_add_Throttle_handler(main_logger, True)
    

    #* Test choosing which handler to use individually
    main_logger.critical("Default go to tty / rich / file when added")
    main_logger.critical("Should only go to tty", extra={"handlers": [HandlerType.Rich]})
    main_logger.critical("Should only go to file", extra={"handlers": [HandlerType.File]})
    main_logger.critical("Should only go to Lstdout", extra={"handlers": [HandlerType.Lstdout]})
    main_logger.critical("Should only go to ERSTrace", extra={"handlers": [HandlerType.ERSTrace]})
    main_logger.critical("Should only go to Throttle", extra={"handlers": [HandlerType.Throttle]})
    # main_logger.critical("Should go to tty and ERS", extra={"handlers": [HandlerType.Rich, HandlerType.ERS]})



    #* Interlude: Inject environment variables
    os.environ["DUNEDAQ_ERS_ERROR"] = "erstrace,throttle,lstdout" #,protobufstream(monkafka.cern.ch:30092)
    os.environ["DUNEDAQ_ERS_CRITICAL"] = "erstrace"
    main_logger.info(f"{os.getenv('DUNEDAQ_ERS_ERROR')=}")
    main_logger.info(f"{os.getenv('DUNEDAQ_ERS_CRITICAL')=}")


    """
    DUNEDAQ_ERS_ERROR="erstrace,throttle,lstdout,protobufstream(monkafka.cern.ch:30092)"
    DUNEDAQ_ERS_CRITICAL="erstrace"

    That should be fatal in the next step
    """

    #* Test the routing to 'Opmon' and base (no ers)    
    handlerconf = HandlerConf()
    main_logger.warning("Handlerconf Base", extra=handlerconf.Base)
    main_logger.warning("Handlerconf Opmon", extra=handlerconf.Opmon)

    # #* Test ERS routing
    main_logger.error("Error now goes to erstrace,throttle,lstdout", extra=handlerconf.ERS)
    main_logger.critical("ers critical should just be erstrace", extra=handlerconf.ERS)

    #! Right so whats the next gameplan for you
    # Simplify the handlertype for kafka, it should just be a number / simple string
    # Fix up the oks parser, that should get you the usual ers handlertypes, and in the case of kafka it should also generate and return the kafkaconf thing
    # Think about how it would work if there are many different kafka streams..
    # Propagate the kafka protobuf thingys
    # Once that is done, test it out on the logger demonstrator
    



    # #! What about
    # main_logger.error("msg", extra={"handlerconf": handlerconf, "streamtype": streamtype.ers})
    
    # main_logger.debug("None", extra={"handlers": handlerconf.ERS})
    # main_logger.info("erstrace,throttle,lstdout,protobufstream", extra={"handlers": handlerconf.ERS})
    # main_logger.warning("erstrace,throttle,lstdout,protobufstream", extra={"handlers": handlerconf.ERS})
    # main_logger.critical("erstrace,lstdout,protobufstream", extra={"handlers": handlerconf.ERS})


    # main_logger.info(f"{os.getenv('DUNEDAQ_ERS_INFO')=}")
    
    
    #! So basically
    # The two ideas I have basically boil down to 'do we want to initialise it in handler conf or in the handlers themself?'


    """
    So you feed something like main_logger.info in , it passes through the logging level, and then its gonna have to do a few things
    
    - First check if it is 'ers' that is specifically called for
    - Check the log level to see what it can be passed with 
    - Only apply those that it asks for 

    # Maybe we can have handlerconf.ers resolve to handlers=something, ers=true? 
    # and have the rest of it resolve to just list of handlers? that could work? its a bit ugly tho


    And what do we want? 
    handlerconf.base  resolves to base
    handlerconf.opmon resolves to opmon
    handler.ers _checks_ the log levels and then resolves to ers_{log_level}
    I think handlerconf needs to be initialised with the full set of filters 


    I mean the best thing is if we just have extra=handler.base/opmon/ers and have that resolve into itself
    we have the handler.obj, and that gets passed into the filter itself




    """


    # Okay lets try to explain it to chatgpt

    # I have a question regarding logging in python thats a bit complicated that I want your advice on.


    # I have a set of handlers that exists, lets call it RichHandler, FileHandler, Throttle, and StreamHandler. A logging instance would have _all_ of it.

    # I want to organise this into different streams, lets call it Base, Opmon, and the 'ERS' streams. Base and Opmon are simple:
    # Base: Rich + File
    # Opmon: Stream + File.

    # We can control this behaviour using filters in each of the handlers

    # The hard part is ERS, because the set of handlers which come out is entirely dependent on the log level that we send it to. Eg. log.info() would have a different set of handlers that we want to use. Eg:

    # ERS_critical: Rich
    # ERS_info: Rich + Throttle.

    # The basic use case should be something like
    # log.info("msg", extra=HandlerConf.Opmon) -> goes to stream + file 
    # log.info("msg", extra=HandlerConf.ERS) -> goes to rich + throttle
    # log.critical("msg", extra=HandlerConf.ERS) -> goes to Rich


    # How can I design a set of python objects that do this? 



    # Maybe have a 
    # stream: ERS
    # Handlers: {set of handlers}? 


    # Filter:
    # - check if stream is ers. 
    #     If stream is ers, pick up the relevant ers_{log_level}
    #     else continue with the current set of base Handlers


    # basic_streams
    # {
    #     Base: [Rich, File]
    #     Opmon: [Stream, File]
    # }

    # ers_streams
    # {
    #     ers_critical: [rich]
    #     ers_info: [rich + throttle]
    # }


    # Can you just have it so that if its a normal basic stream, it just gives you the list
    # but if the stream is ERS, then it returns a dictionary? 
    # and then let the filter select? Ahh but that suckss

    


    

    # main_logger.debug("This should also appear in ERS if set", extra={"use_ers": ers})

    # if child_logger:
    #     nested_logger: logging.Logger = get_daq_logger(
    #         logger_name=f"{logger_name}.child",
    #         log_level=log_level,
    #         use_parent_handlers=not disable_logger_inheritance,
    #         rich_handler=rich_handler,
    #         file_handler_path=file_handler_path,
    #         stream_handlers=stream_handlers,
    #     )
    #     nested_logger.debug("example debug message")
    #     nested_logger.info("example info message")
    #     nested_logger.warning("example warning message")
    #     nested_logger.error("example error message")
    #     nested_logger.critical("example critical message")
    #     nested_logger.info(
    #         "[dim cyan]You[/dim cyan] "
    #         "[bold green]can[/bold green] "
    #         "[bold yellow]also[/bold yellow] "
    #         "[bold red]add[/bold red] "
    #         "[bold white on red]colours[/bold white on red] "
    #         "[bold red]to[/bold red] "
    #         "[bold yellow]your[/bold yellow] "
    #         "[bold green]log[/bold green] "
    #         "[dim cyan]record[/dim cyan] "
    #         "[bold green]text[/bold green] "
    #         "[bold yellow]with[/bold yellow] "
    #         "[bold green]markdown[/bold green]!"
    #     )
    #     nested_logger.warning(
    #         "Note: [red] the daqpytools.logging.formatter removes markdown-style "
    #         "comments from the log record message [/red]."
    #     )

    return


if __name__ == "__main__":
    main()
