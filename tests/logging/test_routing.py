import logging

from daqpytools.logging.handlerconf import ERSPyLogHandlerConf, HandlerType, StreamType
from daqpytools.logging.routing import (
    AllowedHandlersStrategy,
    DefaultAllowedHandlerStrategy,
    ERSAllowedHandlersStrategy,
    StreamAwareAllowedHandlersStrategy,
)


class _StrategyForHelper(AllowedHandlersStrategy):
    def resolve(self, record: logging.LogRecord, fallback_handlers: set[object]) -> set[object] | None:
        del record, fallback_handlers
        return None


def _record(level: int = logging.INFO) -> logging.LogRecord:
    return logging.LogRecord(
        name="test.routing",
        level=level,
        pathname="/tmp/test_routing.py",
        lineno=10,
        msg="message",
        args=(),
        exc_info=None,
    )


def test_safe_return_set_filters_out_none() -> None:
    strategy = _StrategyForHelper()
    assert strategy.safe_return_set({None, HandlerType.Rich}) == {HandlerType.Rich}


def test_safe_return_set_returns_empty_set_when_all_none() -> None:
    strategy = _StrategyForHelper()
    assert strategy.safe_return_set({None}) == set()


def test_default_strategy_uses_record_handlers_when_present() -> None:
    strategy = DefaultAllowedHandlerStrategy()
    record = _record()
    record.handlers = {HandlerType.Rich, None}

    assert strategy.resolve(record, {HandlerType.File}) == {HandlerType.Rich}


def test_default_strategy_uses_fallback_when_handlers_missing() -> None:
    strategy = DefaultAllowedHandlerStrategy()
    record = _record()

    assert strategy.resolve(record, {HandlerType.File}) == {HandlerType.File}


def test_default_strategy_returns_none_when_handlers_attr_is_none() -> None:
    strategy = DefaultAllowedHandlerStrategy()
    record = _record()
    record.handlers = None

    assert strategy.resolve(record, {HandlerType.File}) is None


def test_ers_strategy_returns_none_when_level_not_mapped() -> None:
    strategy = ERSAllowedHandlersStrategy()
    record = _record(level=25)
    record.stream = StreamType.ERS
    record.ers_handlers = {}

    assert strategy.resolve(record, set()) is None


def test_ers_strategy_returns_none_without_ers_handlers() -> None:
    strategy = ERSAllowedHandlersStrategy()
    record = _record(level=logging.ERROR)
    record.stream = StreamType.ERS

    assert strategy.resolve(record, set()) is None


def test_ers_strategy_returns_none_when_level_conf_missing() -> None:
    strategy = ERSAllowedHandlersStrategy()
    record = _record(level=logging.ERROR)
    record.stream = StreamType.ERS
    record.ers_handlers = {"DUNEDAQ_ERS_WARNING": ERSPyLogHandlerConf(handlers=[HandlerType.Rich])}

    assert strategy.resolve(record, set()) is None


def test_ers_strategy_returns_handler_set_when_valid() -> None:
    strategy = ERSAllowedHandlersStrategy()
    record = _record(level=logging.ERROR)
    record.stream = StreamType.ERS
    record.ers_handlers = {
        "DUNEDAQ_ERS_ERROR": ERSPyLogHandlerConf(
            handlers=[HandlerType.Throttle, None],
        )
    }

    assert strategy.resolve(record, set()) == {HandlerType.Throttle}


class _FakeDefault:
    def __init__(self) -> None:
        self.called = False

    def resolve(self, record: logging.LogRecord, fallback_handlers: set[object]) -> set[object] | None:
        del record, fallback_handlers
        self.called = True
        return {HandlerType.File}


class _FakeERS:
    def __init__(self) -> None:
        self.called = False

    def resolve(self, record: logging.LogRecord, fallback_handlers: set[object]) -> set[object] | None:
        del record, fallback_handlers
        self.called = True
        return {HandlerType.Throttle}


def test_streamaware_uses_ers_strategy_for_ers_stream() -> None:
    default = _FakeDefault()
    ers = _FakeERS()
    strategy = StreamAwareAllowedHandlersStrategy(default_strategy=default, ers_strategy=ers)

    record = _record(level=logging.ERROR)
    record.stream = StreamType.ERS

    result = strategy.resolve(record, {HandlerType.Rich})

    assert result == {HandlerType.Throttle}
    assert ers.called is True
    assert default.called is False


def test_streamaware_uses_default_strategy_for_non_ers_stream() -> None:
    default = _FakeDefault()
    ers = _FakeERS()
    strategy = StreamAwareAllowedHandlersStrategy(default_strategy=default, ers_strategy=ers)

    record = _record(level=logging.INFO)

    result = strategy.resolve(record, {HandlerType.Rich})

    assert result == {HandlerType.File}
    assert default.called is True
    assert ers.called is False
