# How to debug routing issues

When logs appear wrong or not at all, use this workflow.

---

## General debugging workflow

### 1. What handlers are attached?

```python
print(log.handlers)  # List all handlers
for h in log.handlers:
    print(f"{h}: filters={h.filters}")  # Check their filters
```

### 2. What's the allowed set for your record?

- Does it have explicit `extra={"handlers": [...]}`?
- If not, what's the fallback set from logger setup?
- If `stream == StreamType.ERS`: Is the severity level mapped? (DEBUG doesn't map)

### 3. Do handler IDs match?

- Each handler has a `HandleIDFilter` with `handler_ids` set
- Is that set in the allowed set?
- If not, the record is silently dropped

### 4. Are logger-level filters rejecting it?

- Less common, but `ThrottleFilter` might suppress repeated messages
- Check filter state and condition

### 5. For ERS specifically

- Env vars set and properly formatted?
- Severity level mapped correctly?
- Verify handler appears in the resolved allowed set

If all else fails, add debug statements in `HandleIDFilter.filter()` to print `handler_ids`, `allowed`, and the intersection result.

---

## Debugging a new handler or filter

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
