import logging
import os
import re
from copy import copy
from datetime import datetime, tzinfo
from pathlib import Path

from pytz import UnknownTimeZoneError, timezone
from rich.theme import Theme

from daqpytools.logging.exceptions import LoggerConfigurationError
from daqpytools.utils.config_loader import ConfigLoader

DAQPYTOOLS_LOGGING_ROOT = Path(os.path.abspath(__file__)).parent
CONFIGURATION_FILE = DAQPYTOOLS_LOGGING_ROOT / "log_format.ini"

config_loader = ConfigLoader(CONFIGURATION_FILE)

LOG_RECORD_PADDING = {
    k: int(v) for k, v in config_loader.safe_load_config("padding").items()
}
LOG_FORMAT = config_loader.safe_load_config("logging", "record_format")
DATE_TIME_FORMAT = config_loader.safe_load_config("logging", "date_time")
DATE_TIME_BASE_FORMAT = config_loader.safe_load_config("logging", "date_time_base")
CONSOLE_THEME = Theme(config_loader.safe_load_config("theme"))

# timezone_name = config_loader.safe_load_config("logging", "timezone")
timezone_load = config_loader.load_env("DUNEDAQ_TIMEZONE")
timezone_name = config_loader.safe_load_config("environment", "DUNEDAQ_TIMEZONE")

try:
    TIME_ZONE = timezone(timezone_name)
except UnknownTimeZoneError as e:
    err_msg = (
        f"Unknown time zone '{timezone_name}' specified in '{CONFIGURATION_FILE}'. "
        "Please check the configuration file and ensure the time zone is valid."
    )
    raise LoggerConfigurationError(CONFIGURATION_FILE, err_msg) from e

help_options_str = config_loader.safe_load_config("cli", "help_option_names")
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
        formatted_record = copy(record)

        if isinstance(formatted_record.msg, str):
            formatted_record.msg = re.sub(
                r"\[/?[^\]]+\]", "", formatted_record.msg
            )

        formatted_record.asctime = self.formatTime(formatted_record, self.datefmt)

        padding = LOG_RECORD_PADDING.get("level", 10)
        formatted_record.levelname = formatted_record.levelname.ljust(padding)[:padding]

        padding = LOG_RECORD_PADDING.get("file_and_line", 40)
        formatted_record.filename = (
            f"{formatted_record.filename}:{formatted_record.lineno}".ljust(padding)[
                :padding
            ]
        )

        padding = LOG_RECORD_PADDING.get("logger_name", 40)
        formatted_record.name = f"{formatted_record.name}".ljust(padding)[:padding]

        return super().format(formatted_record)
