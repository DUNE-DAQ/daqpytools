from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar

from daqpytools.logging.exceptions import (
    ERSEnvError,
    ProtobufFormatError,
)
from daqpytools.logging.levels import level_to_ers_var
from daqpytools.logging.rich_handler import FormattedRichHandler
from daqpytools.logging.utils import get_width

# Initialise a logger to catch erstrace + other unknown handlertypes from OKS
log: logging.Logger = logging.getLogger(__name__)
log.addHandler(FormattedRichHandler(width=get_width()))
log.setLevel("INFO")

class StreamType(Enum):
    """Enumtype to classify the set of relevant handlers (i.e streams)."""
    BASE="base"
    OPMON="opmon"
    ERS="ers"

@dataclass(frozen=True)
class ProtobufConf:
    """Dataclass to hold Protobuf Configuration."""
    url:str= "monkafka.cern.ch"
    port:int= 30092

    def get_string(self) -> str:
        """Converts back to string version."""
        return f"{self.url}:{self.port}"

class HandlerType(Enum):
    """Enumtype to classify the existing set of Handlers.
    Values must match exactly what is given in the OKS configuration, if any
    All are in lowercase.
    """
    Unknown = "unknown"
    Stream = "stream"
    Rich = "rich"
    File = "file"
    Protobufstream = "protobufstream"
    Lstdout = "lstdout"
    Lstderr = "lstderr"
    Throttle = "throttle"
    @classmethod
    def from_string(cls, s: str) -> HandlerType | None:
        """Converts from a case-independent string to HandlerType."""
        try:
            return HandlerType(s.lower())
        except ValueError:
            msg=f"[red]{s}[/red] is not a known handler type"
            log.warning(msg)
            return None

@dataclass(frozen=True)
class ERSPyLogHandlerConf:
    """Dataclass that holds the relevant ERS configuration from OKS.

    As an example, given the following
    <obj class="Variable" id="ehn1-env-ers-error">
        <attr name="name" type="string" val="DUNEDAQ_ERS_ERROR"/>
        <attr name="value" type="string" val="erstrace,throttle,lstdout,
            protobufstream(monkafka.cern.ch:30092)"/>
    </obj>

    This dataclass holds the list of relevant Handlers attached to the ERS log level. 
    In case it also contains a single protobuf handler, the configuration is stored by 
    the ProtobufConf instance. Multiple protobuf handlers with different url/ports 
    are not yet supported.
    """
    handlers: list = field(default_factory = lambda: [])
    protobufconf: ProtobufConf = field(default_factory = lambda: None)


@dataclass
class LogHandlerConf:
    """Dataclass that holds the various streams and relevant handlers.
    
    Attributes:
        init_ers: If True, automatically initializes ERS configuration 
            during construction.
        _BASE_HANDLERS: Private class variable for default base handlers
        _OPMON_HANDLERS: Private class variable for opmon handlers
        BASE_CONFIG: Class variable for base stream configuration
        OPMON_CONFIG: Class variable for opmon stream configuration
        ERS: Instance field for ERS configuration (loaded from environment)
    """
    init_ers: bool = False

    _BASE_HANDLERS: ClassVar[set] = {HandlerType.Stream, HandlerType.Rich,
        HandlerType.File
        }
    _OPMON_HANDLERS: ClassVar[set] = {HandlerType.Rich, HandlerType.Stream,
        HandlerType.File}
    _ERS: object = None
    
    Base: ClassVar[dict] = {
        "handlers": _BASE_HANDLERS,
        "stream": StreamType.BASE
    }
    
    Opmon: ClassVar[dict] = {
        "handlers": _OPMON_HANDLERS,
        "stream": StreamType.OPMON
    }

    def __post_init__(self) -> None:
        """Initialize ERS configuration if init_ers field is True.

        This method is called automatically after dataclass initialization.
        If the init_ers attribute was set to True, it triggers the complete
        ERS initialization.
        """
        if self.init_ers:
            self.init_ers_stream()

    @property
    def ERS(self) -> dict : # noqa: N802
        """Get the ERS configuration dictionary.
        
        Returns:
            dict: Contains 'ers_handlers' and 'stream' configuration for ERS
            
        Raises:
            AttributeError: If ERS has not been
                initialized (call init_ers_stream() first)
        """
        if not self._ERS:
            err_msg = "ERS stream not initialised. Call init_ers_stream() first"
            raise AttributeError(err_msg)
        return self._ERS

    def init_ers_stream(self) -> None:
        """Initialize ERS configuration from environment variables.
        
        Loads ERS configuration from OKS environment variables and populates
        the _ERS dict with handlers and stream information.
        
        Called automatically during construction if init_ers=True, or can be
        called manually afterwards.
        """
        self._ERS = {
            "ers_handlers":  LogHandlerConf._get_oks_conf(),
            "stream": StreamType.ERS
        }   

    @staticmethod
    def _convert_str_to_handlertype(handler_str: str) -> tuple[HandlerType,
        ProtobufConf | None]:
        """Parses a given environment variable to obtain the
        HandlerType and ProtobufConf as necessary. 

        Eg. converts "throttle" to HandlerType.Throttle
            converts "protobufstream(url:port)" to return both the HandlerType and the 
            protobuf configuration
        """
        if "erstrace" in handler_str:
            msg = (
                "ERSTrace is a C++ implementation, "
                "does not have an equivalent in Python"
            )
            log.debug(msg)
            return None, None

        if HandlerType.Protobufstream.value not in handler_str:
            return HandlerType.from_string(handler_str), None

        match = re.search(r"\(([^:]+):(\d+)\)", handler_str)
        if not match:
            raise ProtobufFormatError(handler_str)
        url, port = match.group(1), int(match.group(2))
        return HandlerType.Protobufstream, ProtobufConf(url=url, port=port)

    @staticmethod
    def _make_ers_handler_conf(ers_log_level :str) -> ERSPyLogHandlerConf:
        """Generates the ERSPyLogHandlerConf from reading an environment variable."""
        envvalue = os.getenv(ers_log_level)
        if envvalue is None:
            raise ERSEnvError(ers_log_level)
        
        ers_handlers: list[HandlerType] = []
        protobufconf: ProtobufConf | None = None

        for raw_handler in envvalue.split(","):
            handlertype, parsed_protobufconf = LogHandlerConf._convert_str_to_handlertype(
                raw_handler.strip()
            )

            if handlertype is not None:
                ers_handlers.append(handlertype)

            if parsed_protobufconf is not None:
                protobufconf = parsed_protobufconf
        
        return ERSPyLogHandlerConf(
            handlers = ers_handlers,
            protobufconf = protobufconf
        )

    @staticmethod
    def _get_oks_conf() -> dict:
        """From the set of known environment variables, generate the ERS conf dict."""
        return {var: LogHandlerConf._make_ers_handler_conf(var) 
            for var in list(level_to_ers_var.values())}
    
    @staticmethod
    def get_base() -> set[HandlerType]:
        """Returns the default list of handlers from
        LogHandlerConf._BASE_HANDLERS without having to initialise an instance.
        """
        return set(LogHandlerConf._BASE_HANDLERS)
    

