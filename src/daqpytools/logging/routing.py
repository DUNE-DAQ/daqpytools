import logging
from abc import ABC, abstractmethod
from typing import Any

from daqpytools.logging.handlerconf import StreamType
from daqpytools.logging.levels import level_to_ers_var

"""
So this file basically allows us to define the set of handlers that the logger should send to 
"""


class AllowedHandlersStrategy(ABC):
    """Strategy for resolving allowed handler types for a log record"""

    @abstractmethod
    def resolve(
        self,
        record: logging.LogRecord,
        fallback_handlers : set[Any]
    ) -> set[Any] | None:
        """Resolve allowd handlers for a given record."""

    def safe_return_set(self, raw_set : set[Any]) -> set[Any] | None:
        return {obj for obj in raw_set if obj is not None}



class DefaultAllowedHandlerStrategy(AllowedHandlersStrategy):
    """Resolve allowed handlers from record.handlers, or a fallback case"""

    def resolve(
        self,
        record: logging.LogRecord,
        fallback_handlers : set[Any]
    ) -> set[Any] | None:
        allowed = getattr(record, "handlers", fallback_handlers)
        if allowed is None:
            return None
        return self.safe_return_set(allowed)

class ERSAllowedHandlersStrategy(AllowedHandlersStrategy):
    """Resolve allowed handlers from ERS payload on log records."""

    def resolve(
        self,
        record: logging.LogRecord,
        fallback_handlers : set[Any] 
    ) -> set[Any] | None:
        
        del fallback_handlers # unused

        # Chain None checks using walrus operator
        if (
            # Checks if python log level has an ERS severity level match
            (ers_level_var := level_to_ers_var.get(record.levelno)) is None
            # CHecks if ers_handlers (specifically for ERS) is supplied
            or (ers_handlers := getattr(record, "ers_handlers", None)) is None
            # _Assigns_ the relevant ERS handler conf from supplied level
            or (ershandlerconf := ers_handlers.get(ers_level_var)) is None
        ):
            return None

        return self.safe_return_set(ershandlerconf.handlers)
        


class StreamAwareAllowedHandlersStrategy(AllowedHandlersStrategy):
    """A dispatcher, chooses specific strategies based on record.stream"""

    def __init__(
        self,
        default_strategy : AllowedHandlersStrategy | None = None,
        ers_strategy: AllowedHandlersStrategy | None = None,
    ) -> None: 
        self.default_strategy =  default_strategy or DefaultAllowedHandlerStrategy()
        self.ers_strategy = ers_strategy or ERSAllowedHandlersStrategy()

    def resolve(
        self,
        record: logging.LogRecord,
        fallback_handlers : set[Any],
        ) -> set[Any] | None:

        if getattr(record, "stream", None) == StreamType.ERS:
            return self.ers_strategy.resolve(record, fallback_handlers)
        return self.default_strategy.resolve(record, fallback_handlers)
    