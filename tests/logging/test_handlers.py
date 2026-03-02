import logging
import uuid
from collections.abc import Iterator
from unittest.mock import MagicMock, call

import pytest

from daqpytools.apps import logging_demonstrator as demo
from daqpytools.logging.exceptions import ERSInitError, LoggerHandlerError
from daqpytools.logging.filters import HandleIDFilter
from daqpytools.logging.formatter import LoggingFormatter
from daqpytools.logging.handlerconf import HandlerType
from daqpytools.logging.rich_handler import FormattedRichHandler
from daqpytools.logging import handlers as handlers_mod


@pytest.fixture
def clean_logger() -> Iterator[logging.Logger]:
    name = f"test.handlers.{uuid.uuid4()}"
    logger = logging.getLogger(name)
    logger.handlers = []
    logger.filters = []
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    yield logger
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass
    logger.filters = []
    logging.root.manager.loggerDict.pop(name, None)


@pytest.fixture
def parent_child_loggers() -> Iterator[tuple[logging.Logger, logging.Logger]]:
    parent_name = f"test.handlers.parent.{uuid.uuid4()}"
    child_name = f"{parent_name}.child"

    parent = logging.getLogger(parent_name)
    child = logging.getLogger(child_name)

    parent.handlers = []
    parent.filters = []
    parent.propagate = False
    parent.setLevel(logging.DEBUG)

    child.handlers = []
    child.filters = []
    child.propagate = True
    child.setLevel(logging.DEBUG)

    yield parent, child

    for logger in [child, parent]:
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
        logger.filters = []
        logging.root.manager.loggerDict.pop(logger.name, None)


def test_logger_has_handler_non_logger_returns_false() -> None:
    assert handlers_mod.logger_has_handler(MagicMock(), logging.StreamHandler) is False


def test_logger_has_handler_matches_non_stream_type(clean_logger: logging.Logger) -> None:
    handler = logging.NullHandler()
    clean_logger.addHandler(handler)
    assert handlers_mod.logger_has_handler(clean_logger, logging.NullHandler) is True


def test_logger_has_handler_matches_stream_by_target_stream(
    clean_logger: logging.Logger,
) -> None:
    stdout_handler = logging.StreamHandler(handlers_mod.STDOUT_HANDLER_SPEC.target_stream)
    clean_logger.addHandler(stdout_handler)

    assert (
        handlers_mod.logger_has_handler(
            clean_logger,
            logging.StreamHandler,
            target_stream=handlers_mod.STDOUT_HANDLER_SPEC.target_stream,
        )
        is True
    )
    assert (
        handlers_mod.logger_has_handler(
            clean_logger,
            logging.StreamHandler,
            target_stream=handlers_mod.STDERR_HANDLER_SPEC.target_stream,
        )
        is False
    )


def test_logger_has_filter_detects_filter_type(clean_logger: logging.Logger) -> None:
    clean_logger.addFilter(logging.Filter("named.filter"))
    assert handlers_mod.logger_has_filter(clean_logger, logging.Filter) is True


def test_ancestors_have_handlers_returns_false_when_disabled(
    parent_child_loggers: tuple[logging.Logger, logging.Logger],
) -> None:
    _, child = parent_child_loggers
    assert handlers_mod.ancestors_have_handlers(child, False, logging.NullHandler) is False


def test_ancestors_have_handlers_rejects_root_logger() -> None:
    with pytest.raises(ValueError, match="root logger"):
        handlers_mod.ancestors_have_handlers(
            logging.getLogger(),
            True,
            logging.NullHandler,
        )


def test_ancestors_have_handlers_requires_target_for_streamhandler(
    clean_logger: logging.Logger,
) -> None:
    with pytest.raises(ValueError, match="target_stream must be specified"):
        handlers_mod.ancestors_have_handlers(
            clean_logger,
            True,
            logging.StreamHandler,
        )


def test_ancestors_have_handlers_rejects_target_for_non_stream(
    clean_logger: logging.Logger,
) -> None:
    with pytest.raises(ValueError, match="target_stream can only be specified"):
        handlers_mod.ancestors_have_handlers(
            clean_logger,
            True,
            logging.NullHandler,
            target_stream=handlers_mod.STDOUT_HANDLER_SPEC.target_stream,
        )


def test_ancestors_have_handlers_detects_parent_handler(
    parent_child_loggers: tuple[logging.Logger, logging.Logger],
) -> None:
    parent, child = parent_child_loggers
    parent.addHandler(logging.NullHandler())

    assert handlers_mod.ancestors_have_handlers(child, True, logging.NullHandler) is True


def test_check_parent_handlers_raises_loggerhandlererror(
    parent_child_loggers: tuple[logging.Logger, logging.Logger],
) -> None:
    parent, child = parent_child_loggers
    parent.addHandler(logging.NullHandler())

    with pytest.raises(LoggerHandlerError):
        handlers_mod.check_parent_handlers(child, True, logging.NullHandler)


def test_logger_or_ancestors_have_handler_checks_local_then_parent(
    parent_child_loggers: tuple[logging.Logger, logging.Logger],
) -> None:
    parent, child = parent_child_loggers
    assert handlers_mod.logger_or_ancestors_have_handler(child, True, logging.NullHandler) is False

    parent.addHandler(logging.NullHandler())
    assert handlers_mod.logger_or_ancestors_have_handler(child, True, logging.NullHandler) is True


def test_get_handler_specs_returns_expected_specs() -> None:
    assert len(handlers_mod.get_handler_specs(HandlerType.Rich)) == 1
    assert len(handlers_mod.get_handler_specs(HandlerType.Lstdout)) == 1
    assert len(handlers_mod.get_handler_specs(HandlerType.Lstderr)) == 1
    assert len(handlers_mod.get_handler_specs(HandlerType.Stream)) == 2
    assert len(handlers_mod.get_handler_specs(HandlerType.File)) == 1
    assert len(handlers_mod.get_handler_specs(HandlerType.Protobufstream)) == 1


def test_build_rich_handler_uses_get_width_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(handlers_mod, "get_width", lambda: 111)
    handler = handlers_mod._build_rich_handler()
    assert isinstance(handler, FormattedRichHandler)
    assert handler.console.width == 111


def test_build_stdout_handler_sets_formatter() -> None:
    handler = handlers_mod._build_stdout_handler()
    assert isinstance(handler, logging.StreamHandler)
    assert handler.stream is handlers_mod.STDOUT_HANDLER_SPEC.target_stream
    assert isinstance(handler.formatter, LoggingFormatter)


def test_build_stderr_handler_sets_level_and_formatter() -> None:
    handler = handlers_mod._build_stderr_handler()
    assert isinstance(handler, logging.StreamHandler)
    assert handler.stream is handlers_mod.STDERR_HANDLER_SPEC.target_stream
    assert handler.level == logging.ERROR
    assert isinstance(handler.formatter, LoggingFormatter)


def test_build_file_handler_requires_path() -> None:
    with pytest.raises(ValueError, match="path is required"):
        handlers_mod._build_file_handler()


def test_build_file_handler_creates_handler_with_formatter(tmp_path: pytest.TempPathFactory) -> None:
    file_path = tmp_path / "test.log"
    handler = handlers_mod._build_file_handler(path=str(file_path))
    assert isinstance(handler, logging.FileHandler)
    assert isinstance(handler.formatter, LoggingFormatter)
    handler.close()


def test_build_erskafka_handler_wraps_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise RuntimeError("boom")

    monkeypatch.setattr(handlers_mod, "ERSKafkaLogHandler", _raise)
    with pytest.raises(ERSInitError):
        handlers_mod._build_erskafka_handler(session_name="s1")


def test_build_erskafka_handler_success_passes_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeKafkaHandler:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    monkeypatch.setattr(handlers_mod, "ERSKafkaLogHandler", FakeKafkaHandler)
    handler = handlers_mod._build_erskafka_handler(
        session_name="session_x",
        topic="topic_x",
        address="addr_x",
        ers_app_name="app_x",
    )

    assert isinstance(handler, FakeKafkaHandler)
    assert handler.kwargs["session"] == "session_x"
    assert handler.kwargs["kafka_address"] == "addr_x"
    assert handler.kwargs["kafka_topic"] == "topic_x"
    assert handler.kwargs["app_name"] == "app_x"


def test_add_handler_adds_single_spec_and_handleidfilter(clean_logger: logging.Logger) -> None:
    handlers_mod.add_handler(clean_logger, HandlerType.Rich, use_parent_handlers=True)

    assert len(clean_logger.handlers) == 1
    assert isinstance(clean_logger.handlers[0], FormattedRichHandler)
    assert any(
        isinstance(logger_filter, HandleIDFilter)
        for logger_filter in clean_logger.handlers[0].filters
    )


def test_add_handler_skips_when_matching_handler_exists(clean_logger: logging.Logger) -> None:
    handlers_mod.add_handler(clean_logger, HandlerType.Rich, use_parent_handlers=True)
    handlers_mod.add_handler(clean_logger, HandlerType.Rich, use_parent_handlers=True)
    assert len(clean_logger.handlers) == 1


def test_add_handler_skips_when_parent_has_handler(
    parent_child_loggers: tuple[logging.Logger, logging.Logger],
) -> None:
    parent, child = parent_child_loggers
    handlers_mod.add_handler(parent, HandlerType.Rich, use_parent_handlers=True)
    handlers_mod.add_handler(child, HandlerType.Rich, use_parent_handlers=True)

    assert len(parent.handlers) == 1
    assert len(child.handlers) == 0


def test_add_handler_accepts_string_type(clean_logger: logging.Logger) -> None:
    handlers_mod.add_handler(clean_logger, "rich", use_parent_handlers=True)
    assert len(clean_logger.handlers) == 1


def test_add_handler_unknown_string_does_nothing(clean_logger: logging.Logger) -> None:
    handlers_mod.add_handler(clean_logger, "unknown_type", use_parent_handlers=True)
    assert len(clean_logger.handlers) == 0


def test_add_handler_uses_explicit_fallback_override(clean_logger: logging.Logger) -> None:
    override = {HandlerType.Unknown}
    handlers_mod.add_handler(
        clean_logger,
        HandlerType.Rich,
        use_parent_handlers=True,
        fallback_handler=override,
    )

    handler_filter = next(
        logger_filter
        for logger_filter in clean_logger.handlers[0].filters
        if isinstance(logger_filter, HandleIDFilter)
    )
    assert handler_filter.fallback_handlers == override


def test_add_handler_for_stream_adds_stdout_and_stderr(clean_logger: logging.Logger) -> None:
    handlers_mod.add_handler(clean_logger, HandlerType.Stream, use_parent_handlers=True)
    stream_handlers = [
        handler for handler in clean_logger.handlers if isinstance(handler, logging.StreamHandler)
    ]
    assert len(stream_handlers) == 2


def test_add_handlers_from_types_stream_deduplicates(clean_logger: logging.Logger) -> None:
    handlers_mod.add_handlers_from_types(
        clean_logger,
        {HandlerType.Stream, HandlerType.Lstdout, HandlerType.Lstderr},
        use_parent_handlers=True,
        fallback_handlers={HandlerType.Stream},
    )
    stream_handlers = [
        handler for handler in clean_logger.handlers if isinstance(handler, logging.StreamHandler)
    ]
    assert len(stream_handlers) == 2


def test_add_handlers_from_types_routes_to_filter_spec(
    clean_logger: logging.Logger,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    add_filter_mock = MagicMock()
    monkeypatch.setattr(handlers_mod, "add_filter", add_filter_mock)

    handlers_mod.add_handlers_from_types(
        clean_logger,
        {HandlerType.Throttle},
        use_parent_handlers=True,
        fallback_handlers={HandlerType.Throttle},
    )

    add_filter_mock.assert_called_once()


def test_add_handlers_from_types_no_duplicate_filter(
    clean_logger: logging.Logger,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clean_logger.addFilter(MagicMock(spec=handlers_mod.get_filter_spec(HandlerType.Throttle).filter_class))
    add_filter_mock = MagicMock()
    monkeypatch.setattr(handlers_mod, "add_filter", add_filter_mock)

    handlers_mod.add_handlers_from_types(
        clean_logger,
        {HandlerType.Throttle},
        use_parent_handlers=True,
        fallback_handlers={HandlerType.Throttle},
    )

    add_filter_mock.assert_not_called()


# demonstrator test_* parity integrated into handlers tests

def test_demo_test_main_functions_emits_expected_levels() -> None:
    logger = MagicMock(spec=logging.Logger)

    demo.test_main_functions(logger)

    logger.debug.assert_called_once()
    assert logger.info.call_count >= 2
    assert logger.warning.call_count >= 2
    logger.error.assert_called_once()
    logger.critical.assert_called_once()


def test_demo_test_child_logger_builds_child_and_logs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child_logger = MagicMock(spec=logging.Logger)
    get_logger_mock = MagicMock(return_value=child_logger)
    monkeypatch.setattr(demo, "get_daq_logger", get_logger_mock)

    demo.test_child_logger(
        logger_name="parent.logger",
        log_level="INFO",
        disable_logger_inheritance=True,
        rich_handler=True,
        file_handler_path="/tmp/demo.log",
        stream_handlers=True,
    )

    get_logger_mock.assert_called_once_with(
        logger_name="parent.logger.child",
        log_level="INFO",
        use_parent_handlers=False,
        rich_handler=True,
        file_handler_path="/tmp/demo.log",
        stream_handlers=True,
    )
    child_logger.debug.assert_called_once()
    child_logger.info.assert_called()
    child_logger.warning.assert_called()
    child_logger.error.assert_called_once()
    child_logger.critical.assert_called_once()


def test_demo_test_throttle_uses_throttle_extra_and_sleep(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = MagicMock(spec=logging.Logger)
    sleep_mock = MagicMock()
    monkeypatch.setattr(demo.time, "sleep", sleep_mock)

    demo.test_throttle(logger)

    sleep_mock.assert_called_once_with(31)
    logger.warning.assert_called_once_with("Sleeping for 30 seconds")
    assert logger.info.call_count == 1050

    first_call_kwargs = logger.info.call_args_list[0].kwargs
    assert first_call_kwargs["extra"]["handlers"] == [
        HandlerType.Rich,
        HandlerType.Throttle,
    ]


def test_demo_test_handlertypes_routes_expected_extras() -> None:
    logger = MagicMock(spec=logging.Logger)

    demo.test_handlertypes(logger)

    critical_calls = logger.critical.call_args_list
    assert any(c.kwargs.get("extra", {}).get("handlers") == [HandlerType.Rich] for c in critical_calls)
    assert any(c.kwargs.get("extra", {}).get("handlers") == [HandlerType.File] for c in critical_calls)
    assert any(c.kwargs.get("extra", {}).get("handlers") == [HandlerType.Lstdout] for c in critical_calls)
    assert any(c.kwargs.get("extra", {}).get("handlers") == [HandlerType.Throttle] for c in critical_calls)
    assert any(
        c.kwargs.get("extra", {}).get("handlers")
        == [HandlerType.Rich, HandlerType.Protobufstream]
        for c in critical_calls
    )


def test_demo_test_fallback_handlers_calls_add_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = MagicMock(spec=logging.Logger)
    get_logger_mock = MagicMock(return_value=logger)
    add_handler_mock = MagicMock()

    monkeypatch.setattr(demo, "get_daq_logger", get_logger_mock)
    monkeypatch.setattr(demo, "add_handler", add_handler_mock)

    demo.test_fallback_handlers("DEBUG")

    get_logger_mock.assert_called_once_with(
        logger_name="fallback_logger",
        log_level="DEBUG",
        stream_handlers=False,
        rich_handler=True,
    )
    add_handler_mock.assert_has_calls(
        [
            call(logger, HandlerType.Lstdout, True),
            call(
                logger,
                HandlerType.Lstderr,
                True,
                fallback_handler={HandlerType.Unknown},
            ),
        ]
    )
