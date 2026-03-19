# How to add a new handler

This page walks through adding a new handler to daqpytools.logging from scratch.

**Important:** You'll be editing files in the daqpytools repository itself. The main files you'll work with are:
- `src/daqpytools/logging/handlerconf.py` — Handler/filter type definitions
- `src/daqpytools/logging/handlers.py` — Handler implementations and registry
- `src/daqpytools/logging/filters.py` — Filter implementations and registry
- `src/daqpytools/logging/logger.py` — Logger setup (optional for Step 6)

For how the system actually works, start with the [developer explanation](../explanation.md).
For adding filters instead, see [How to add a new filter](./add-a-filter.md).

---

Let's say you want to add a handler that formats and displays log records in the terminal, similar to `FormattedRichHandler` but with a custom initialization name instead of a timezone.

## Step 1: Add a `HandlerType` enum value

In `handlerconf.py`, add your handler to the `HandlerType` enum:

```python
class HandlerType(Enum):
    # ... existing handlers ...
    CustomTerminal = "custom_terminal"
```

Guidelines:

- Use lowercase, snake_case for the string value (matches ERS token parsing)
- Choose a name that clearly describes what it does

## Step 2: Implement the handler class and factory function

In `handlers.py`, create your handler:

```python
import logging
import sys

class CustomTerminalHandler(logging.StreamHandler):
    """Emits formatted log records to terminal with a custom name."""
    
    def __init__(self, name: str):
        super().__init__(sys.stdout)
        self.name_label = name
        # Use a simple formatter that includes the custom name
        fmt = f"[{name}] %(levelname)-8s | %(message)s"
        self.setFormatter(logging.Formatter(fmt))
    
    def emit(self, record: logging.LogRecord):
        """Emit the record to stdout."""
        try:
            msg = self.format(record)
            self.stream.write(msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)


def build_custom_terminal_handler(name: str, **extras) -> CustomTerminalHandler:
    """Build a custom terminal handler.
    
    Args:
        name: Name label to display (e.g., 'APP', 'SERVICE'). Required.
        **extras: ignored, for compatibility with setup functions
    
    Returns:
        Configured CustomTerminalHandler instance
    """
    return CustomTerminalHandler(name)
```

Key points:

- The factory accepts `**extras` for compatibility with logger setup functions
- The handler only knows *how* to emit (format and write to stdout)
- Fail clearly if required args are missing — don't silently use defaults

## Step 3: Define a `HandlerSpec`

Create a spec that describes your handler metadata:

```python
from specs import HandlerSpec

custom_terminal_spec = HandlerSpec(
    alias=HandlerType.CustomTerminal,
    handler_class=CustomTerminalHandler,
    factory=build_custom_terminal_handler,
    fallback_types=(HandlerType.CustomTerminal,),
)
```

`fallback_types` is the set of routing tokens this handler responds to. When the routing strategy resolves the allowed handlers, any token in `fallback_types` will trigger this handler to emit.

Best practice: `fallback_types` should include all the `HandlerType` keys that can load this handler. Typically this is just the `alias` itself (e.g., `(HandlerType.CustomTerminal,)`). But if your handler handles multiple roles (like `Stream` handling both `Lstdout` and `Lstderr`), include all applicable tokens in the tuple.

## Step 4: Register the spec

Add it to the registry:

```python
from handlers import HANDLER_SPEC_REGISTRY

HANDLER_SPEC_REGISTRY[HandlerType.CustomTerminal] = custom_terminal_spec
```

The registry is the "catalog" of all handler types. When setup code needs to build a handler, it looks it up here.

## Step 5: Test it locally

Create a clean logger and attach your handler:

```python
import logging
from daqpytools.logging import HandlerType, get_daq_logger, add_handler

# Start with a clean logger (no handlers attached)
log = get_daq_logger(
    "test_app",
    log_level="DEBUG",
    rich_handler=False,  # don't add any handlers yet
    stream_handlers=False,
)

# Attach your new handler
add_handler(
    log,
    HandlerType.CustomTerminal,
    use_parent_handlers=True,
    name="MYAPP",  # passed to the factory
)

# Test: standard logging (uses fallback)
log.info("This goes to MYAPP")  # Emits (CustomTerminal in fallback)

# Test: explicit routing (overrides fallback)
log.info("Also to MYAPP", extra={"handlers": [HandlerType.CustomTerminal]})

# Test: explicit exclusion (no fallback, empty override)
log.info("Silently dropped", extra={"handlers": [HandlerType.Unknown]})
```

## Step 6: (Optional) Add it to `get_daq_logger`

If you want users to enable your handler directly via `get_daq_logger(...)`, add a parameter:

**In `logger.py`, update `get_daq_logger`:**

```python
def get_daq_logger(
    logger_name: str,
    log_level: int | str = logging.NOTSET,
    use_parent_handlers: bool = True,
    rich_handler: bool = False,
    file_handler_path: str | None = None,
    stream_handlers: bool = False,
    ers_kafka_session: str | None = None,
    throttle: bool = False,
    custom_terminal_name: str | None = None,  # Add this
    **extras: object
) -> logging.Logger:
    # ... docstring ...
    
    fallback_handlers: set[HandlerType] = set()
    if rich_handler:
        fallback_handlers.add(HandlerType.Rich)
    if file_handler_path:
        fallback_handlers.add(HandlerType.File)
    if stream_handlers:
        fallback_handlers.add(HandlerType.Stream)
    if custom_terminal_name:  # Add this
        fallback_handlers.add(HandlerType.CustomTerminal)
    if ers_kafka_session:
        fallback_handlers.add(HandlerType.Protobufstream)
    if throttle:
        fallback_handlers.add(HandlerType.Throttle)
    
    add_handlers_from_types(
        logger,
        fallback_handlers,
        use_parent_handlers,
        fallback_handlers,
        path=file_handler_path,
        session_name=ers_kafka_session,
        name=custom_terminal_name,  # Pass it through
        **extras
    )
```

Now users can attach it directly:

```python
from daqpytools.logging import get_daq_logger

log = get_daq_logger(
    "myapp",
    log_level="INFO",
    rich_handler=True,
    custom_terminal_name="SERVICE",  # Your handler is now in fallback
)

log.info("Goes to both Rich and CustomTerminal")  # Emits to both
```

Best practices:
- If your handler needs a **single required argument** (like file path), make that the parameter: `custom_terminal_path: str | None`
- If it needs a **single optional boolean flag**, use: `custom_terminal_enabled: bool = False`
- If it needs **multiple required arguments**, use a boolean flag and fail in `add_handler` if args are missing
- Always pass handler-specific args via `**extras` in the logger setup

## Step 7: (Optional) Add ERS support (if applicable)

If your handler should be controllable via ERS environment variables:

1. Your `HandlerType` string already works as an ERS token (e.g., `custom_terminal`)
2. The parser will recognize it automatically (if it's in the enum)
3. Users can enable it via:

```bash
DUNEDAQ_ERS_ERROR="custom_terminal,throttle,lstdout"
```

Note: Beyond daqpytools, this requires adding the variable to OKS configurations for your DAQ system.

## Common mistakes to avoid

- **Don't hardcode routing logic in the handler.** It should only know *how* to emit. Filters decide *when*.
- **Don't silently ignore missing required args.** Fail fast with a clear error.
- **Don't skip `**extras` in the factory.** Accept it even if you don't use it — other parts of the system rely on this.
- **Don't register the same handler type twice.** The system prevents duplicate handlers on a single logger.
