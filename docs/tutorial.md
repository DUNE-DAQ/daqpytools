# Getting Started with Logging in DUNE-DAQ

<!-- YOU SHOULD WRITE A BRIEF INTRO HERE: one paragraph orienting a brand new user to what they will accomplish by the end of this tutorial (e.g. "By the end of this page you will have a working logger printing coloured output to your terminal"). Keep it concrete and task-focused. -->

## Prerequisites

<!-- YOU SHOULD WRITE ABOUT: what the reader needs before starting — DUNE environment loaded, daqpytools installed, etc. -->

## Step 1: Initialize a logger

Initializing a logger instance is simple:

```python
from daqpytools.logging import get_daq_logger
test_logger = get_daq_logger(
    logger_name = "test_logger", # Set as your logger name. Preferrably it should be relevant to what module / file you are in 
    log_level = "INFO", # Default level you will transmit at or above. In this case, Debugs will not be transmitted
    use_parent_handlers = True, # Just keep this true
    
    ## the rest are whatever handlers you want to attach. Read on for what exists. Rich is your standard TTY logger so the vast majority will be using this
    rich_handler = True, 
    stream_handlers = False # you dont really need this; its False by default
)
```

For now, **please see the docstring of `get_daq_logger` to see what stuff you can have and what to initialise with.**

## Step 2: Emit your first messages

```python
test_logger.info("Hello, world!")

test_logger.info(
        "[dim cyan]Look[/dim cyan] "
        "[bold green]at[/bold green] "
        "[bold yellow]all[/bold yellow] "
        "[bold red]the[/bold red] "
        "[bold white on red]colours![/bold white on red] "
)
```

## Step 3: Explore with the logging demonstrator

A lot of the available features can be demonstrated via the logging demonstrator functionality. With the DUNE environments loaded, simply run:

```
daqpytools-logging-demonstrator
```

and view the help string to learn more, and view the script itself in the repository to see how it is implemented.

## Next steps

- To understand *why* logging works the way it does, read the [Concepts & explanation](./explanation.md).
- To learn how to use specific handlers and filters, see the [How-to guides](./how-to/).
- For a full API reference, see the [Reference](./reference/).
- If you are introducing logging to your Python repo, or upgrading an existing implementation, **please** read the [Logging best practices](./how-to/best-practices.md).
