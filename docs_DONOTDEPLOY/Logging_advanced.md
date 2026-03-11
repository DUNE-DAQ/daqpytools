
# Advanced Logging for Python in DUNE-DAQ

This page collects advanced user-facing logging patterns for daqpytools.

## Contents

- **Managing and manipulating the logger object** — Add handlers at runtime and pass configuration arguments
- **Understanding and configuring record transmissions** — Route records to handlers, understand streams, and configure ERS
- **Troubleshooting** — Common issues and solutions

For basic setup and common usage, start with `docs/Logging.md`.
For implementation internals, see `docs/dev_docs.md`.

---

## Managing and manipulating the logger object

You can configure handlers in two phases:

1. Build a logger first with `get_daq_logger(...)`.
2. Add more handlers/filters later, based on runtime context.

This is useful in long-running services where extra outputs (for example ERS Kafka) should only be attached after additional configuration becomes available.

### Managing handlers after logger creation

#### Add one handler at a time with `add_handler`

Use `add_handler` if you want to attach a single handler type to an existing logger.

```python
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

#### Suppress by default with `fallback_handler={HandlerType.Unknown}`

You can make newly-added handlers opt-in only by setting fallback handlers to `HandlerType.Unknown`. This means records without explicit `extra["handlers"]` will not be emitted by those handlers.

```python
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

### Passing arguments to handlers and filters via `**kwargs`

Advanced setup functions accept extra keyword arguments and forward them to the relevant handler/filter factories.

- `get_daq_logger(..., **extras)` forwards extras to handler/filter construction.
- `add_handler(..., **extras)` forwards extras to that handler factory.

Common examples:

- file handler: `path="mylog.log"`
- ERS Kafka handler: `ers_kafka_session=...`
- throttle filter: `initial_threshold=...`, `time_limit=...`
- rich handler: `width=...`

Example with explicit extras:

```python
from daqpytools.logging import HandlerType, add_handler, get_daq_logger

log = get_daq_logger("extras_demo", rich_handler=False)

# Pass file-specific kwargs to file handler
add_handler(
    log,
    HandlerType.File,
    use_parent_handlers=True,
    path="extras_demo.log",
)

# Pass rich-specific kwargs to rich handler
add_handler(
    log,
    HandlerType.Rich,
    use_parent_handlers=True,
    width=120,
)

# ERS-specific kwargs are supplied through setup/get APIs
# setup_daq_ers_logger(log, ers_kafka_session="session_tester")
```

---

## Understanding and configuring record transmissions

### Choosing handlers with HandlerTypes

You can route individual records to specific handlers by using `extra={"handlers": [...]}`:  

```python
from daqpytools.logging import HandlerType

log = get_daq_logger("example", rich_handler=True, file_handler_path="logging.log")

log.info("This will only go to Rich", extra={"handlers": [HandlerType.Rich]})
log.info("This will only go to File", extra={"handlers": [HandlerType.File]})
log.info("You can even send to both", extra={"handlers": [HandlerType.Rich, HandlerType.File]})
```

Note: Asking for a handler type that isn't attached is a no-op. Using `HandlerType.Stream` in the example above (when only Rich and File are attached) will be silently ignored.

### Understanding handler streams and routing

Within the DUNE DAQ ecosystem, there are several handler configurations that work together. The native implementation supports three logical **streams**:

- **Base** stream: Standard logging (Rich, File, Stream handlers)
- **OpMon** stream: Monitoring-related output
- **ERS** stream: Event Record System routing (severity-driven handler selection)

You can think of streams as different "channels" where each has its own set of handlers. The key insight: **ERS Kafka handlers and Throttle filters need to be explicitly activated via `HandlerType` tokens** because they're typically only used when specifically configured.

![streams](img/streams.png)

This is why routing via `extra={"handlers": [...]}` matters—it tells the logger which stream/handlers to use for each record.

### Using LogHandlerConf for structured routing

`LogHandlerConf` is a configuration dataclass that encapsulates the handler setup for different streams. It handles ERS environment variable parsing and creates routing metadata bundles that you attach to records via `extra`.

#### Understanding LogHandlerConf

The ERS configuration is defined in OKS and automatically parsed by daqpytools. A key feature: **handlers are severity-level dependent**. ERS Fatal and ERS Info may have different handler requirements.

`LogHandlerConf` manages this complexity:

```python
from daqpytools.logging import LogHandlerConf

handlerconf = LogHandlerConf()

# Access router metadata for each stream
main_logger.warning("Handlerconf Base", extra=handlerconf.Base)
main_logger.warning("Handlerconf Opmon", extra=handlerconf.Opmon)
```

This passes the appropriate handler routing metadata so the record is emitted to the right handlers for that stream.

#### Initialize ERS streams lazily

By default, `LogHandlerConf` does not initialize the ERS stream because it requires ERS environment variables. You can initialize it later when ERS becomes available:

```python
# By default init_ers is false
LHC = LogHandlerConf()  # ERS not initialized yet

print(LHC.Base)  # Success
print(LHC.ERS)   # Throws: ERS stream not initialised

# Later, when ERS envs are set
LHC.init_ers_stream()
print(LHC.ERS)   # Success
```

Or initialize upfront if ERS vars are already defined:

```python
LHC_with_ers = LogHandlerConf(init_ers=True)
```

### Configuring ERS handlers on an existing logger

Use `setup_daq_ers_logger` to attach ERS-derived handlers to an existing logger based on environment configuration.

```python
from daqpytools.logging import LogHandlerConf, get_daq_logger, setup_daq_ers_logger

log = get_daq_logger(
    logger_name="ers_logger",
    rich_handler=True,
    stream_handlers=False,
)

# Attach ERS-derived handlers (lstdout, protobufstream) to this logger
setup_daq_ers_logger(log, ers_kafka_session="session_temp")

# Now use LogHandlerConf routing to target ERS handlers
ers_conf = LogHandlerConf(init_ers=True)
log.info("ERS Info routing", extra=ers_conf.ERS)
log.warning("ERS Warning routing", extra=ers_conf.ERS)
log.error("ERS Error routing", extra=ers_conf.ERS)
```

---

## Troubleshooting

| Symptom | Likely cause | What to check | Fix |
|---|---|---|---|
| `Logger ... already exists with different handler configuration` | Same logger name reused with different constructor flags | Logger name and previous initialization path | Reuse same config for that name, or choose a new logger name |
| `Root logger ... already has handlers configured` | `setup_root_logger` called after handlers were already attached | Existing handlers on the named root logger | Use a fresh logger name or clear handlers before setup |
| Throttle filter appears to do nothing | `HandlerType.Throttle` is not in resolved allowed handlers for that record | `extra={"handlers": ...}` and stream metadata | Add `HandlerType.Throttle` to routing metadata for the messages you want throttled |
| ERS stream access raises `ERS stream not initialised` | `LogHandlerConf` created with `init_ers=False` and ERS not initialized yet | Whether `init_ers_stream()` was called | Call `init_ers_stream()` after ERS env vars are present |
| ERS setup fails due to missing env | One or more required `DUNEDAQ_ERS_*` variables are unset/empty | Environment before ERS init/setup | Export required ERS variables before initializing ERS |
| ERS setup fails with multiple protobuf endpoints | ERS env vars define different `protobufstream(url:port)` targets by severity | Parsed ERS vars across severities | Use one shared endpoint in Python setup path |
| Message not emitted to expected handler | Requested handler not attached or filtered out by routing | Attached handlers and `extra["handlers"]` values | Attach the handler at logger setup and include the right `HandlerType` on the record |
