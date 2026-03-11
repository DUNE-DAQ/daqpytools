# Advanced Logging for Python in DUNE-DAQ

This page collects advanced user-facing logging patterns for daqpytools.

For basic setup and common usage, start with `docs/Logging.md`.
For implementation internals, see `docs/dev_docs.md`.

## Advanced ways to initialize handlers on an existing logger

You can configure handlers in two phases:

1. Build a logger first with `get_daq_logger(...)`.
2. Add more handlers/filters later, based on runtime context.

This is useful in long-running services where extra outputs (for example ERS Kafka)
should only be attached after additional configuration becomes available.

### Add one handler at a time with `add_handler`

Use `add_handler` if you want to attach a single handler type to an existing logger.

```python
import logging

from daqpytools.logging import HandlerType, add_handler, get_daq_logger

log = get_daq_logger(
    logger_name="existing_logger",
    rich_handler=True,
    stream_handlers=False,
)

# Add stdout stream handler later
add_handler(log, HandlerType.Lstdout, use_parent_handlers=True)

log.info("Now routes to rich + stdout by default")
```

### Suppress by default with `fallback_handlers={HandlerType.Unknown}`

You can make newly-added handlers opt-in only by setting fallback handlers to
`HandlerType.Unknown`. This means records without explicit `extra["handlers"]`
will not be emitted by those handlers.

```python
import logging

from daqpytools.logging import HandlerType, add_handler, get_daq_logger

log = get_daq_logger("fallback_demo", rich_handler=True, stream_handlers=False)

# Add stderr handler, but suppress it by default
add_handler(
    log,
    HandlerType.Lstderr,
    use_parent_handlers=True,
    fallback_handler={HandlerType.Unknown},
)

log.critical("Only rich by default")

# Explicitly target stderr when needed
log.critical(
    "Rich + stderr when explicitly requested",
    extra={"handlers": [HandlerType.Rich, HandlerType.Lstderr]},
)
```

### Configure ERS handlers on an existing logger with `setup_daq_ers_logger`

If you already have a logger instance, `setup_daq_ers_logger` can attach handlers
based on ERS environment configuration.

```python
import logging

from daqpytools.logging import LogHandlerConf, get_daq_logger, setup_daq_ers_logger

log = get_daq_logger(
    logger_name="ers_existing_logger",
    rich_handler=True,
    stream_handlers=False,
)

# Attach ERS-derived handlers (for example lstdout/protobufstream) to this logger
setup_daq_ers_logger(log, ers_kafka_session="session_temp")

ers_conf = LogHandlerConf(init_ers=True)
log.info("ERS Info routing", extra=ers_conf.ERS)
log.warning("ERS Warning routing", extra=ers_conf.ERS)
log.error("ERS Error routing", extra=ers_conf.ERS)
```

### How `**kwargs` are propagated

Advanced setup functions accept extra keyword arguments and pass them to the relevant
handler/filter factories.

- `get_daq_logger(..., **extras)` forwards extras to handler/filter construction.
- `add_handler(..., **extras)` forwards extras to that handler factory.

Common examples:

- file handler: `path="mylog.log"`
- ERS Kafka handler: `ers_kafka_session=...` via `get_daq_logger(...)` or
  `setup_daq_ers_logger(...)`
- throttle filter: `initial_treshold=...`, `time_limit=...`
- rich handler: `width=...`

Example with explicit extras:

```python
from daqpytools.logging import HandlerType, add_handler, get_daq_logger

log = get_daq_logger("extras_demo", rich_handler=False)

# pass file-specific kwargs to file handler
add_handler(
    log,
    HandlerType.File,
    use_parent_handlers=True,
    path="extras_demo.log",
)

# pass rich-specific kwargs to rich handler
add_handler(
    log,
    HandlerType.Rich,
    use_parent_handlers=True,
    width=120,
)

# ERS-specific kwargs are supplied through setup/get APIs
# setup_daq_ers_logger(log, ers_kafka_session="session_tester")
```
