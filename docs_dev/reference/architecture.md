# Architecture reference: initialization and record flow

This page documents the runtime behaviour of the logging system — how loggers are initialised and how records flow through the system.

For the static structure of components (HandlerType, Specs, Filters, Strategies), see the [developer explanation](../explanation.md).

---

## Logger initialisation flow

When you build a logger and need to determine which handlers should be attached:

1. **You call** `get_daq_logger(...)` with flags like `rich_handler=True`, `stream_handlers=True`, etc.
2. **Logger setup** resolves which handlers to attach based on your flags
3. **For each handler type**, setup:
   - Looks it up in `HANDLER_SPEC_REGISTRY` and `FILE_SPEC_REGISTRY`
   - Calls the factory function to build it
   - Attaches a `HandleIDFilter` with the handler's routing identity
   - Installs it on the logger
4. **The fallback set** is composed from all enabled handlers. This becomes the default allowed set for records that don't carry explicit `extra["handlers"]`.

If you add ERS handlers via `setup_daq_ers_logger(...)`, the process is similar but with a critical difference:

1. **ERS env variables** are parsed (e.g., `DUNEDAQ_ERS_ERROR=...`)
2. **Handler types are extracted** from each severity's config (e.g., `throttle`, `lstdout`, `protobufstream(...)`)
3. **Handlers are built and attached** with `fallback_handler={HandlerType.Unknown}`
   - This is the key: ERS handlers **won't emit by default**
   - They only emit when explicitly requested by ERS severity routing (see `ERSAllowedHandlersStrategy`)
   - This prevents accidental spillover into standard logging
4. **Records are routed to ERS handlers only via ERS severity mapping**
   - A record marked `extra={"stream": StreamType.ERS}` triggers ERS-aware routing
   - The routing strategy maps Python level → ERS severity variable → handler set

![LogHandlerConf](../img/LHC_activity.png)

---

## Record flow

When you call `log.info("something")`, here's the actual flow:

1. **Python's logging creates a `LogRecord`** with your message, severity, and any `extra` metadata

2. **Logger-level filters run first** (e.g., `ThrottleFilter`):
   
   - If any filter returns `False`, the record stops here
   - It never reaches handlers
   - This is where global concerns like throttling happen

3. **Record is offered to each attached handler**

4. **Each handler's `HandleIDFilter` decides** whether to emit:
   
   - The filter calls the routing strategy to resolve `allowed_handlers`:
     - If `extra["handlers"]` is present, use it
     - Otherwise use the fallback set
     - If `stream == StreamType.ERS`, use ERS-specific routing
   - The filter checks: `handler_ids ∩ allowed_handlers`
   - Non-empty = emit; empty = drop the record

5. **Format and emit** (if the record passed the filter):
   
   - The handler formats it and emits (to file, stdout, kafka, etc.)

This two-stage filtering is key: logger-level filters decide "should ANY handler see this?" while handler-level filters decide "should THIS handler see this?"

![Filtering](../img/Filter_activity.png)


### Practical example

Here the practical logic flow is explained more with demonstrations. 

Lets say we have a logger that contains both a Rich and File handler, and we explicitly define what the fallback handlers is. 

```python
from daqpytools.logging import add_handler, HandlerType, get_daq_logger
log = get_daq_logger(
    "myapp",
    log_level="INFO",
    rich_handler=False,      # deliberately don't add handlers, we'll do it manually
)

add_handler(log,
   HandlerType.Rich, 
   use_parent_handlers=True
   fallback_handler={HandlerType.Rich} # default behaviour
   )
add_handler(
    log, 
    HandlerType.File, 
    use_parent_handlers=True,
    fallback_handler={HandlerType.File} # default behaviour
)

```

And now we investigate what happens if we send a log message with `log.info("msg", extra={"handlers": HandlerType.Rich})`. Here, the log message will be sent to both the Rich and File handlers for processing. In each handler, it will check to see what the allowed handlers are (lets call it `handlers_to_check_against`). In this case, since we set it explicitly when sending the mesage, `handlers_to_check_against = HandlerType.Rich`. 

For the Rich handler, it checks if the Rich handler is in the `handlers_to_check_against` list. In this case, it is, so it will transmit.

For the File handler, it will check if the File handler is in the `handlers_to_check_against` list. In this case, the file handler is _not_ in the list so it will not transmit the record.


Using the same setup, lets investigate what happens if we send a log a log message with `log.info("msg")`. In this case, the handlers keyword is not explicitly populated.

In this example, the record is sent independently to the two handlers. Since the handlers keyword is not set, the logic that populates `handlers_to_check_against` will check the `fallback_handlers` that are attached to each handler.

In the rich handler, we have initialised it with a fallback_handler of `HandlerType.Rich`, so `handlers_to_check_against = fallback_handler = HandlerType.Rich`. The rich handler will then check if the rich handler is in the `handlers_to_check_against`, which it is. So it will transmit the record.

In the file handler, we have initialised it with a fallback_handler of `HandlerType.File`, so `handlers_to_check_against = fallback_handler = HandlerType.File`. The file handler will then check if the file handler is in the `handlers_to_check_against`, which it is. So it will transmit the record.

This sounds a bit circular, but the reasoning for this should become clear in the case where we set different fallback handlers. Consider the following setup, where the only difference is that we set the the file handler's fallback_handler to `HandlerType.Unknown`:


```python
from daqpytools.logging import add_handler, HandlerType, get_daq_logger
log = get_daq_logger(
    "myapp",
    log_level="INFO",
    rich_handler=False,      # deliberately don't add handlers, we'll do it manually
)

add_handler(log,
   HandlerType.Rich, 
   use_parent_handlers=True
   fallback_handler={HandlerType.Rich} # default behaviour
   )
add_handler(
    log, 
    HandlerType.File, 
    use_parent_handlers=True,
    fallback_handler={HandlerType.Unknown} # Suppressing behaviour!
)
```

Transmitting `log.info("msg", extra={"handlers": HandlerType.Rich})` will yield identical results to before. However, transmitting `log.info("msg")` yields different results.

As before, the log record is _independently_ fed towards the two handlers. For the rich handler, the flow is identical and so it will transmit.

In the case of the file handler, we have initialised it with a fallback_handler of `HandlerType.Unknown`, so `handlers_to_check_against = fallback_handler = HandlerType.Unknown`. The file handler will then check if the file handler is in the `handlers_to_check_against = HandlerType.Unknown`, which it is _not_ as `HandlerType.File` is not in `HandlerType.Unknown`. So it will **suppress** the record. 

This has a very useful suppression effect, allowing the handlers to remain dormant by default. The only way to transmit with the file handler now is only if it was explicitly called for, by `log.info("msg", extra={"handlers": HandlerType.File})`


