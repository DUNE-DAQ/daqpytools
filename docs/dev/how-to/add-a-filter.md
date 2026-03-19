# How to add a new logger-level filter

Logger-level filters are attached to the logger itself (not individual handlers) and run before any handler sees the record.

**Important:** Logger-level filters are **only active when explicitly activated**. A filter only applies its logic if its `HandlerType` is present in the record's allowed handlers set. This prevents filters from unexpectedly activating on all records.

For adding handlers instead, see [How to add a new handler](./add-a-handler.md).
For how filters interact with the rest of the system, see the [developer explanation](../explanation.md).

---

Let's add a custom filter that only processes records containing specific metadata.

## Implementation

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

## Using your new filter

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

## Key points about logger-level filters

- They run **before** handlers, so if they reject a record, no handler sees it
- They **only activate when explicitly requested** via their `HandlerType` in `extra={"handlers": [...]}`
- They inherit from `BaseHandlerFilter` to participate in routing logic
- They DON'T need a `HandleIDFilter` (that's for handlers)
- They're global to the logger, not per-handler

---

## Common patterns

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
