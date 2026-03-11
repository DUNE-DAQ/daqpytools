# Extending the Logging System

This page covers how to add new handlers and filters to **daqpytools.logging**.

**Important:** You'll be editing files in the daqpytools repository itself. The main files you'll work with are:
- `src/daqpytools/logging/handlerconf.py` — Handler/filter type definitions
- `src/daqpytools/logging/handlers.py` — Handler implementations and registry
- `src/daqpytools/logging/filters.py` — Filter implementations and registry
- `src/daqpytools/logging/logger.py` — Logger setup (optional for Step 6)

For how the system actually works, start with `docs/dev_docs.md`.
For user-facing patterns, see `docs/Logging.md` and `docs/Logging_advanced.md`.

---

## Adding a new handler

Let's say you want to add a handler that formats and displays log records in the terminal, similar to `FormattedRichHandler` but with a custom initialization name instead of a timezone.

### Step 1: Add a `HandlerType` enum value

In `handlerconf.py`, add your handler to the `HandlerType` enum:

```python
class HandlerType(Enum):
    # ... existing handlers ...
    CustomTerminal = "custom_terminal"
```

Guidelines:

- Use lowercase, snake_case for the string value (matches ERS token parsing)
- Choose a name that clearly describes what it does

### Step 2: Implement the handler class and factory function

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
- Fail clearly if required args are missing—don't silently use defaults

### Step 3: Define a `HandlerSpec`

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

### Step 4: Register the spec

Add it to the registry:

```python
from handlers import HANDLER_SPEC_REGISTRY

HANDLER_SPEC_REGISTRY[HandlerType.CustomTerminal] = custom_terminal_spec
```

The registry is the "catalog" of all handler types. When setup code needs to build a handler, it looks it up here.

### Step 5: Test it locally

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

### Step 6: (Optional) Add it to `get_daq_logger`

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

### Step 7: (Optional) Add ERS support (if applicable)

If your handler should be controllable via ERS environment variables:

1. Your `HandlerType` string already works as an ERS token (e.g., `custom_terminal`)
2. The parser will recognize it automatically (if it's in the enum)
3. Users can enable it via:

```bash
DUNEDAQ_ERS_ERROR="custom_terminal,throttle,lstdout"
```

Note: Beyond daqpytools, this requires adding the variable to OKS configurations for your DAQ system.

### Common mistakes to avoid

- **Don't hardcode routing logic in the handler.** It should only know *how* to emit. Filters decide *when*.
- **Don't silently ignore missing required args.** Fail fast with a clear error.
- **Don't skip `**extras` in the factory.** Accept it even if you don't use it—other parts of the system rely on this.
- **Don't register the same handler type twice.** The system prevents duplicate handlers on a single logger.

---

## Adding a new logger-level filter

Logger-level filters are attached to the logger itself (not individual handlers) and run before any handler sees the record.

**Important:** Logger-level filters are **only active when explicitly activated**. A filter only applies its logic if its `HandlerType` is present in the record's allowed handlers set. This prevents filters from unexpectedly activating on all records.

Let's add a custom filter that only processes records containing specific metadata.

### Implementation

In `filters.py`:

```python
from filters import BaseHandlerFilter
from routing import DefaultAllowedHandlerStrategy
from handlerconf import HandlerType
import logging

class MetadataAwareFilter(BaseHandlerFilter):
    """Only pass records that match specific metadata patterns."""
    
    def __init__(
        self,
        required_keyword: str,
        fallback_handlers: set[HandlerType],
        allowed_handlers_strategy: AllowedHandlersStrategy
    ):
        super().__init__(fallback_handlers, allowed_handlers_strategy)
        self.required_keyword = required_keyword
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Return False to suppress records missing the keyword in extra."""
        # Check if we want to apply the filter
        if not (allowed := self.get_allowed(record)):
            return False
        if HandlerType.MetadataAware not in allowed:
            return True  # Filter not active, pass record through
        
        # Filter is active - apply the metadata check
        if hasattr(record, self.required_keyword):
            return True  # Pass it through
        return False  # Suppress it


def build_metadata_aware_filter(
    required_keyword: str = "metadata",
    fallback_handlers: set[HandlerType] = None,
    **extras
) -> MetadataAwareFilter:
    """Build a metadata-aware filter.
    
    Args:
        required_keyword: Name of the extra field to check for (e.g., "session_id")
        fallback_handlers: Default allowed handler set
        **extras: ignored
    
    Returns:
        Configured MetadataAwareFilter instance
    """
    if fallback_handlers is None:
        fallback_handlers = set()
    
    strategy = DefaultAllowedHandlerStrategy(fallback_handlers)
    return MetadataAwareFilter(required_keyword, fallback_handlers, strategy)
```

Look at `ThrottleFilter` in `filters.py` to see how this pattern is implemented in practice.

> **Future improvement:** This activation pattern should be standardized to be more universal. For now, each new filter follows the same two-step check: resolve the allowed set, then verify the filter's own type is present before applying logic.

Then define and register it (in `handlerconf.py` and `filters.py`):

```python
# In handlerconf.py, add to HandlerType enum:
class HandlerType(Enum):
    # ... existing ...
    MetadataAware = "metadata_aware"

# In filters.py, add to registry:
FILTER_SPEC_REGISTRY[HandlerType.MetadataAware] = FilterSpec(
    alias=HandlerType.MetadataAware,
    filter_class=MetadataAwareFilter,
    factory=build_metadata_aware_filter,
    fallback_types=(HandlerType.MetadataAware,),
)
```

### Using it

```python
from daqpytools.logging import HandlerType, get_daq_logger, add_handler

log = get_daq_logger(
    "myapp",
    rich_handler=True,
)

# Add the filter (it won't activate yet)
add_handler(
    log,
    HandlerType.MetadataAware,
    required_keyword="session_id",
)

# This record passes (filter not active, no explicit MetadataAware requested)
log.info("Missing metadata")

# This record is filtered (filter is now active via extra, and session_id is missing)
log.info("No session", extra={"handlers": [HandlerType.MetadataAware]})

# This record passes (filter active but session_id is present)
log.info("Has metadata", extra={"handlers": [HandlerType.MetadataAware], "session_id": "abc123"})
```

### Key points about logger-level filters

- They run **before** handlers, so if they reject a record, no handler sees it
- They **only activate when explicitly requested** via their `HandlerType` in `extra={"handlers": [...]}`
- They inherit from `BaseHandlerFilter` to participate in routing logic
- They DON'T need a `HandleIDFilter` (that's for handlers)
- They're global to the logger, not per-handler

---

## Debugging and verification checklist

When you're implementing a new handler or filter and something doesn't work:

### Check handler attachment

```python
log = get_daq_logger("test", rich_handler=True)
add_handler(log, HandlerType.MyCustomService, endpoint="http://localhost")

# What's actually attached?
for h in log.handlers:
    print(f"Handler: {h}")
    for f in h.filters:
        print(f"  Filter: {f}")
```

### Check the allowed set

```python
# Emit a test record with explicit handlers
log.info("test", extra={"handlers": [HandlerType.Rich, HandlerType.MyCustomService]})

# Now add debug output to HandleIDFilter.filter() to see what's happening:
# "Handler IDs: {self.handler_ids}, Allowed: {allowed}, Match: {bool(overlap)}"
```

### Check fallback behavior

```python
# Build with your handler in fallback
log = get_daq_logger("test", my_custom_service_enabled=True)

# This should use fallback (if you configured it)
log.info("Should go to custom service")

# This overrides fallback
log.info("Only rich", extra={"handlers": [HandlerType.Rich]})
```

### Test ERS parsing (if applicable)

```python
import os
os.environ["DUNEDAQ_ERS_INFO"] = "my_custom_service,lstdout"

from daqpytools.logging import LogHandlerConf
conf = LogHandlerConf(init_ers=True)
# Did ERS correctly parse your handler type?
```

### For filters, check order

```python
log = get_daq_logger("test", rich_handler=True)
add_handler(log, HandlerType.Throttle)
add_handler(log, HandlerType.ModuleSuppress, suppressed_modules=["test"])

# Logger-level filters run first, then handlers
print(f"Logger filters: {log.filters}")
print(f"Handler filters: {log.handlers[0].filters}")
```

---

## Common patterns

### Handler that wraps an existing logger

```python
class ExistingServiceHandler(logging.Handler):
    """Wrap an existing service client."""
    
    def __init__(self, client):
        super().__init__()
        self.client = client  # e.g., a sentry client
    
    def emit(self, record):
        self.client.send_record(self.format(record), level=record.levelname)
```

### Filter that uses record metadata

```python
class MetadataAwareFilter(BaseHandlerFilter):
    def filter(self, record):
        # Filters can look at extra metadata
        if "skip_logging" in record.__dict__:
            return False
        return True

# Usage:
log.info("skip me", extra={"skip_logging": True})
```

### Handler that writes JSON

```python
class JSONHandler(logging.Handler):
    def emit(self, record):
        entry = {
            "timestamp": record.created,
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
        }
        # Write JSON somewhere
```

---

## Next steps

- Look at existing handlers in `handlers.py` for patterns
- Look at `ThrottleFilter` for a complex filter example
- Check test files in `tests/logging/` for usage examples
- Add your handler/filter, submit a PR!
