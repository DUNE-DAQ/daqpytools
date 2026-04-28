# Logging in DUNE-DAQ — Documentation

Welcome, fellow beavers, to the logging documentation for daqpytools.

This documentation is split into two sections depending on your role:

- **User docs** — for anyone writing Python applications that use logging
- **Developer docs** — for anyone extending the logging system itself (new handlers, new filters). This is found in [a separate MKDocs website](https://dune-daq.github.io/daqpytools/).

---

## User documentation

| Page | What it's for |
|---|---|
| [Tutorial](./tutorial.md) | Get a working logger running from scratch |
| [Concepts & explanation](./explanation.md) | Understand how Python logging and daqpytools work |
| [Severity levels](./severitylevels.md) | Quick reference for `DEBUG`, `INFO`, `WARNING`, `ERROR`, and `CRITICAL` |
| [How to use handlers and filters](./how-to/use-handlers.md) | Descriptions and examples for each handler and filter |
| [How to route messages](./how-to/route-messages.md) | Direct records to specific handlers using HandlerType and LogHandlerConf |
| [How to add handlers at runtime](./how-to/add-handlers-at-runtime.md) | Attach handlers after logger creation; pass kwargs |
| [How to configure ERS](./how-to/configure-ers.md) | Attach and use ERS handlers |
| [How to upgrade an existing package](./how-to/upgrade-package.md) | Migration checklist for adopting daqpytools logging in existing codebases |
| [Best practices](./how-to/best-practices.md) | Recommended patterns for structuring logging in your application |
| [Troubleshooting](./reference/troubleshooting.md) | Common symptoms, causes, and fixes |
| [API reference](../APIref/) | Auto-generated kwargs, types, and defaults for all public APIs (redirects to MKDocs website) |

