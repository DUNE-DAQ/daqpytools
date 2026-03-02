import logging
import uuid
from unittest.mock import MagicMock

import pytest

from daqpytools.apps import logging_demonstrator as demo
from daqpytools.logging.exceptions import ERSEnvError, ProtobufFormatError
from daqpytools.logging.handlerconf import (
    ERSPyLogHandlerConf,
    HandlerType,
    LogHandlerConf,
    ProtobufConf,
    StreamType,
)
from daqpytools.logging.levels import level_to_ers_var


def test_handlertype_from_string_case_insensitive() -> None:
    assert HandlerType.from_string("RiCh") == HandlerType.Rich


def test_handlertype_from_string_unknown_returns_none() -> None:
    assert HandlerType.from_string("definitely_unknown") is None


def test_protobufconf_get_string_formats_url_port() -> None:
    conf = ProtobufConf(url="host", port=1234)
    assert conf.get_string() == "host:1234"


def test_loghandlerconf_ers_property_raises_before_init() -> None:
    conf = LogHandlerConf(init_ers=False)
    with pytest.raises(AttributeError, match="ERS stream not initialised"):
        _ = conf.ERS


def test_loghandlerconf_init_ers_stream_sets_structure(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_oks = {"DUNEDAQ_ERS_ERROR": ERSPyLogHandlerConf(handlers=[HandlerType.Rich])}
    monkeypatch.setattr(LogHandlerConf, "_get_oks_conf", staticmethod(lambda: fake_oks))

    conf = LogHandlerConf(init_ers=False)
    conf.init_ers_stream()

    assert conf.ERS["ers_handlers"] == fake_oks
    assert conf.ERS["stream"] == StreamType.ERS


def test_loghandlerconf_post_init_calls_init_when_flag_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_oks = {"DUNEDAQ_ERS_ERROR": ERSPyLogHandlerConf(handlers=[HandlerType.Rich])}
    monkeypatch.setattr(LogHandlerConf, "_get_oks_conf", staticmethod(lambda: fake_oks))

    conf = LogHandlerConf(init_ers=True)
    assert conf.ERS["ers_handlers"] == fake_oks


def test_get_base_returns_copy_not_original_reference() -> None:
    base_one = LogHandlerConf.get_base()
    base_two = LogHandlerConf.get_base()

    base_one.add(HandlerType.Unknown)

    assert HandlerType.Unknown in base_one
    assert HandlerType.Unknown not in base_two


def test_convert_str_to_handlertype_ignores_erstrace() -> None:
    handler, protobuf_conf = LogHandlerConf._convert_str_to_handlertype("erstrace")
    assert handler is None
    assert protobuf_conf is None


def test_convert_str_to_handlertype_regular_handler() -> None:
    handler, protobuf_conf = LogHandlerConf._convert_str_to_handlertype("throttle")
    assert handler == HandlerType.Throttle
    assert protobuf_conf is None


def test_convert_str_to_handlertype_parses_protobuf_with_url_port() -> None:
    handler, protobuf_conf = LogHandlerConf._convert_str_to_handlertype(
        "protobufstream(monkafka.cern.ch:30092)"
    )
    assert handler == HandlerType.Protobufstream
    assert protobuf_conf == ProtobufConf(url="monkafka.cern.ch", port=30092)


def test_convert_str_to_handlertype_invalid_protobuf_format_raises() -> None:
    with pytest.raises(ProtobufFormatError):
        LogHandlerConf._convert_str_to_handlertype("protobufstream(bad-format)")


def test_make_ers_handler_conf_raises_when_env_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("os.getenv", lambda _: None)
    with pytest.raises(ERSEnvError):
        LogHandlerConf._make_ers_handler_conf("DUNEDAQ_ERS_ERROR")


def test_make_ers_handler_conf_parses_multiple_handlers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "os.getenv",
        lambda _: "erstrace, throttle, lstdout, protobufstream(host:1234)",
    )

    conf = LogHandlerConf._make_ers_handler_conf("DUNEDAQ_ERS_ERROR")

    assert HandlerType.Throttle in conf.handlers
    assert HandlerType.Lstdout in conf.handlers
    assert conf.protobufconf == ProtobufConf(url="host", port=1234)


def test_get_oks_conf_builds_mapping_for_all_ers_level_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def _fake_make(level_var: str) -> ERSPyLogHandlerConf:
        calls.append(level_var)
        return ERSPyLogHandlerConf(handlers=[HandlerType.Rich])

    monkeypatch.setattr(LogHandlerConf, "_make_ers_handler_conf", staticmethod(_fake_make))

    conf = LogHandlerConf._get_oks_conf()

    assert set(calls) == set(level_to_ers_var.values())
    assert set(conf.keys()) == set(level_to_ers_var.values())


# demonstrator test_* parity integrated into handlerconf tests

def test_demo_test_handlerconf_runs_ers_flow_and_restores(monkeypatch: pytest.MonkeyPatch) -> None:
    logger = MagicMock(spec=logging.Logger)

    class FakeHC:
        Base = {"handlers": {HandlerType.Stream}, "stream": StreamType.BASE}
        Opmon = {"handlers": {HandlerType.Rich}, "stream": StreamType.OPMON}

        def __init__(self, init_ers: bool = False) -> None:
            self._ers = {
                "ers_handlers": {"DUNEDAQ_ERS_ERROR": ERSPyLogHandlerConf(handlers=[HandlerType.Rich])},
                "stream": StreamType.ERS,
            }
            if init_ers:
                self.init_ers_stream()

        @property
        def ERS(self) -> dict:
            return self._ers

        def init_ers_stream(self) -> None:
            return None

    restore_mock = MagicMock()

    monkeypatch.setattr(demo, "LogHandlerConf", FakeHC)
    monkeypatch.setattr(demo, "restore_original_envs", restore_mock)

    demo.test_handlerconf(logger)

    restore_mock.assert_called_once()
    logger.warning.assert_called()
    logger.info.assert_called()


def test_demo_test_ers_handler_configuration_calls_setup_and_logs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger_name = f"demo.ers.{uuid.uuid4()}"
    logger = logging.getLogger(logger_name)
    logger.handlers = []
    logger.filters = []
    logger.propagate = False

    get_logger_mock = MagicMock(return_value=logger)
    setup_mock = MagicMock()

    class FakeHC:
        def __init__(self, init_ers: bool = False) -> None:
            assert init_ers is True
            self._ers = {"stream": StreamType.ERS, "ers_handlers": {}}

        @property
        def ERS(self) -> dict:
            return self._ers

    monkeypatch.setattr(demo, "get_daq_logger", get_logger_mock)
    monkeypatch.setattr(demo, "setup_daq_ers_logger", setup_mock)
    monkeypatch.setattr(demo, "LogHandlerConf", FakeHC)

    demo.test_ers_handler_configuration("INFO")

    get_logger_mock.assert_called_once()
    setup_mock.assert_called_once_with(logger, "session_temp")

    logging.root.manager.loggerDict.pop(logger_name, None)
