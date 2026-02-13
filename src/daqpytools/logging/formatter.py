import configparser
import logging
import os
import re
from datetime import datetime, tzinfo
from pathlib import Path

from pytz import UnknownTimeZoneError, timezone
from rich.theme import Theme

from daqpytools.logging.exceptions import LoggerConfigurationError

DAQPYTOOLS_LOGGING_ROOT = Path(os.path.abspath(__file__)).parent
CONFIGURATION_FILE = DAQPYTOOLS_LOGGING_ROOT / "log_format.ini"
CONFIG: configparser.ConfigParser = configparser.ConfigParser()
if not CONFIG.read(CONFIGURATION_FILE):
    err_msg = (
        f"Configuration file '{CONFIGURATION_FILE}' not found or could not be read."
    )
    raise FileNotFoundError(err_msg)

LOG_RECORD_PADDING = {k: int(v) for k, v in CONFIG.items("padding")}
if not LOG_RECORD_PADDING:
    err_msg = f"Padding configuration in '{CONFIGURATION_FILE}' is empty or invalid."
    raise LoggerConfigurationError(CONFIGURATION_FILE, err_msg)

LOG_FORMAT = CONFIG.get("logging", "record_format")
if not LOG_FORMAT:
    err_msg = (
        f"Record format in '{CONFIGURATION_FILE}' is empty or not defined under "
        "'format'."
    )
    raise LoggerConfigurationError(CONFIGURATION_FILE, err_msg)

DATE_TIME_FORMAT = CONFIG.get("logging", "date_time")
if not DATE_TIME_FORMAT:
    err_msg = (
        f"Date and time format in '{CONFIGURATION_FILE}' is empty or not defined under "
        "'format'."
    )
    raise LoggerConfigurationError(CONFIGURATION_FILE, err_msg)

DATE_TIME_BASE_FORMAT = CONFIG.get("logging", "date_time_base")
if not DATE_TIME_BASE_FORMAT:
    err_msg = (
        f"Date and time base format in '{CONFIGURATION_FILE}' is empty or not defined "
        "under 'format'."
    )
    raise LoggerConfigurationError(CONFIGURATION_FILE, err_msg)

CONSOLE_THEME = Theme(dict(CONFIG.items("theme")))
if not CONSOLE_THEME:
    err_msg = (
        f"Theme configuration in '{CONFIGURATION_FILE}' is empty or not defined under "
        "'theme'."
    )
    raise LoggerConfigurationError(CONFIGURATION_FILE, err_msg)

timezone_name = CONFIG.get("logging", "timezone")
try:
    TIME_ZONE = timezone(timezone_name)
except UnknownTimeZoneError as e:
    err_msg = (
        f"Unknown time zone '{timezone_name}' specified in '{CONFIGURATION_FILE}'. "
        "Please check the configuration file and ensure the time zone is valid."
    )
    raise LoggerConfigurationError(CONFIGURATION_FILE, err_msg) from e

help_options_str = CONFIG.get("cli", "help_option_names")
HELP_OPTION_NAMES = [opt.strip() for opt in help_options_str.split(",")]
CONTEXT_SETTINGS = {"help_option_names": HELP_OPTION_NAMES}


class LoggingFormatter(logging.Formatter):
    """Overwrites the logging formatter properties."""

    def __init__(
        self, log_format: str = LOG_FORMAT, time_zone: tzinfo = TIME_ZONE
    ) -> None:
        """Overwrites the formatter's default date and time format and time zone."""
        self.datefmt: str = DATE_TIME_FORMAT
        if not self.datefmt:
            err_msg = (
                f"Date and time format in '{CONFIGURATION_FILE}' is empty or not "
                "defined under 'format'."
            )
            raise LoggerConfigurationError(CONFIGURATION_FILE, err_msg)
        self.tz = time_zone
        super().__init__(log_format, self.datefmt)

    def formatTime(  # noqa: N802
        self, record: logging.LogRecord, datefmt: str | None = None
    ) -> str:
        """Overwrites the record's default time format."""
        date_time = datetime.fromtimestamp(record.created, self.tz)
        padding: int = LOG_RECORD_PADDING.get("time", 25)
        if datefmt is None:
            datefmt = self.datefmt
        return date_time.strftime(datefmt).ljust(padding)[:padding]

    def format(self, record: logging.LogRecord) -> str:
        """Defines new format of record.
        Things updated:
        * Time structure to include date and time at pre-determined time_zone.
        * Record filename.
        * Formats record source.
        * Component widths.
        * Removes markdown-style comments from the message.
        """
        if isinstance(record.msg, str):
            record.msg = re.sub(r"\[/?[^\]]+\]", "", record.msg)

        record.asctime = self.formatTime(record, self.datefmt)

        padding = LOG_RECORD_PADDING.get("level", 10)
        record.levelname = record.levelname.ljust(padding)[:padding]

        padding = LOG_RECORD_PADDING.get("file_and_line", 40)
        record.filename = f"{record.filename}:{record.lineno}".ljust(padding)[:padding]

        padding = LOG_RECORD_PADDING.get("logger_name", 40)
        record.name = f"{record.name}".ljust(padding)[:padding]

        return super().format(record)
