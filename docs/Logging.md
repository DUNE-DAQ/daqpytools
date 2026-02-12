# Logging (user facing)

This should entirely focus on the user side. How logigng works, and then how to use the stuff in daqptyools

---
Updates as of mid February

# Logging for Python in DUNE-DAQ

Welcome, fellow beavers! This page provides a user's guide to how logging is done in Python in the context of DUNE-DAQ. 

## Basics

The bulk of the loggign functionality in drunc and other Python applications is built off the cool [Python logging framework](https://docs.python.org/3/library/logging.html), with its mission defined below:

> This module defines functions and classes which implement a flexible event logging system for applications and libraries.

It is worth a read to understand how logging works in Python, however the salient points are covered below.

In general, the built in logging module allows for producing severity-classified diagnostic events, which can be filtered, formatted, or routed as necessary. These logs automatically contain useful information including the timestamp, module, and context of the message. 

The core object of the logging functionality in Python is the logger. A logging instance, `log`, can be initialised as follows. The phrase "Hello, World!" is used as an input to the logger, with this message being bundled up by other useful information, including the severity level, to form whats known as a LogRecord. This record will then be transmitted as required. 

```python
import logging
log = logging.getLogger("Demo")
log.warning("Hello, world!")

>> Hello, World!
```

### Severity levels

Every record has an attached severity level, which can be used to flag how important a log record is. By default, Python has 5 main levels and one 'notset' level as shown in the image below[^1]:

![log_level_overview](img/loglevels.png)

[^1]: more can be defined as required, see Python's logging manual.

Each logging instance can have an attached severity level. If it has one, then only records that have the same severity level or higher will be transmitted.

```python
import logging
log = logging.getLogger("Demo", level = logging.WARNING)

log.info("This will not print")
log.warning("This will print")

>> This will print
```

### Handlers

Handlers are a key concept of logging in Python, as they control how the records are processed and formatted. There are several default one that the DAQ uses, and there are also several ones that are custom defined for the purposes of the DAQ. 

The example below shows an example of a file handler, a stream handler, and a webhook handler. As can be seen, each of the records are processed and formatted by each of the handlers and transmitted in each of their respective ways.

![drunc_overview](img/handlers.png)

Importantly, each handler can have its own associated severity level! In the example above, it is certainly possible to have the WebHookHandler to only transmit if a record is of the level Warning or higher.



### Filters
A sidegrade and important add on for the loggers is the filters, whos primary purpose is to decide if an error should be transmitted or not. Filters can be attached to both the logger instance as well as any handlers attached to the logger instance itself. 

When a log record arrives, it will first be processed by the filters attached to the loggers first. Should they pass, the record is then passed onto each handler as shown before, where they are then further processed by each handler's attached filters. Only when they pass will a log be record be transmitted.

![filters](img/filters.png)

### Inheritance

Another key part of logging in Python is the inheritance feature. Loggers are organised in a heirarchical fashion and so it is possible to initialise descendant loggers by chaining the names together with a period, such as "root.parent.child". 

By default, loggers will inheret certain properties of the parent:
- severity level of the logger 
- handlers (and all attached properties, including severity level and filters on handlers)

![inheritance](img/inheritance.png)



Note that a particular exceptoin is that they _don't_ inheret any filters attached to the logger itself. 

A useful diagram to peruse is the [logging flow in the official docs](https://docs.python.org/2/howto/logging.html#logging-flow).


## Using logging with daqpytools

The [daqpytools](https://github.com/DUNE-DAQ/daqpytools) contains several quality of life improvements to DAQ pytools, the most relevant to this document of which being the logging tools.

These include:
- standardised ways of initialising top-level 'root' loggers
- constructors for default logging instances
- many bespoke handlers 
- filters relevant to the DAQ
- handler configurations


A lot of these features can be demonstrated via the logging demonstrator functionality. With the DUNE environments loaded, simply run 

```
daqpytools-logging-demonstrator
```

and view the help string to learn more, and view the script itself in the repository to see how it is implemented. 



### Initialising a handler

Initialising a handler is simple:

```python
from daqpytools.logging.logger import get_daq_logger
test_logger = get_daq_logger(
    logger_name = "test_logger",
    log_level = "INFO",
    use_parent_handlers = True,
    rich_handler = True,
    stream_handlers = False
)

test_logger.warning("Hello, world!")
```

As shown above, initialising a logging instance with a specific handler is as easy as modifying a flag in the constructor.


The core philosophy of the logging framework in daqpytools is that each logger should only have _one_ instance of a specific type of logger. This means that while a single logger can have both a Rich and a Stream handler, a single logger cannot have _two_ Rich handlers to prevent duplicating messages.


Please refer to the docstrings for the most up to date definitions on the options and what handlers may or may not be included. There are some exceptions which are clearly labelled in the document. Choosing which handler to trigger on a per-message instance is an advanced feature of logging in DUNE-DAQ, so please refer to the advanced section of this guide. 


### Walkthrough of existing handlers and filters 

As seen in the previous section, there are several handlers and filters that are present in the daqpytools that may readily be used. What follows will be a brief description of each handlers as well as a quick example,  but for more complete docs please refer to the docstrings and the logging demonstrator.

Remember that by default, any messages received by the logger will be transmitted to _all_ available handlers that are attached to the logger. 


#### Rich handler

The Rich handler should be the 'default' handler for any messages that should be transmitted in the terminal. This handler has great support of colors, and delivers a complete message out to the terminal to make it easy to view and also trace back to the relevant message. 

![rich_demo](img/demo_rich.png)


#### File handler

As the name suggests, the file handler is used to transmit messages directly to a log file. Unlike stream and rich handlers, instead of defining a boolean in the constructor the user must supply the _filename_ of the target file for the messages to go into.

![file_demo](img/demo_file.png)


#### Stream handlers

Stream handlers are used to transmit messages directly to the terminal without any color formatting. This is of great use for the logs of the controllers in drunc, which has its own method of capturing logs via a capture of the terminal output and a pipe to the relevant log file. 

Note that the stream handlers consist of two handlers, one which outputs do `stdout` and another to `stderr`. The latter will only transmit if the record severity level is Error or higher.

![streams_demo](img/demo_streams.png)

#### ERS Kafka handler

The ERS Kafka handler is used to transmit ERS messages via Kafka, which is incredibly useful to show on the dashboards messages as they happen. 

This handler is not included in the default list of handlers to emit. An extra configuration must be used to properly transmit this message; eg. 

```python
from daqpytools.logging.handlers import HandlerType
from daqpytools.logging.logger import get_daq_logger

main_logger: logging.Logger = get_daq_logger(
    logger_name="daqpytools_logging_demonstrator",
    ers_kafka_handler=True
)

main_logger.error(
    "ERS Message",
    extra={"handlers": [HandlerType.Protobufstream]} 
)
```

See the advanced section for more details.

![ers_demo](img/demo_ers.png)

**Notes**
At the moment, by default they will be sent via the following:
```
session_name: session_tester
topic: ers_stream
addres: monkafka.cern
port: 30092
```


#### Throttle filter

There are times when an application decides to send a huge amount of logs of a single message in a very short time, which can overwhelm the systems. When such an event occurs, it is wise to throttle the output coming out. 

The throttle filter replicates the same logic that exists in the ERS C++ implementation, which dynamically limits how many messages get transmitted. The filter is by default attached to the _logger_ instance, with no support for this filter being attached to a specific handler just yet. 

Initialising the filter takes in two argument:
 - `initial_treshold`: number of initial occurences to let through immediately
 - `time_limit`: time window in seconds for resetting state

The basic logic is as follows. 

1. The first N messages will instantly get transmitted, up to `initial_treshold`
2. The next 10 messages will be suppressed, with the next single message reported at the end
3. The next 100 messages will be suppressed, with the next single message reported at the end
4. This continues, with the treshold increaseing by 10x everytime
5. After `time_limit` seconds after the last message, the filter gets reset, allowing messages to be sent once more


For the throttle filter, a 'log record' is **uniquely** defined by the record's pathname and linenumber. Therefore, 50 records that contain the same 'message' but defined in different line numbers in the script will not be erroneously filtered.


An example is as follows:

```python
from daqpytools.logging.handlers import HandlerType
from daqpytools.logging.logger import get_daq_logger

main_logger: logging.Logger = get_daq_logger(
    logger_name="daqpytools_logging_demonstrator",
    stream_handlers=True
    throttle=True
)

emit_err = lambda i: main_logger.info(
    f"Throttle test {i}",
    extra={"handlers": [HandlerType.Rich, HandlerType.Throttle]},
)

for i in range(50):
        emit_err(i)
    main_logger.warning("Sleeping for 30 seconds")
    time.sleep(30)
for i in range(1000):
    emit_err(i)
```

Which will behave as expected.

![throttle_demo](img/demo_throttle.png) 

**Note**
By default, throttle filters obtained via `get_daq_logger` will be initialised with an `initial_treshold` of 30 and a `time_limit` of 30. 

**Note**
Similarly to the ERS Kafka handler, this filter is not enabled by default, hence requiring the use of HandlerTypes. See the Advanced section for more info.

### Advanced logging

The above walkthrough should be sufficient for the vast majority of logging. However, there are a few advanced features in daqpytools that would benefit the user. These mainly are targetted towards a high degree of customisability for the user, including the ability to choose which of the attached handlers will transmit a given message, and automatic routing of messages to certain handlers.

#### Choosing handlers with HandlerTypes 

Lets say you have a logger with an attached Rich handler and File handler as below, and that there are two messages you want to log. However, one of them should only be sent to the file, and the other one should be sent to the terminal via the rich handler. 

```
log = get_daq_logger("example", rich_handler=True, file_handler="logging.log")
```

These can be done by using the `HandlerTypes` enum. The loggers defined here have a special ability to read which HandlerTypes are supplied and to only transmit to the required handlers. 

There is a very specific syntax that must be followed involving the `extra` kwarg:

```
from daqpytools.logging.handlers import HandlerType

log.info("This will only be sent to the Rich", extra={"handlers": [HandlerType.Rich]})
log.info("This will only be sent to the File", extra={"handlers": [HandlerType.File]})
log.info("You can even send to both", extra={"handlers": [HandlerType.Rich, HandlerType.File]})
```

Naturally, if tell the logger to transmit a message where the associated Handler is not attached will cause it to do nothing. For example above, using HandlerTypes.Stream will do nothing. 



#### The need for handler streams

Within the DUNE DAQ ecosystem, there are several other configurations that interplay. These include the OpMon and ERS, which require several handlers for each configuration. These can be best thought of as 'streams' which interact with several other handlers, as shown in an example below.

![streams](img/streams.png)

The native implemention in drunc and most applications is referred to as the 'Base' stream, which will only require interactions with the Rich, File, and Stream handlers. **This is why the ERS Kafka Handler and the Throttle filter need to be 'activated' with HandlerTypes**.

The ERS configuration is defined in OKS, [for example here](https://github.com/DUNE-DAQ/daqsystemtest/blob/974965be6e96aff969c69a380ed34aa96705e802/config/daqsystemtest/ccm.data.xml#L189), and are automatically parsed by daqpytools as they get used. A special feature of the ERS configuration is that the relevant Handlers are severity-level dependent; ERS Fatal and ERS info may have a different set of handler requirements

#### Log Handler Conf


To deal with the constraints set above, a handler configuration dataclass called `LogHandlerConf` is constructed to define the relevant configurations and a system of filters is initialised with every handler. When passing a log record that needs to be processed via a specific stream, the log record and the handler configuration is passed to the relevant logger, after which it is processed. 

An example of which is shown in the logging demonstrator, copied here.

```python
handlerconf = LogHandlerConf()

main_logger.warning("Handlerconf Base", extra=handlerconf.Base)
main_logger.warning("Handlerconf Opmon", extra=handlerconf.Opmon)
```


#### Using ERS
By default, the LogHandlerConf does not initialise the ERS stream because it requires the ERS environment variables to be defined. Should these variables exists, there are two ways to initialise the ERS stream with the LogHandlerConf. 

```python
# By default init_ers is false
# When this is the case, ERS Streams are _not_ defined. Will survive without ERS envs being defined
LHC_no_init = LogHandlerConf() == LogHandlerConf(init_ers=False)

print(LHC_no_init.Base) # Success
print(LHC_no_init.ERS) # Throws ERS stream not initialised. Call init_ERS() first

# Later on, when ERS envs are defined, can be initialised
LHC_no_init.init_ERS() 
print(LHC_no_init.ERS) # Success

```

