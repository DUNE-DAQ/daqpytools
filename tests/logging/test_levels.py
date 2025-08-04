from daqpytools.logging.levels import log_level_to_int, log_level_to_str


def test_log_level_to_str() -> None:
    """Test that the log_level_to_str function works correctly."""
    assert log_level_to_str("DEBUG") == "DEBUG"
    assert log_level_to_str("INFO") == "INFO"
    assert log_level_to_str("WARNING") == "WARNING"
    assert log_level_to_str("ERROR") == "ERROR"
    assert log_level_to_str("CRITICAL") == "CRITICAL"
    assert log_level_to_str(10) == "DEBUG"
    assert log_level_to_str(20) == "INFO"
    assert log_level_to_str(30) == "WARNING"
    assert log_level_to_str(40) == "ERROR"
    assert log_level_to_str(50) == "CRITICAL"


def test_log_level_to_int() -> None:
    """Test that the log_level_to_int function works correctly."""
    assert log_level_to_int("DEBUG") == 10
    assert log_level_to_int("INFO") == 20
    assert log_level_to_int("WARNING") == 30
    assert log_level_to_int("ERROR") == 40
    assert log_level_to_int("CRITICAL") == 50
    assert log_level_to_int(10) == 10
    assert log_level_to_int(20) == 20
    assert log_level_to_int(30) == 30
    assert log_level_to_int(40) == 40
    assert log_level_to_int(50) == 50
