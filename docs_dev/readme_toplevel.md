# Logging in DUNE-DAQ — Documentation

Welcome to the logging documentation for daqpytools (as of fddaq-v5.6.0).

This documentation is split into two sections depending on your role:

- **User docs** — for anyone writing Python applications that use logging
- **Developer docs** — for anyone extending the logging system itself (new handlers, new filters)

---

## User documentation

| Page | What it's for |
|---|---|
| [Tutorial](./user/tutorial.md) | Get a working logger running from scratch |
| [Concepts & explanation](./user/explanation.md) | Understand how Python logging and daqpytools work |
| [How to use handlers and filters](./user/how-to/use-handlers.md) | Descriptions and examples for each handler and filter |
| [How to route messages](./user/how-to/route-messages.md) | Direct records to specific handlers using HandlerType and LogHandlerConf |
| [How to add handlers at runtime](./user/how-to/add-handlers-at-runtime.md) | Attach handlers after logger creation; pass kwargs |
| [How to configure ERS](./user/how-to/configure-ers.md) | Attach and use ERS handlers |
| [Best practices](./user/how-to/best-practices.md) | Recommended patterns for structuring logging in your application |
| [Troubleshooting](./user/reference/troubleshooting.md) | Common symptoms, causes, and fixes |
| [API reference](https://dune-daq.github.io/daqpytools/APIref) | Auto-generated kwargs, types, and defaults for all public APIs |

---

## Developer documentation

| Page | What it's for |
|---|---|
| [Concepts & explanation](./dev/explanation.md) | The routing model, component definitions, fallback logic |
| [Architecture reference](./dev/reference/architecture.md) | Logger init flow and record flow at runtime |
| [How to add a handler](./dev/how-to/add-a-handler.md) | Step-by-step guide to adding a new handler type |
| [How to add a filter](./dev/how-to/add-a-filter.md) | Step-by-step guide to adding a new logger-level filter |
| [How to debug routing](./dev/how-to/debug-routing.md) | Systematic workflow for diagnosing routing issues |
| [Common patterns](./dev/reference/patterns.md) | Quick-reference recipes for handlers and filters |
