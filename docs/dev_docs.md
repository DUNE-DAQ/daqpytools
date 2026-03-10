# Logging (developer facing)

This page documents the internal logging architecture in `daqpytools.logging` for developers. It focuses on *runtime logic and architecture* rather than user-facing API basics.

For user-facing guides, see:

- `docs/Logging.md` (quickstart)
- `docs/Logging_advanced.md` (advanced usage patterns)

For extension workflows (adding handlers/filters, debugging checklist), see `docs/dev_docs_extension.md`.

---

## Developer map

- Core runtime flow: sections 1-5
- Registries and config models: sections 6-9
- Public setup APIs and error model: sections 10-11
- Extending and debug workflow: `docs/dev_docs_extension.md`

## Core philosophy (read this first)

Before looking at module-by-module details, treat the logging system as a routing engine whose core job is to answer one question for every record:

`Should this specific handler transmit this specific record right now?`

Everything else exists to make that answer deterministic, configurable, and easy to extend.

### Why this design exists

The code intentionally avoids embedding destination rules inside handler implementations. Handlers should only know *how* to emit (terminal, file, kafka, etc.), not *when* they are eligible to emit. Eligibility is computed from metadata attached to each record, plus a well-defined fallback policy.

This gives three major properties:

- routing behavior can be changed per message via `extra`, without reconfiguring logger objects
- global defaults remain stable through fallback sets when metadata is absent
- new handlers/filters can be added without rewriting decision logic in every existing handler

### The mental model: capability set vs requested set

Each installed handler has a capability identity represented as one or more `HandlerType` values (via its attached `HandleIDFilter`).

Each record has a requested destination set, resolved by strategy:

- explicit set from record metadata (`extra["handlers"]`) when present
- otherwise fallback handlers configured during logger setup
- stream-specific overrides (for example ERS severity maps) when applicable

Transmission is then a pure set operation:

`transmit <=> handler_ids ∩ allowed_handlers is non-empty`

If the intersection is empty, that handler drops the record. If non-empty, it emits.

This is the key concept to keep in mind when reading or changing this code.

### Fallback handlers are not a backup feature, they are default policy

A common misunderstanding is to treat fallback handlers as a rare "if all else fails" path. In this architecture, fallback is the normal baseline policy for records that do not carry explicit routing metadata.

In practice:

- no `extra["handlers"]` means "route by default policy"
- default policy is the composed `fallback_handlers` set from setup/specs
- `HandleIDFilter` still enforces per-handler identity checks against that default set

So fallback behavior is central to system correctness, not an edge case.

### Where filtering responsibility lives

Filtering is intentionally split into two layers with different responsibilities:

- logger-level filters decide whether a record should continue to fan out at all (for example throttling concerns)
- handler-level `HandleIDFilter` decides whether a particular handler is allowed to transmit that record

This split prevents business routing logic from leaking into output classes and keeps global policies independent from destination policies.

### Why `HandlerType` is the routing contract

`HandlerType` is the shared language across parser, strategy, specs, setup, and filters. It is the stable contract that ties together:

- configuration tokens (including ERS/env parsing)
- declared handler/filter capabilities in registries
- per-record requested destinations
- per-handler identity checks

Because the same token model is used end-to-end, the pipeline remains composable and predictable.

### Practical rule for developers

When behavior looks wrong, debug in this order:

1. what allowed set was resolved for the record (explicit vs fallback vs stream strategy)
2. what `handler_ids` are attached to each handler's `HandleIDFilter`
3. whether intersection logic should pass or fail for each destination

Most "missing log" or "unexpected log" issues reduce to one of those three points.

## 1. Scope and architecture map

At runtime, logging follows a two-stage filter model:

1. A `LogRecord` is produced by a logger call.
2. Logger-level filters run first (for example, `ThrottleFilter`).
3. The record is then offered to each attached handler.
4. Each handler has a `HandleIDFilter` that decides if that specific handler should emit.
5. If accepted, the handler formats and emits to terminal/file/kafka.

The core design principle is metadata-driven routing: records carry routing metadata in `extra`, and filters/strategies interpret it. This avoids hardcoding destination logic in handler classes.

## 2. Module responsibilities

### 2.1 `handlerconf.py`

- Defines canonical enums (`HandlerType`, `StreamType`)
- Defines stream/config dataclasses (`ProtobufConf`, `ERSPyLogHandlerConf`, `LogHandlerConf`)
- Parses ERS environment variables into structured Python configuration

### 2.2 `routing.py`

- Defines strategy interfaces and implementations for resolving allowed handlers
- Contains default routing, ERS routing, and stream-aware dispatch

### 2.3 `specs.py`

- Defines immutable declarative spec models (`HandlerSpec`, `FilterSpec`)
- Provides the common contract used by registries/builders

### 2.4 `handlers.py`

- Implements handler factories/builders
- Owns `HANDLER_SPEC_REGISTRY`
- Installs handlers while preventing duplicates
- Attaches per-handler `HandleIDFilter`

### 2.5 `filters.py`

- Implements routing-aware filter base class (`BaseHandlerFilter`)
- Implements `HandleIDFilter` and `ThrottleFilter`
- Owns `FILTER_SPEC_REGISTRY`
- Installs logger-level filters via registry

### 2.6 `logger.py`

- Public setup entry points (`setup_root_logger`, `get_daq_logger`, `setup_daq_ers_logger`)
- Integrates handler/filter selection, fallback composition, and extras propagation

### 2.7 `exceptions.py`

- Declares logging-specific exception types used across setup/parsing paths

## 3. Core concepts and vocabulary

### 3.1 `HandlerType`

`HandlerType` is the canonical routing token for things attachable to a logger setup path.

It includes:

- Output handlers (`Rich`, `Stream`, `File`, `Protobufstream`, etc.)
- Logger-level filter tokens (`Throttle`)

Important: `HandleIDFilter` itself is **not** a `HandlerType`. It is an internal filter attached to handlers to enforce routing.

### 3.2 `StreamType`

`StreamType` classifies logical routing contexts:

- `BASE`
- `OPMON`
- `ERS`

Routing strategies inspect `record.stream` to choose how to resolve allowed handlers.

### 3.3 Fallback handlers

Fallback handlers are the default allow-list used when a record does not explicitly carry `extra["handlers"]`. This is the practical meaning behind “base handler id” behavior: every handler/filter has an effective default identity set derived from spec fallback and logger construction.

### 3.4 Record metadata (`extra`)

Supported metadata consumed by routing/filtering internals:

- `handlers`: explicit `HandlerType` set/list for default routing
- `stream`: logical stream selector (`StreamType`), especially `StreamType.ERS`
- `ers_handlers`: ERS severity map used in ERS strategy

## 4. Filtering model (deep dive)

### 4.1 Attachment points

- Logger-level filters gate records before any handler fan-out.
- Handler-level filters gate whether a specific handler emits.

This split is intentional:

- Logger-level filters are good for global cross-handler concerns (throttling, global suppression).
- Handler-level filters are good for destination selection.

### 4.2 `BaseHandlerFilter`

`BaseHandlerFilter` centralizes two concerns:

- `fallback_handlers`: default allow-list if record metadata is absent
- `allowed_handlers_strategy`: resolver object deciding the record’s effective allowed set

`get_allowed(record)` delegates to the strategy and returns the resolved set (or `None` for no emission).

### 4.3 `HandleIDFilter` logic

`HandleIDFilter` is attached to each installed handler. During setup, the filter is given the handler’s own identity metadata (`handler_id`), normalized to `handler_ids: set[HandlerType]`.

At emit time:

1. It resolves allowed handlers from record metadata via strategy/fallback.
2. It emits if and only if intersection is non-empty:

`handler_ids ∩ allowed != ∅`

This is the key mechanism that makes per-record handler routing work.

### 4.4 Base/fallback handler ID behavior

The "base handler ID" concept is implemented as fallback identity behavior:

- Each `HandlerSpec` defines `fallback_types`.
- Logger construction composes an overall `fallback_handlers` set from enabled flags.
- If a record provides no explicit `handlers`, routing strategy falls back to that default set.
- `HandleIDFilter` compares its attached handler ids against this resolved default set.

So filtering works because each handler-side filter knows *what it is attached to*, and compares that with *what this record is allowed to reach*.

### 4.5 `ThrottleFilter` state machine

`ThrottleFilter` is attached to the logger, not to individual handlers.

Per unique issue key (`pathname:lineno`) it tracks state in `IssueRecord`:

- first `initial_threshold` occurrences pass immediately
- then suppression occurs in escalating buckets (10, then 100, then 1000, ...)
- suppression summaries are emitted as synthetic records
- state resets after inactivity of `time_limit`

Notes:

- Thread-safe via mutex around issue map updates.
- Suppression summary records bypass throttling via internal `_throttle_suppression` flag.
- Throttling is activated per record only when `HandlerType.Throttle` is in the resolved allowed set.

### 4.6 Adding a new logger-level filter

To add a logger-level filter that participates in routing:

1. Add/choose a `HandlerType` token.
2. Implement filter class (usually derive from `BaseHandlerFilter`).
3. Implement a builder function accepting fallback handlers and `**extras`.
4. Define `FilterSpec`.
5. Register in `FILTER_SPEC_REGISTRY`.
6. Ensure `add_handlers_from_types` can discover it through that token.

## 5. Routing model (deep dive)

### 5.1 Strategies

`routing.py` uses strategy objects to resolve allowed handlers:

- `AllowedHandlersStrategy`: abstract contract
- `DefaultAllowedHandlerStrategy`: default `record.handlers` / fallback logic
- `ERSAllowedHandlersStrategy`: ERS severity map logic
- `StreamAwareAllowedHandlersStrategy`: dispatcher based on `record.stream`

### 5.2 Default case

If `record.stream` is not `StreamType.ERS`, default strategy applies:

- Use `record.handlers` when present.
- Otherwise use filter fallback handlers.

This is the normal path for `extra={"handlers": [...]}` routing.

### 5.3 ERS case

If `record.stream == StreamType.ERS`, ERS strategy applies:

1. Map Python numeric level to ERS env variable name using `level_to_ers_var`.
2. Read `record.ers_handlers`.
3. Pick `ERSPyLogHandlerConf` for that severity.
4. Use its `handlers` as allowed set.

Because ERS config is severity-specific, ERROR/INFO/etc can route to different handler sets.

### 5.4 Typical extras case

For common per-message routing:

```python
log.info("file only", extra={"handlers": [HandlerType.File]})
```

Every attached handler receives the record, but only handlers whose `HandleIDFilter` intersects with `{HandlerType.File}` emit. If the requested type is not attached, nothing emits for that target (expected no-op).

## 6. Specs and builders

### 6.1 `HandlerSpec`

`HandlerSpec` captures:

- `alias`: canonical key (usually `HandlerType`)
- `handler_class`: runtime class used in duplicate checks
- `factory`: builder callable
- `fallback_types`: default routing ids for the built handler
- `target_stream`: stream discriminator for stream handlers (stdout/stderr)

### 6.2 `FilterSpec`

`FilterSpec` captures:

- `alias`
- `filter_class`
- `factory`
- `fallback_types`

### 6.3 Why builder/factory functions

Builders centralize construction details and kwargs validation. This keeps registry and installation logic declarative and avoids constructor-specific branching in setup code.

### 6.4 `kwargs` propagation contract

`get_daq_logger(..., **extras)` forwards extras to `add_handlers_from_types`, which forwards to handler/filter factories.

In practice:

- File factory expects `path`.
- ERS Kafka factory expects `session_name` and may use `address`, `topic`, `ers_app_name`.
- Throttle factory may consume `initial_treshold` and `time_limit`.

Guideline: factories should accept `**extras` and ignore unknown values unless strict validation is needed.

## 7. Registries and type mapping

### 7.1 Handler registry

`HANDLER_SPEC_REGISTRY` maps one `HandlerType` to one or more `HandlerSpec` values.

Notable pattern: `HandlerType.Stream` maps to *both* stdout and stderr specs. This is why one logical type can install multiple physical handlers.

### 7.2 Filter registry

`FILTER_SPEC_REGISTRY` maps `HandlerType` to `FilterSpec`.

This is why logger-level filters can be selected using the same routing token model as handlers.

### 7.3 Installation flow

`add_handlers_from_types` resolves each requested `HandlerType` in order:

1. Try handler specs; if found, install handler(s).
2. Otherwise, try filter spec; if found, install logger-level filter.
3. Skip already-installed classes where duplicate checks indicate existing instances.

## 8. `LogHandlerConf` and stream configuration

### 8.1 `StreamType` usage

`StreamType` marks which logical stream a record/config belongs to (`BASE`, `OPMON`, `ERS`) and enables stream-aware routing strategy selection.

### 8.2 Base and Opmon configuration

`LogHandlerConf` provides class-level base dictionaries:

- `Base`: handlers + stream metadata for normal/base output
- `Opmon`: handlers + stream metadata for opmon-related output

These dictionaries are intended for passing directly through `extra`, so records carry both handlers and stream context together.

### 8.3 ERS lifecycle in `LogHandlerConf`

`LogHandlerConf(init_ers=False)` does not parse ERS immediately. This allows logger setup in environments where ERS vars are not yet available.

ERS can then be initialized later via `init_ers_stream()`. Accessing `ERS` before initialization raises an `AttributeError` by design.

### 8.4 `ERSPyLogHandlerConf` and `ProtobufConf`

`ERSPyLogHandlerConf` encapsulates one ERS severity’s parsed config:

- `handlers`: list of `HandlerType` values for that severity
- `protobufconf`: optional parsed protobuf endpoint

`ProtobufConf` encapsulates endpoint details (`url`, `port`) and can re-serialize to `url:port` string for kafka handler setup.

### 8.5 `HandlerType` and ERS token strings

`HandlerType` values must match ERS/OKS token strings (lowercase semantics). This is essential for successful parsing from env variables.

Special handling:

- `erstrace` is intentionally ignored in Python (C++-specific behavior).
- unknown handler strings are warned and dropped.
- malformed `protobufstream(host:port)` raises `ProtobufFormatError`.

## 9. ERS integration details

### 9.1 Environment parsing model

ERS variables such as `DUNEDAQ_ERS_ERROR` are parsed as comma-separated tokens.

Supported token styles:

- plain handler names (`throttle`, `lstdout`, `protobufstream`, ...)
- protobuf endpoint form (`protobufstream(host:port)`)

Each variable is converted into an `ERSPyLogHandlerConf`.

### 9.2 Severity-specific handler sets

ERS routing is severity-dependent by construction. Each severity variable has its own handler list and optional protobuf endpoint, so severity classes can intentionally diverge.

### 9.3 `setup_daq_ers_logger(...)`

`setup_daq_ers_logger`:

1. Loads/parses all ERS severity configurations.
2. Computes the union of handler types across severities for attachment.
3. Resolves protobuf address if present.
4. Installs relevant handlers/filters on the logger.

Constraint: multiple distinct protobuf endpoints are not currently supported in this setup path.

## 10. Public setup APIs

### 10.1 `setup_root_logger(...)`

- Creates/validates root logger setup.
- Fails fast if handlers already exist on the named root logger.
- Raises logging level on noisy third-party loggers (`sh`, `kafka`) for readability.

### 10.2 `get_daq_logger(...)`

- Main constructor for standard DAQ loggers.
- Composes fallback handler set from flags (`rich_handler`, `file_handler_path`, `stream_handlers`, `ers_kafka_session`, `throttle`).
- Delegates installation to registry-driven setup.
- Reuses existing logger only when requested handler signature is compatible.

### 10.3 `setup_daq_ers_logger(...)`

- Enriches an existing logger with ERS-derived handler/filter configuration.
- Keeps ERS-specific parsing/setup concerns out of the default constructor.

## 11. Error model

The exception classes in `exceptions.py` communicate specific failure classes:

- `LoggerHandlerError`: duplicate handler type found in logger ancestry
- `LoggerSetupError`: invalid/conflicting logger construction request
- `LoggerConfigurationError`: external configuration parse/load error
- `ERSEnvError`: required ERS env variable missing/empty
- `ERSInitError`: ERS kafka handler cannot be initialized
- `ProtobufFormatError`: invalid protobuf endpoint token format

## Next reading

Continue with `docs/dev_docs_extension.md` for:

- adding new handlers
- adding new logger-level filters
- debugging/verification checklist
- suggested extension documentation improvements

