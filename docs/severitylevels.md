# Severity levels

Logging messages are grouped by severity so you can decide what should be shown, routed, or ignored.
The names below match the standard Python logging levels used by daqpytools.

## Overview

| Level | Typical meaning | When to use it | Example |
|---|---|---|---|
| `DEBUG` | The most detailed diagnostic output. | Use when you need to trace control flow, inspect state, or confirm that everything is wired correctly. Useful for troubleshooting. | A health check is running and you want to confirm the retry behavior. `Health check: attempt 5 at 4s elapsed.` |
| `INFO` | Normal progress information. | Use for messages that help a user understand what command or service is doing without adding noise. | A process manager has started and you want to report normal progress. `Starting process manager for the session.` |
| `WARNING` | Something unexpected happened, but execution can continue. | Use when a fallback is taken, input looks suspicious, or behavior is not ideal but still recoverable. | A command still works, but the old name is being phased out. `Retract partition is deprecated. Please use retract-session instead.` |
| `ERROR` | A problem occurred that must be fixed for the current operation to succeed. | Use when a command failed, a configuration is invalid, or a required dependency is missing. | Drunc not working due to some http variables not being set. `This can happen if you have the webproxy enabled at CERN. Ensure 'http_proxy' and equivalent aren't set` |
| `CRITICAL` | An unrecoverable failure. | Use when the process or running instance cannot continue safely. | An application has died unexpectedly. `Process [uuid] has died with a return code [code].` |


For more information on how these are used in logging, see the [concepts and explanation page](./explanation.md).