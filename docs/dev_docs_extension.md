# Logging Extension Guide (developer)

This page covers developer workflows for extending `daqpytools.logging`.

For runtime architecture and flow, start with `docs/dev_docs.md`.
For user-facing usage, see `docs/Logging.md` and `docs/Logging_advanced.md`.

## 1. How to add your own handler

### Step 1: add a type

Add a new `HandlerType` enum entry in `handlerconf.py`.

- Keep string value aligned with any ERS token you expect to parse.
- Decide if it is a concrete handler output or a logger-level filter token.

### Step 2: implement builder + spec

In `handlers.py` (for concrete handlers):

1. Add builder factory function.
2. Define `HandlerSpec`.
3. Choose `fallback_types` carefully (this affects default routing behavior).

### Step 3: register

Insert the spec into `HANDLER_SPEC_REGISTRY` under the correct `HandlerType` key.

### Step 4: ensure kwargs compatibility

- Document required kwargs.
- Accept `**extras` in builder.
- Fail clearly when required values are missing.
- Avoid breaking current `get_daq_logger(...)` call paths.

### Step 5: ERS compatibility (if needed)

If the new handler should be ERS-configurable:

- ensure parser in `LogHandlerConf._convert_str_to_handlertype` can recognize it
- define any token syntax and validation behavior
- verify severity-specific ERS maps still parse correctly

## 2. How to add your own logger-level filter

To add a new logger-attached filter (similar to throttle):

1. Add/select `HandlerType` activation token.
2. Implement filter class (prefer deriving from `BaseHandlerFilter` for routing-aware behavior).
3. Implement filter builder (`factory`) that accepts fallback handlers and extras.
4. Define `FilterSpec` and register in `FILTER_SPEC_REGISTRY`.
5. Confirm installation via `add_handlers_from_types` when that `HandlerType` is enabled.

This model does **not** apply to `HandleIDFilter`, which remains a per-handler internal routing filter.

## 3. Debugging and verification checklist

When debugging routing/filter behavior:

- inspect `logger.handlers` and `logger.filters`
- inspect each handler's attached filters to verify `HandleIDFilter` identity setup
- emit test messages with controlled `extra={"handlers": [...]}`
- test ERS path with representative env var sets for different severities
- validate throttle behavior with repeated logs from same file/line

## 4. Suggested future enhancements for extension docs

- Add a sequence diagram of record flow through strategy/filter/handler stages.
- Add a reference table mapping `HandlerType` -> registry entry -> required kwargs.
- Add ERS env-token examples alongside parsed object forms.
- Add extension cookbook snippets for common "new handler/new filter" scenarios.
