# How to configure ERS handlers

This page covers how to attach and use ERS (error reporting system) handlers on a logger.

For background on ERS streams and routing, see [Concepts](../explanation.md). For the `LogHandlerConf` routing API, see [Routing messages to specific handlers](./route-messages.md).

---

## Configuring ERS handlers on an existing logger

Use `setup_daq_ers_logger` to attach ERS-derived handlers to an existing logger based on environment configuration.

```python
from daqpytools.logging import LogHandlerConf, get_daq_logger, setup_daq_ers_logger

log = get_daq_logger(
    logger_name="ers_logger",
    rich_handler=True,
    stream_handlers=False,
)

# Attach ERS-derived handlers (lstdout, protobufstream) to this logger
setup_daq_ers_logger(log, ers_kafka_session="session_temp")

# Now use LogHandlerConf routing to target ERS handlers
ers_conf = LogHandlerConf(init_ers=True)
log.info("ERS Info routing", extra=ers_conf.ERS)
log.warning("ERS Warning routing", extra=ers_conf.ERS)
log.error("ERS Error routing", extra=ers_conf.ERS)
```

---

## ERS environment variables

ERS handlers are configured via environment variables. These are parsed automatically by daqpytools:

```
DUNEDAQ_ERS_ERROR="throttle,lstdout,protobufstream(monkafka.cern.ch:30092)"
DUNEDAQ_ERS_WARNING="..."
# etc.
```

These are parsed into `ERSPyLogHandlerConf` objects that hold the handler list and optional protobuf endpoint for each severity.

Remember that ERS environment variables need to exist at the point of ERS logger initialisation. See [best practices](./best-practices.md) for guidance on when to call `setup_daq_ers_logger`.
