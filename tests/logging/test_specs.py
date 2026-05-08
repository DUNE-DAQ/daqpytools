import logging
from dataclasses import FrozenInstanceError

import pytest

from daqpytools.logging.specs import FilterSpec, HandlerSpec


def _handler_factory(**kwargs: object) -> logging.Handler:
    del kwargs
    return logging.NullHandler()


def _filter_factory(
    fallback_handlers: set[object], extras: dict[str, object]
) -> logging.Filter:
    del fallback_handlers, extras
    return logging.Filter()


def test_handlerspec_is_frozen() -> None:
    spec = HandlerSpec(
        alias="rich",
        handler_class=logging.NullHandler,
        factory=_handler_factory,
        fallback_types=("rich",),
    )

    with pytest.raises(FrozenInstanceError):
        spec.alias = "stream"


def test_handlerspec_stores_target_stream_optional() -> None:
    spec_without = HandlerSpec(
        alias="a",
        handler_class=logging.NullHandler,
        factory=_handler_factory,
        fallback_types=("a",),
    )
    assert spec_without.target_stream is None

    stream = object()
    spec_with = HandlerSpec(
        alias="b",
        handler_class=logging.StreamHandler,
        factory=_handler_factory,
        fallback_types=("b",),
        target_stream=stream,
    )
    assert spec_with.target_stream is stream


def test_handlerspec_factory_signature_compatible() -> None:
    spec = HandlerSpec(
        alias="rich",
        handler_class=logging.NullHandler,
        factory=_handler_factory,
        fallback_types=("rich",),
    )
    handler = spec.factory(width=120)
    assert isinstance(handler, logging.NullHandler)


def test_filterspec_is_frozen() -> None:
    spec = FilterSpec(
        alias="throttle",
        filter_class=logging.Filter,
        factory=_filter_factory,
    )

    with pytest.raises(FrozenInstanceError):
        spec.alias = "x"


def test_filterspec_defaults_fallback_types_to_empty_tuple() -> None:
    spec = FilterSpec(
        alias="throttle",
        filter_class=logging.Filter,
        factory=_filter_factory,
    )
    assert spec.fallback_types == ()


def test_filterspec_accepts_factory_and_alias() -> None:
    spec = FilterSpec(
        alias="throttle",
        filter_class=logging.Filter,
        factory=_filter_factory,
        fallback_types=("throttle",),
    )

    assert spec.alias == "throttle"
    assert spec.filter_class is logging.Filter
    assert spec.fallback_types == ("throttle",)
    assert isinstance(spec.factory(set(), {}), logging.Filter)
