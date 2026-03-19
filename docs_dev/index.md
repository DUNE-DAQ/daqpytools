# Logging in DUNE-DAQ — Documentation

Welcome to the developer documentation for daqpytools. 

This documentation is split into two sections depending on your role:

- **User docs** — for anyone writing Python applications that use logging. This is found in the [official DUNE DAQ SW website](https://dune-daq-sw.readthedocs.io/en/latest/packages/daqpytools/).
- **Developer docs** — for anyone extending the logging system itself (new handlers, new filters).



## Developer documentation

| Page | What it's for |
|---|---|
| [Concepts & explanation](./explanation.md) | The routing model, component definitions, fallback logic |
| [Architecture reference](./reference/architecture.md) | Logger init flow and record flow at runtime |
| [How to add a handler](./how-to/add-a-handler.md) | Step-by-step guide to adding a new handler type |
| [How to add a filter](./how-to/add-a-filter.md) | Step-by-step guide to adding a new logger-level filter |
| [How to debug routing](./how-to/debug-routing.md) | Systematic workflow for diagnosing routing issues |
| [Common patterns](./reference/patterns.md) | Quick-reference recipes for handlers and filters |
