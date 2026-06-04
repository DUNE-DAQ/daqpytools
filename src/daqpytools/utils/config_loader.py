import configparser
import os
from pathlib import Path
from typing import overload


class ConfigurationError(Exception):
    """Custom error for logger configuration issues."""

    def __init__(self, configuration_file_path: str | Path, err_msg: str) -> None:
        """C'tor."""
        err_msg = (
            f"Configuration file '{configuration_file_path}' could not be read or "
            f"contains invalid configuration:\n {err_msg}"
        )
        super().__init__(err_msg)


class ConfigLoader:
    """Helper to read and validate INI configuration files.

    Provides `safe_load_config` for guarded access to sections and
    options with consistent error messages.
    """

    def __init__(self, config_file: Path | str) -> None:
        """Read a configuration file into a ``ConfigParser`` instance.

        Args:
            config_file: Path to the configuration file.

        Raises:
            FileNotFoundError: If ``config_file`` cannot be found or read.
        """
        self.config_file = config_file
        self.config: configparser.ConfigParser = configparser.ConfigParser()
        self.read_conf(self.config_file)
        
    
    def read_conf(self, conf: str) -> None: 
        """Reads and loads a given config file."""
        if not self.config.read(conf):
            err_msg = (
                f"Configuration file '{self.config_file}' "
                "not found or could not be read."
            )
            raise FileNotFoundError(err_msg)


    @overload
    def safe_load_config(
        self,
        section: str,
    ) -> dict[str, str]:
        ...


    @overload
    def safe_load_config(
        self,
        section: str,
        option: str,
    ) -> str:
        ...


    # define a thing that lets you parse environment variables
    def load_env(self, env_key: str) -> str | None:
        """Read an environment variable and insert it into the
        ``environment`` section of the internal ``ConfigParser``.

        If the section does not exist it will be created. The method stores
        the variable only when it is set and non-empty; if the variable is
        not set (or is an empty string), the config is left unchanged and
        the method returns ``None``. This differs from earlier behaviour that
        used to write an empty string for unset variables.

        Returns the environment value or ``None`` if the variable is not set
        or is empty.
        """
        env_value = os.environ.get(env_key)
        section = "environment"
        if not self.config.has_section(section):
            self.config.add_section(section)

        # Only store the value when the environment variable is set and
        # non-empty. If the variable is unset or empty, leave the config
        # unchanged and return None.
        if env_value:
            self.config.set(section, env_key, env_value)

        return env_value


    def safe_load_config(
        self,
        section: str,
        option: str | None = None,
    ) -> dict[str, str] | str:
        """Safely load configuration content from a section or a single option.

        Behavior:
            - If ``option`` is ``None``, returns all key/value pairs from ``section``.
            - If ``option`` is provided, returns that single option value.

        Validation:
            - Ensures the requested section exists.
            - Ensures section content is non-empty.
            - Ensures the requested option exists when provided.
            - Ensures option values are non-empty.

        Args:
            section: Configuration section name.
            option: Optional option name within ``section``.

        Returns:
            Either ``dict[str, str]`` for section reads or ``str`` for option reads.

        Raises:
            ConfigurationError: If the section/option is missing or empty.
        """
        if option is None:
            if not self.config.has_section(section):
                err_msg = f"Configuration section '{section}' is missing."
                raise ConfigurationError(self.config_file, err_msg)

            values = dict(self.config.items(section))
            if not values:
                err_msg = f"Configuration section '{section}' is empty."
                raise ConfigurationError(self.config_file, err_msg)

            return values

        if not self.config.has_option(section, option):
            err_msg = (
                f"Configuration option '{option}' in section '{section}' is missing."
            )
            raise ConfigurationError(self.config_file, err_msg)

        value = self.config.get(section, option)
        if not value:
            err_msg = (
                f"Configuration option '{option}' in section '{section}' is empty."
            )
            raise ConfigurationError(self.config_file, err_msg)

        return value
