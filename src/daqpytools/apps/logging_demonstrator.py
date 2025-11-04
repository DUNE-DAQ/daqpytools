import logging

import click
from rich.traceback import install as rich_traceback_install

from daqpytools.logging.exceptions import LoggerSetupError
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
@click.option("-o", "--stdout_handler", is_flag=True, help=("Set up a stdout handler"))
@click.option("-e", "--stderr_handler", is_flag=True, help=("Set up a stdout handler"))
@click.option("--ers", is_flag=True, help=("An ERS handler is always added in this demonstration. If set to true, publish to ERS"))
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
    stdout_handler: bool,
    stderr_handler: bool,
    child_logger: bool,
    disable_logger_inheritance: bool,
    ers: bool
) -> None:
    """Demonstrate use of the daq_logging class with daqpyutils_logging_demonstrator."""
    logger_name = "daqpytools_logging_demonstrator"

    validate_test_configuration(
        logger_name=logger_name,
        rich_handler=rich_handler,
        stdout_handler=stdout_handler,
        stderr_handler=stderr_handler,
        file_handler_path=file_handler_path,
    )

    main_logger: logging.Logger = get_daq_logger(
        logger_name="daqpytools_logging_demonstrator",
        log_level=log_level,
        use_parent_handlers=not disable_logger_inheritance,
        rich_handler=rich_handler,
        file_handler_path=file_handler_path,
        stream_stdout_handler=stdout_handler,
        stream_stderr_handler=stderr_handler,
        ers_protobuf_handler=True
    )
    main_logger.debug("example debug message")
    main_logger.info("example info message")
    main_logger.warning("example warning message")
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
    main_logger.debug("This should also appear in ERS if set", extra={"use_ers": ers})

    if child_logger:
        nested_logger: logging.Logger = get_daq_logger(
            logger_name="daqpytools_logging_demonstrator.child",
            log_level=log_level,
            use_parent_handlers=not disable_logger_inheritance,
            rich_handler=rich_handler,
            file_handler_path=file_handler_path,
            stream_stdout_handler=stdout_handler,
            stream_stderr_handler=stderr_handler,
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

    return


if __name__ == "__main__":
    main()
