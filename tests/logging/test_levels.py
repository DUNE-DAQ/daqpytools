import pytest

from daqpytools.logging.levels import (
    logging_log_level_to_int,
    logging_log_level_to_str,
    oks_log_level_to_int,
    oks_log_level_to_str,
)

invalid_log_level_str = "INVALID_LEVEL"
invalid_log_level_int = 15
invalid_log_level_type = None

def test_logging_log_level_to_str() -> None:
    """Check function logging_log_level_to_str works as intended.
    """
    # Correct cases
    assert logging_log_level_to_str("DEBUG") == "DEBUG"
    assert logging_log_level_to_str("INFO") == "INFO"
    assert logging_log_level_to_str("WARNING") == "WARNING"
    assert logging_log_level_to_str("ERROR") == "ERROR"
    assert logging_log_level_to_str("CRITICAL") == "CRITICAL"
    assert logging_log_level_to_str(0) == "NOTSET"
    assert logging_log_level_to_str(10) == "DEBUG"
    assert logging_log_level_to_str(20) == "INFO"
    assert logging_log_level_to_str(30) == "WARNING"
    assert logging_log_level_to_str(40) == "ERROR"
    assert logging_log_level_to_str(50) == "CRITICAL"

    # Exception raising cases
    with pytest.raises(ValueError, match=f"Level '{invalid_log_level_str}' is not from the recognized logging levels"):
        logging_log_level_to_str(invalid_log_level_str)
    with pytest.raises(ValueError, match=f"Level '{invalid_log_level_int}' is not from the recognized logging level values"):
        logging_log_level_to_str(invalid_log_level_int)
    with pytest.raises(TypeError, match=f"Log level must be a string or an integer. Received type {type(invalid_log_level_type).__name__}."):
        logging_log_level_to_str(invalid_log_level_type)


def test_logging_log_level_to_int() -> None:
    """Check function logging_log_level_to_int works as intended.
    """
    # Correct cases
    assert logging_log_level_to_int("NOTSET") == 0
    assert logging_log_level_to_int("DEBUG") == 10
    assert logging_log_level_to_int("INFO") == 20
    assert logging_log_level_to_int("WARNING") == 30
    assert logging_log_level_to_int("ERROR") == 40
    assert logging_log_level_to_int("CRITICAL") == 50
    assert logging_log_level_to_int(10) == 10
    assert logging_log_level_to_int(20) == 20
    assert logging_log_level_to_int(30) == 30
    assert logging_log_level_to_int(40) == 40
    assert logging_log_level_to_int(50) == 50

    # Exception raising cases
    with pytest.raises(ValueError, match=f"Level '{invalid_log_level_str}' is not from the recognized logging levels"):
        logging_log_level_to_int(invalid_log_level_str)
    with pytest.raises(ValueError, match=f"Level '{invalid_log_level_int}' is not from the recognized logging level values"):
        logging_log_level_to_int(invalid_log_level_int)
    with pytest.raises(TypeError, match=f"Log level must be a string or an integer. Received type {type(invalid_log_level_type).__name__}."):
        logging_log_level_to_int(invalid_log_level_type)


def test_oks_log_level_to_str() -> None:
    """Check function oks_log_level_to_str works as intended.
    """
    # Correct cases
    assert oks_log_level_to_str("kLowestPriority") == "DEBUG"
    assert oks_log_level_to_str("kDefault") == "INFO"
    assert oks_log_level_to_str("kEventDriven") == "WARNING"
    assert oks_log_level_to_str("kTopPriority") == "ERROR"
    assert oks_log_level_to_str(4294967295) == "DEBUG"
    assert oks_log_level_to_str(2147483648) == "INFO"
    assert oks_log_level_to_str(1073741824) == "WARNING"
    assert oks_log_level_to_str(0) == "ERROR"

    # Exception raising cases
    with pytest.raises(ValueError, match=f"Level '{invalid_log_level_str}' is not from the recognized OKS levels"):
        oks_log_level_to_str(invalid_log_level_str)
    with pytest.raises(ValueError, match=f"Level '{invalid_log_level_int}' is not from the recognized OKS values"):
        oks_log_level_to_str(invalid_log_level_int)
    with pytest.raises(TypeError, match=f"Log level must be a string or an integer. Received type {type(invalid_log_level_type).__name__}."):
        oks_log_level_to_str(invalid_log_level_type)


def test_oks_log_level_to_int() -> None:
    """Check function oks_log_level_to_int works as intended.
    """
    # Correct cases
    assert oks_log_level_to_int("kLowestPriority") == 10
    assert oks_log_level_to_int("kDefault") == 20
    assert oks_log_level_to_int("kEventDriven") == 30
    assert oks_log_level_to_int("kTopPriority") == 40
    assert oks_log_level_to_int(4294967295) == 10
    assert oks_log_level_to_int(2147483648) == 20
    assert oks_log_level_to_int(1073741824) == 30
    assert oks_log_level_to_int(0) == 40

    # Exception raising cases
    with pytest.raises(ValueError, match=f"Level '{invalid_log_level_str}' is not from the recognized OKS levels"):
        oks_log_level_to_int(invalid_log_level_str)
    with pytest.raises(ValueError, match=f"Level '{invalid_log_level_int}' is not from the recognized OKS values"):
        oks_log_level_to_int(invalid_log_level_int)
    with pytest.raises(TypeError, match=f"Log level must be a string or an integer. Received type {type(invalid_log_level_type).__name__}."):
        oks_log_level_to_int(invalid_log_level_type)
