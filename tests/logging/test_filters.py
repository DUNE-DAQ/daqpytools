import logging
import uuid
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest

from daqpytools.logging.filters import (
    HandleIDFilter,
    ThrottleFilter,
    add_filter,
    add_throttle_filter,
    get_filter_spec,
)
from daqpytools.logging.handlerconf import HandlerType


def _record(level: int = logging.INFO) -> logging.LogRecord:
    return logging.LogRecord(
        name="test.filters",
        level=level,
        pathname="<test>",
        lineno=42,
        msg="message",
        args=(),
        exc_info=None,
    )


@pytest.fixture
def clean_logger() -> Iterator[logging.Logger]:
    name = f"test.filters.{uuid.uuid4()}"
    logger = logging.getLogger(name)
    logger.handlers = []
    logger.filters = []
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    yield logger
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    logger.filters = []
    logging.root.manager.loggerDict.pop(name, None)


def test_get_filter_spec_registry_lookup() -> None:
    assert get_filter_spec(HandlerType.Throttle) is not None
    assert get_filter_spec(HandlerType.Rich) is None


def test_add_filter_uses_default_fallback_from_spec(
    clean_logger: logging.Logger,
) -> None:
    add_filter(clean_logger, HandlerType.Throttle, fallback_handlers=None)

    assert len(clean_logger.filters) == 1
    logger_filter = clean_logger.filters[0]
    assert isinstance(logger_filter, ThrottleFilter)
    assert logger_filter.fallback_handlers == {HandlerType.Throttle}


def test_add_filter_uses_explicit_fallback_and_extras(
    clean_logger: logging.Logger,
) -> None:
    add_filter(
        clean_logger,
        HandlerType.Throttle,
        fallback_handlers={HandlerType.Unknown},
        initial_treshold=7,
        time_limit=11,
    )

    logger_filter = clean_logger.filters[0]
    assert isinstance(logger_filter, ThrottleFilter)
    assert logger_filter.fallback_handlers == {HandlerType.Unknown}
    assert logger_filter.initial_threshold == 7
    assert logger_filter.time_limit == 11


def test_add_throttle_filter_delegates_to_add_filter(
    clean_logger: logging.Logger,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    add_filter_mock = MagicMock()
    monkeypatch.setattr("daqpytools.logging.filters.add_filter", add_filter_mock)

    add_throttle_filter(clean_logger, fallback_handlers={HandlerType.Throttle})

    add_filter_mock.assert_called_once_with(
        clean_logger,
        HandlerType.Throttle,
        {HandlerType.Throttle},
    )


def test_handleid_filter_matches_with_fallback_when_record_handlers_missing() -> None:
    logger_filter = HandleIDFilter(
        handler_id=HandlerType.Rich,
        fallback_handlers={HandlerType.Rich},
    )

    assert logger_filter.filter(_record()) is True


def test_handleid_filter_rejects_when_no_allowed_handlers() -> None:
    logger_filter = HandleIDFilter(
        handler_id=HandlerType.Rich,
        fallback_handlers={HandlerType.Rich},
    )
    record = _record()
    record.handlers = None

    assert logger_filter.filter(record) is False


def test_throttle_filter_passthrough_when_throttle_not_allowed() -> None:
    logger_filter = ThrottleFilter(
        fallback_handlers={HandlerType.Rich},
        initial_threshold=1,
        time_limit=60,
    )

    assert logger_filter.filter(_record(level=logging.ERROR)) is True


def test_throttle_filter_suppresses_after_initial_threshold() -> None:
    logger_filter = ThrottleFilter(
        fallback_handlers={HandlerType.Throttle},
        initial_threshold=1,
        time_limit=60,
    )
    record = _record(level=logging.ERROR)

    assert logger_filter.filter(record) is True
    assert logger_filter.filter(record) is False
