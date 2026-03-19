# Common handler and filter patterns

Quick reference recipes for specific handler and filter types.

---

## Handler that wraps an existing service client

```python
class ExistingServiceHandler(logging.Handler):
    """Wrap an existing service client."""
    
    def __init__(self, client):
        super().__init__()
        self.client = client  # e.g., a sentry client
    
    def emit(self, record):
        self.client.send_record(self.format(record), level=record.levelname)
```

## Handler that writes JSON

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

## Filter that uses record metadata

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

---

## Next steps

- Look at existing handlers in `handlers.py` for patterns
- Look at `ThrottleFilter` for a complex filter example
- Check test files in `tests/logging/` for usage examples
- Add your handler/filter, submit a PR!
